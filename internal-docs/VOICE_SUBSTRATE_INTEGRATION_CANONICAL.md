# Voice Substrate Integration Canonical

## Purpose

This is the canonical integration contract for external apps that need to use Aether Voice as a speech substrate.

Use this document as the single source of integration truth.

Use dated runbooks for lane-specific operational notes, experiments, and rollout deltas.

## Scope

This canonical contract covers:
- batch ASR
- realtime ASR
- batch TTS
- realtime TTS
- server-side voice turn orchestration
- Studio voice registry read/write for route-aware voice selection
- auth, tenant, and scope expectations

It does not replace:
- provider-specific experiment repos (`qwen-experiments`, `voxtream-experiments`)
- dated operational runbooks
- internal deployment playbooks

## Stable Integration Rule

External apps must integrate with the gateway surface only.

Do not integrate directly with internal ASR/TTS service containers or provider sidecars unless you are intentionally running a provider-debug harness.

## Base URLs

Current production-like substrate deployment:
- HTTP: `https://asr.aetherpro.us/api`
- WebSocket: `wss://asr.aetherpro.us`

Path contracts are stable; hostnames can change per environment.

## Authentication And Tenant Contract

### Accepted auth modes

Gateway supports three modes based on deployment config:
1. optional anonymous mode (`AUTH_MODE=optional`)
2. API key via `X-API-Key`
3. JWT via `Authorization: Bearer <token>`

Current code truth:
- API key auth validates `sha256(key)` against Postgres table `api_keys.key_hash` where `is_active=true`.
- JWT auth validates `HS256` with `JWT_SECRET`.
- Optional mode falls back to default tenant with broad voice scopes.

### Tenant truth

- default tenant UUID: `00000000-0000-0000-0000-000000000001`
- tenant is resolved by auth context
- internal service calls propagate tenant via `X-Tenant-Id`

Integration rule:
- callers should not invent tenant semantics per endpoint
- callers authenticate once at gateway and let gateway apply tenant routing/scoping

### Scope truth

Endpoints enforce scopes via gateway middleware/dependencies.
Current common scopes:
- `voice:asr`
- `voice:tts`
- `voice:triage`
- `voice:sessions:read`
- `voice:metrics:read`

## Core API Surface

### ASR

- `POST /v1/asr/transcribe`
  - batch transcription
- `POST /v1/asr/stream/start`
  - starts realtime ASR session and returns websocket URL
- `WS /v1/asr/stream/{session_id}`
  - audio-frame ingest and transcript events

### TTS

- `POST /v1/tts/synthesize`
  - batch synthesis
- `POST /v1/tts/stream/start`
  - starts realtime TTS session and returns websocket URL
- `WS /v1/tts/stream/{session_id}`
  - text push and audio events

### Voice turn orchestration

- `POST /v1/voice/turn`
  - server-side turn orchestration lane (ASR->LLM->TTS flow where configured)

### Studio voice registry + routing

- `GET /v1/tts/studio/overview`
- `GET /v1/tts/studio/voices`
- `POST /v1/tts/studio/voices`
- `POST /v1/tts/studio/voices/import`
- `GET /v1/tts/studio/providers`
- `GET /v1/tts/studio/providers/{provider}/models`
- `GET /v1/tts/studio/routing`
- `POST /v1/tts/studio/routing`
- `POST /v1/tts/studio/routes/{route_name}/warmup`

### Models, sessions, metrics

- `GET /v1/models`
- `GET /v1/sessions`
- `GET /v1/sessions/{id}`
- `GET /v1/metrics`

## Realtime Contract Shape

### Realtime ASR flow

1. `POST /v1/asr/stream/start`
2. connect returned websocket URL
3. send JSON `audio_frame` messages (`pcm_s16le`, mono, 16k)
4. receive partial/final transcript events
5. send `end_stream` to finalize

### Realtime TTS flow

1. `POST /v1/tts/stream/start`
2. connect returned websocket URL
3. send text chunks/events
4. receive audio chunk events + final artifact
5. end stream and consume final download URL when provided

## Voice Selection And Registry Rules

Voice dropdowns must be populated from Studio registry, not provider `/v1/voices`, for product flows.

Routing rule:
- filter voices by `runtime_target` for the active model route.

Examples:
- `kokoro_realtime` -> Kokoro preset voices
- `voxtream2_realtime` -> imported/seeded reference voices with `reference_audio_path`
- `qwen_customvoice*` -> qwen preset/runtime-target voices

Provider `/v1/voices` remains useful for provider diagnostics only.

## Warmup Rule

Warmup should be triggered via gateway studio route endpoint:
- `POST /v1/tts/studio/routes/{route_name}/warmup`

This keeps auth/tenant/routing consistent and avoids direct provider coupling in product clients.

## Canonical Known Routes (Current)

Realtime and/or batch route families currently wired in the substrate include:
- `voxtral_realtime` (ASR)
- `faster_whisper` (ASR batch/fallback path)
- `kokoro_realtime` (TTS realtime baseline)
- `voxtream_realtime` (TTS realtime experimental lane)
- `voxtream2_realtime` (TTS realtime experimental lane)
- `qwen_customvoice` (TTS batch)
- `qwen_customvoice_streaming` (TTS streaming eval lane)
- `qwen_voice_design` (TTS voice-design lane)
- `chatterbox` (compatibility batch fallback)

Operational promotion status is tracked in `PROJECT_STATE.md` and dated runbooks.

## Error Handling Contract

External clients must treat these classes distinctly:
- `400` caller payload/contract error
- `401` missing/invalid auth
- `403` missing scope
- `409` session lifecycle conflict
- `5xx` upstream/runtime/internal failure

Recommended behavior:
- log request ID + session ID
- surface actionable message to operator
- retry only idempotent calls

## Integration Profiles

### Profile A: Product app integration (recommended)

Use gateway-only endpoints for all speech operations and studio reads.

Benefits:
- one auth surface
- tenant and scope consistency
- stable contract while providers evolve

### Profile B: Provider debug harness

Use provider endpoints directly only for lane bring-up, warmup benchmarking, and low-level diagnostics.

Keep this isolated from product runtime paths.

## API Key Platform Readiness (Current Truth)

What already exists in this repo:
- API key authentication check in gateway auth resolver
- `api_keys` table in Postgres bootstrap schema

What does not yet exist here:
- public API for key creation/list/revocation
- scoped key management UX
- first-class usage/billing key lifecycle endpoints

Implication:
- your future `platform.aetherpro.us` is the correct place to own key lifecycle
- this substrate can remain the enforcement plane

## Recommended Platform Split

For your planned platform/admin surface:

1. Platform service owns:
- user/org auth
- subscription + billing
- API key issuance and revocation
- scope templates and tenant bindings

2. Voice substrate owns:
- key validation and scope enforcement
- speech runtime execution
- session/request telemetry

3. Contract between platform and substrate:
- platform writes hashed keys + tenant/scope metadata to shared auth store or auth service
- substrate validates on each request

## Minimum Cross-Repo Questions (Use This Checklist)

When integrating any app/harness into Aether Voice, ask:

1. Base URLs
- Which HTTP and WS base URLs are used in this environment?

2. Auth mode
- Is substrate running `AUTH_MODE=optional` or `AUTH_MODE=strict`?
- Which header is expected (`X-API-Key`, `Authorization`)?

3. Tenant mapping
- Which tenant should this app run under?

4. Endpoint contract
- Which exact substrate endpoints does this app call?

5. Realtime behavior
- Who owns websocket lifecycle and retries?

6. Voice sourcing
- Does app load voices from Studio registry and filter by `runtime_target`?

7. Warmup
- Does app call route warmup via gateway for first-load lanes?

8. Model fallback
- What should happen when requested route is unavailable?

9. Observability
- Where are session IDs, request IDs, and timing metrics stored/exposed?

10. Deployment boundaries
- Is app cross-VM? If yes, are calls using public hostname (not localhost)?

## Related Documents

- [VOICE_SUBSTRATE_API_INTEGRATION_RUNBOOK_2026-03-26.md](/home/cory/Aether-Voice-Platform/Aether-Voice-X/VOICE_SUBSTRATE_API_INTEGRATION_RUNBOOK_2026-03-26.md)
- [VOICEOPS_REALTIME_VOICE_API_CONTRACT_2026-03-14.md](/home/cory/Aether-Voice-Platform/Aether-Voice-X/VOICEOPS_REALTIME_VOICE_API_CONTRACT_2026-03-14.md)
- [PROJECT_STATE.md](/home/cory/Aether-Voice-Platform/Aether-Voice-X/PROJECT_STATE.md)
