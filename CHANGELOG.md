# Changelog

## 2026-06-29 — live call no longer re-asks already-answered fields

- Symptom on the Mary's Beauty Spa demo line (`+18127212341`, legacy `session_manager` path, `FSM_PIPELINE_ENABLED=false`): the agent asked "what service" again after the caller had already answered it and moved on to the phone number.
- Root cause: the live LLM turn was sent only `[system, user]` with no transcript, so the stateless model's only memory of what was answered was the `Missing required fields` list. A vague/free-text answer that the regex extractor could not normalize was never marked collected, so it stayed "missing" and the model dutifully re-asked. The tracked `prompted_field` is also only `missing_fields[0]` (a guess), not what the model actually asked, so answers could be matched against the wrong field and dropped.
- Fix (backend only):
  - `agent_runtime.generate_response` now accepts `conversation_history` and replays the recent turns to the LLM (capped at `MAX_LLM_HISTORY_MESSAGES = 8`), and the system prompt now treats the conversation as the source of truth — never re-ask something already answered, even if still under `Missing required fields`.
  - `session_manager` maintains `VoiceSession.conversation_history` (seeded with the opening greeting, appended per turn, trimmed) and passes it into the LLM call.
  - `capture_required_fields` now records a prompted **soft/free-text** field from a substantive spoken answer when no specialized extractor normalizes it; structured `name`/`phone` fields keep strict extraction + retry/skip-ahead.
- Tests: added history-replay, soft-field capture, and structured-field-guard cases to `tests/test_agent_runtime.py` (77 passed across agent_runtime/session_manager/state_controller).

## 2026-06-29 — nginx allowlist refresh + recovery stack restart (deploy VM)

- `voice.aetherpro.us` was returning nginx `403 Forbidden` for the operator browser: Xfinity rotated the operator public IP to `73.145.241.211`, which was not in the `voiceops-recovery.conf` allowlist (rolling-IP problem).
- Confirmed the gate is the intentional `allow`/`deny` block in `/etc/nginx/sites-enabled/voiceops-recovery.conf`; Tailnet `100.64.0.0/10` and prior operator IPs `73.145.240.8`/`73.145.242.40` were already allowed.
- Added `73.145.241.211` to all four restricted blocks (aetherpro `/api/v1/`, `= /api/v1`, `/`, and syndicateai `/`); `sudo nginx -t` clean, `sudo systemctl reload nginx` OK.
- Moved the config backup out of `sites-enabled/` to `/etc/nginx/backups/` (a `.bak` left in `sites-enabled/` was being parsed by nginx and produced `conflicting server name` warnings).
- Recovery stack had been taken down by a `docker compose` run against the default `docker-compose.yml` (external network `aether_net` missing) instead of `docker-compose.recovery.yml` (network `acer_infra`). Restored with `docker compose -f docker-compose.recovery.yml up -d --build`; this also deployed the Voxtral TTS lane (FF of the deploy branch to `b7937c2`).
- Verified post-restart: FE `127.0.0.1:3102` → 200, BE `127.0.0.1:8102` healthy (401 auth-gated), backend registry exposes `voxtral_casual_female`, frontend image carries the `voxtral_tts` dropdown entry.
- Rotation-proof follow-up: reach the UI over Tailnet (node `100.92.18.20`) via a laptop `/etc/hosts` override so future Xfinity rotations stop mattering.

## 2026-06-27 — VoiceOps nginx allowlist refresh

- Investigated `https://voice.aetherpro.us` returning nginx `403 Forbidden` for the operator browser.
- Verified the request matched `/etc/nginx/sites-enabled/voiceops-recovery.conf` and was blocked by the intentional app/admin `allow`/`deny` gate, not by an upstream failure.
- Verified `voiceops-frontend-recovery` and `voiceops-backend-recovery` were healthy on `127.0.0.1:3102` and `127.0.0.1:8102`.
- Added operator public IP `73.145.242.40` to the restricted nginx allowlist while keeping Tailnet access and the previous operator IP.
- Validation: `sudo nginx -t` passed, then `sudo systemctl reload nginx` completed.

## 2026-06-29 — Voxtral TTS demo lane added to operator builders

- Added the `voxtral_tts` lane to the VoiceOps TTS model dropdown (inbound, outbound, and agents builders share `services/frontend/lib/operator-builder.js`).
  - Canonical gateway model id is `voxtral_tts` (Aether-Voice-X also aliases `voxtral-tts` -> `voxtral_tts`).
  - Runs as a separate provider container (`~/Aether-Voice-Platform/voxtral-tts`, `Voxtral-4B-TTS-2603` on the L4-360 GPU) behind the Aether-Voice-X gateway.
- Seeded the provider's preset voice `voxtral_casual_female` (raw provider name `casual_female`):
  - backend static registry `services/backend/app/services/tts/voice_registry.py` (`list_tts_voices()`)
  - frontend offline fallback `DEFAULT_VOICE_OPTIONS`
- Marked the lane conservatively (`telephony_recommended=False`, `barge_in_quality=unverified`, `latency_profile=unverified`) so the existing non-baseline operator warning surfaces — this is an internal premium demo lane (output not licensed for client sale), not a qualified live telephony baseline.
- Added/updated tests:
  - `services/backend/tests/test_tts_voice_registry.py`
- Verification:
  - `cd services/backend && pytest -q tests/test_tts_voice_registry.py`

## 2026-06-26 — telephony lane truth surfaced in inbound builder

- Diagnosed the Mary demo talk-over regression against live runtime evidence instead of guessing:
  - live save/mapping path was working
  - live `+18127212341` was reading the updated mapped agent row
  - recovery deployment was still on the legacy telephony runtime (`FSM_PIPELINE_ENABLED=false`)
  - strongest causal shift was TTS lane change from `kokoro_realtime` to `voxtream2_realtime`
- Added explicit TTS capability metadata to the backend voice contract in:
  - `services/backend/app/schemas/agent.py`
  - `services/backend/app/services/tts/voice_registry.py`
- Voice metadata now includes:
  - `telephony_recommended`
  - `barge_in_quality`
  - `latency_profile`
  - `operator_note`
- Marked current lane truth conservatively:
  - `kokoro_realtime` = qualified/recommended live inbound baseline
  - `qwen_*` voices = unverified for live inbound baseline
  - `voxtream2_realtime` studio voices = degraded for live inbound based on observed 2026-06-26 runtime traces
- Updated inbound workflow editor to surface a visible warning when an operator selects a non-baseline live TTS voice/lane.
- Added/updated tests:
  - `services/backend/tests/test_tts_voice_registry.py`
- Verification:
  - `cd services/backend && pytest -q tests/test_tts_voice_registry.py tests/test_stream_ingester.py tests/test_session_manager.py tests/test_agent_runtime.py tests/test_state_controller.py`
  - `cd services/frontend && npm run build`

## 2026-06-26 — inbound builder save-path visibility fix + recovery deployment truth refresh

- Verified live recovery deployment facts from the `b3-32` VoiceOps VM without changing backend app code:
  - deploy checkout path: `/home/ubuntu/aether-nodes/VoiceOps`
  - local baseline branch on box: `deploy/b3-32-voiceops-baseline-2026-06-26`
  - verified baseline commit: `d52411cb3514012b2355bddde1573065a0eb7da8`
  - active compose: `docker-compose.recovery.yml`
  - frontend container runs `npm run dev`
  - backend container runs `uvicorn`
- Verified live number-routing truth during save-bug triage:
  - `+18127212341` was initially still mapped to `Carla - Skilled Trades & Services`
  - recent calls were reaching the route, but outcomes were mostly `failed_intake`
  - live traces reported `empty_transcript`, `silence_or_dead_air_turn`, and barge-in anomalies
- Applied direct recovery-DB configuration update to the already-mapped `+18127212341` agent row:
  - live agent now verified as `Mary's Beauty Spa - Medspa Demo`
  - runtime now verified as `grm2.6-plus` + `voxtream2_realtime` + `cj_clone_male`
  - updated agent id remains `de9c2ae7-fe68-4936-aea6-aa4ff4d84bdf`, so phone-number mapping did not need to change
- Updated inbound builder frontend in:
  - `services/frontend/app/inbound/page.js`
  - `services/frontend/lib/operator-builder.js`
- Added pre-submit JSON validation for inbound builder fields:
  - `required_fields`
  - `action_config`
  - `crm_mapping`
  - `fsm_config`
- Added field-level JSON error messages plus one-click JSON formatting helpers for the editable JSON sections.
- Added visible status messaging near the top of the page so operators can immediately see whether:
  - the workflow saved
  - the workflow saved but number mapping failed
  - the workflow saved with no inbound number assigned
- Clarified in code and docs that inbound workflow persistence and phone-number reassignment are separate writes.
- Verification:
  - `cd services/frontend && npm run build`
  - Result: passed
- Additional note:
  - `cd services/frontend && npm run lint` is currently stale because `next lint` fails under the current Next.js 16 setup before linting code.

## 2026-06-07 — fsm-build branch (FSM config activation + retry-skip fix)

- Activated the useful live subset of persisted inbound `fsm_config` in the Phase 3 State Controller/runtime path:
  - `silence_timeout_seconds`
  - `max_retries_per_field`
  - `frustration_escalation_enabled`
- Fixed a real FSM retry bug in `services/backend/app/services/state_controller/controller.py`:
  - exhausting per-field retries previously wrote an empty string and the field still remained "missing"
  - result: the controller could loop the same field indefinitely instead of actually skipping ahead
  - new behavior tracks skipped fields explicitly and emits a skip-ahead prompt to the next field
- Updated guardrail escalation behavior:
  - sensitive-language escalation in `services/backend/app/services/agent_runtime/runtime.py`
  - explicit `escalate.frustration` handling in the State Controller
  - both now respect `frustration_escalation_enabled=false`
- Added/updated tests:
  - `services/backend/tests/test_agent_runtime.py`
  - `services/backend/tests/test_state_controller.py`
- Verification:
  - `cd services/backend && pytest -q tests/test_agent_runtime.py tests/test_state_controller.py`
  - Result: `67 passed`

## 2026-04-09 — fsm-build branch (auth session contract: platform admin signal)

- Added distinct platform-admin signal to authenticated session response:
  - `/api/v1/auth/me` now returns `is_platform_admin: boolean`
- Source of truth:
  - new DB-backed user field `users.is_platform_admin` (not email-based, not env-flag-based)
- Implementation details:
  - model update: `services/backend/app/models/models.py` (`User.is_platform_admin`)
  - auth dependency update: `services/backend/app/api/deps.py` (`CurrentUser.is_platform_admin`)
  - auth schema update: `services/backend/app/schemas/auth.py` (`UserResponse.is_platform_admin`)
  - response mapping update: `services/backend/app/api/routes/auth.py` (`/auth/me`)
  - tenant/bootstrap owner creation explicitly sets `is_platform_admin=False`
    in `services/backend/app/api/routes/auth.py` and `services/backend/app/api/routes/tenants.py`
- Migration:
  - `services/backend/alembic/versions/20260409_0003_user_platform_admin_flag.py`
  - adds `users.is_platform_admin boolean not null default false`
  - marks the earliest existing user as `is_platform_admin=true` during upgrade
    (bootstrap-first internal admin path), while keeping all other users false
- Added tests:
  - `services/backend/tests/test_auth_me_platform_admin.py`
  - verifies `/auth/me` includes true/false platform admin signal
- Verification:
  - `pytest -q services/backend/tests/test_auth_me_platform_admin.py`
  - `pytest -q services/backend/tests/test_auth_change_password.py services/backend/tests/test_tenant_bootstrap.py`
  - Result: `11 passed`

## 2026-04-07 — fsm-build branch (platform admin tenant onboarding endpoint)

- Added platform-admin onboarding endpoint for portal client creation flow:
  - `POST /api/v1/admin/tenant-bootstrap`
- Purpose:
  - creates a new tenant + owner user in one request without requiring manual bootstrap payload shaping
  - intended for internal admin onboarding from the separate portal repo
- Implementation details:
  - new schemas in `services/backend/app/schemas/tenant.py`:
    - `TenantBootstrapRequest`
    - `TenantBootstrapResponse`
  - route in `services/backend/app/api/routes/tenants.py`
  - automatic slug normalization + collision handling (`name`, `name-2`, `name-3`, ...)
  - owner email normalized to lowercase
  - temporary password created internally (not returned)
  - returns a password reset token for first-login activation path
- Safety:
  - endpoint requires valid `X-Platform-Admin-Key`
  - no database migrations added
  - existing `/api/v1/auth/bootstrap` and login flow unchanged
- Added tests:
  - `services/backend/tests/test_tenant_bootstrap.py`
- Verification:
  - `pytest -q services/backend/tests/test_tenant_bootstrap.py`
  - `pytest -q services/backend/tests/test_auth_change_password.py`
  - Result: `9 passed`

## 2026-04-07 — fsm-build branch (full forgot/reset password flow, additive)

- Added forgot/reset password endpoints (login flow unchanged):
  - `POST /api/v1/auth/forgot-password`
  - `POST /api/v1/auth/reset-password`
- Implementation details:
  - new reset token primitives in `services/backend/app/core/security.py`
    - token scope: `password_reset`
    - token payload binds to user id, tenant id, email, and current password fingerprint
    - password update invalidates prior reset tokens automatically
  - new auth schemas in `services/backend/app/schemas/auth.py`
  - route logic + optional SMTP delivery in `services/backend/app/api/routes/auth.py`
  - optional server-to-server token handoff:
    - `forgot-password` returns `reset_token` when called with valid `X-Platform-Admin-Key`
    - or when `AUTH_PASSWORD_RESET_ALLOW_DEBUG_TOKEN_RESPONSE=true`
- Added config fields and env examples:
  - `services/backend/app/core/config.py`
  - `.env.example`
- Added tests:
  - `services/backend/tests/test_auth_change_password.py`
  - covers:
    - forgot-password token issuance (platform-admin path)
    - reset-password success
    - reset token replay rejection after password change
    - existing login/change-password regressions still passing
- Verification:
  - `pytest -q services/backend/tests/test_auth_change_password.py`
  - `pytest -q services/backend/tests/test_portal.py services/backend/tests/test_stream_ingester.py`
  - Result: `25 passed`

## 2026-04-07 — fsm-build branch (auth password-change endpoint, additive)

- Added authenticated self-service password change endpoint:
  - `POST /api/v1/auth/change-password`
- Implementation details:
  - route added in `services/backend/app/api/routes/auth.py`
  - new request/response schemas in `services/backend/app/schemas/auth.py`
  - validates current password before update
  - rejects no-op password reuse (`new_password == current_password`)
  - updates stored hash and commits transaction
- Added auth regression tests:
  - `services/backend/tests/test_auth_change_password.py`
  - covers:
    - successful password update path
    - invalid current password rejection (`401`)
    - same-password rejection (`400`)
    - existing login success path still functional
    - invalid login rejection (`401`)
- Test bootstrap cleanup:
  - removed temporary `email_validator` shim from `services/backend/tests/conftest.py` to avoid metadata/collection failures
- Verification:
  - `pytest -q services/backend/tests/test_auth_change_password.py`
  - `pytest -q services/backend/tests/test_portal.py`
  - `pytest -q services/backend/tests/test_stream_ingester.py`
  - Result: `23 passed`

## 2026-04-06 — fsm-build branch (first-turn extraction hardening pass)

- Tightened first-turn FSM field alignment and noisy-name capture behavior for inbound calls.
- Updated `services/backend/app/services/state_controller/controller.py`:
  - seed `last_prompted_field` from `build_opening_prompt()` on `call.incoming` so first caller turn extraction stays aligned to the active prompt.
- Updated `services/backend/app/services/agent_runtime/runtime.py`:
  - hardened `_extract_name()` to reject noise/service-trade tokens in short phrase captures (prevents values like `"And Electrical"` from being accepted as caller names).
- Added/updated tests:
  - `services/backend/tests/test_state_controller.py`
  - `services/backend/tests/test_agent_runtime.py`
- Verification:
  - `cd services/backend && pytest -q tests/test_state_controller.py tests/test_agent_runtime.py tests/test_fsm_consumers.py tests/test_stream_ingester.py tests/test_portal.py`
  - Result: `88 passed`

## 2026-04-06 — fsm-build branch (portal API foundation, additive only)

- Added minimal customer-portal API routes (backend only, no call-flow rewrites):
  - `GET /api/v1/portal/dashboard`
  - `GET /api/v1/portal/business-profile`
  - `GET /api/v1/portal/agent-mode`
  - `PUT /api/v1/portal/agent-mode`
  - `GET /api/v1/portal/audit-log`
- Implementation details:
  - new route module: `services/backend/app/api/routes/portal.py`
  - new response/request schemas: `services/backend/app/schemas/portal.py`
  - router registration in `services/backend/app/api/router.py`
- Safety constraints:
  - no DB migrations introduced
  - no Twilio webhook or call-loop behavior changed
  - agent-mode state is persisted via tenant-scoped audit events (`portal.agent_mode.updated`)
  - `effective_in_live_routing` is explicitly `false` until routing path integration is implemented
- Added tests:
  - `services/backend/tests/test_portal.py` (mode validation unit coverage)
- Verification:
  - `cd services/backend && pytest -q tests/test_portal.py tests/test_state_controller.py tests/test_agent_runtime.py tests/test_fsm_consumers.py tests/test_stream_ingester.py`
  - Result: `87 passed`

## 2026-04-06 — fsm-build branch (greeting overlap suppression pass)

- Continued S1 call-open polish to reduce step-on/recovery churn before first real caller utterance.
- Updated `services/backend/app/services/state_controller/controller.py`:
  - added greeting/listen-window timing telemetry (`answer_time`, greeting start/complete, first listen, first valid transcript)
  - empty/near-empty ASR finals are now discarded with immediate re-listen instead of speaking recovery prompts
  - added S1 greeting recovery hold window (`GREETING_RECOVERY_DELAY_SECONDS=20.0`) so early silence timeouts re-open listening before speaking
  - preserved listen-window anchoring across re-listens; clear anchor when emitting TTS or after first committed user input
- Updated `services/backend/tests/test_state_controller.py`:
  - listen-window anchor preservation test
  - S1 empty transcript discard + reopen-listen behavior assertion
  - S1 silence timeout behavior tests (reopen during greeting window, recover after window)
- Verification:
  - `cd services/backend && pytest -q tests/test_state_controller.py tests/test_agent_runtime.py tests/test_fsm_consumers.py tests/test_stream_ingester.py`
  - Result: `85 passed`

## 2026-03-30 — fsm-build branch (inbound human transfer settings V1)

- Added minimal inbound workflow `human_transfer` config support (persisted in `workflow_dsl.inbound_builder`):
  - `enabled`, `trigger_mode`, `keywords`, `destination_type`, `destination`, `label`,
    `confirmation_message`, `no_answer_fallback`, `ring_timeout_seconds`
- Updated inbound workflow editor UI:
  - new collapsible **Human Transfer Settings** section with defaults and full save/load support
  - frontend files:
    - `services/frontend/lib/operator-builder.js`
    - `services/frontend/app/inbound/page.js`
- Updated runtime contract support:
  - structured transfer action contract supported:
    - `{"action":"transfer_call","target":"<label>","reason":"<string>"}`
  - LLM system prompt now explicitly forbids outputting raw destination numbers/SIP/client identifiers
  - transfer target is label-based only; destination resolution stays backend-only
  - backend runtime file:
    - `services/backend/app/services/agent_runtime/runtime.py`
- Added Twilio transfer execution path and transfer TwiML endpoints:
  - session manager now executes transfer by updating active Twilio call URL
  - TwiML route resolves destination from workflow config and dials with configured timeout
  - transfer fallback route supports V1 `return_to_ai` reconnect behavior
  - backend files:
    - `services/backend/app/services/realtime/session_manager.py`
    - `services/backend/app/api/routes/webhooks.py`
- Added tests for transfer config/action handling:
  - `services/backend/tests/test_agent_runtime.py`
  - `services/backend/tests/test_session_manager.py`

## 2026-03-27 — fsm-build branch (0.9 near-100% polish pass)

- Investigated `logs/working-logs-0.9_1st_Near-100%.md` and fixed two remaining live-call polish issues:
  - empty ASR final transcripts in confirmation loop could repeatedly trigger the same retry line
  - noisy name phrase like `"Gibson and 812..."` could capture `"And"` as caller name
- Updated `services/backend/app/services/state_controller/controller.py`:
  - empty transcripts no longer reset silence/empty counters as if valid caller speech occurred
  - caller turn count now increments only on non-empty final transcripts
  - S6 confirmation loop now suppresses back-to-back duplicate yes/no retry prompts on repeated empty ASR finals
- Updated `services/backend/app/services/agent_runtime/runtime.py`:
  - added `and` to name-noise filtering to avoid bad trailing-token name capture
- Added tests:
  - `services/backend/tests/test_state_controller.py`
    - empty transcript counter/turn handling regression
    - S6 duplicate confirmation retry suppression
  - `services/backend/tests/test_agent_runtime.py`
    - trailing `and` + phone digits name extraction regression
- Verification:
  - `cd services/backend && pytest -q tests/test_state_controller.py tests/test_agent_runtime.py tests/test_tts_voice_registry.py`
  - Result: `55 passed`

## 2026-03-27 — fsm-build branch (0.8 confirmation/readback polish pass)

- Investigated `logs/working-logs-0.8.md` and fixed S6 confirmation-loop issues:
  - readback included non-required captured fields
  - confirmation listen timeout was too short for natural yes/no pauses
  - silence/unclear handling in S6 reused generic recovery and repeated full readback too aggressively
- Updated `services/backend/app/services/state_controller/controller.py`:
  - S6 readback now uses only `agent.required_fields` keys (ordered), instead of all `collected_fields`
  - added S6 confirmation listen timeout floor (`14s`)
  - added S6-specific yes/no retry prompt for silence and unclear transcripts
  - unclear S6 confirmations now use concise yes/no retry instead of re-reading full intake immediately
- Added tests in `services/backend/tests/test_state_controller.py`:
  - S6 silence timeout uses confirmation retry prompt
  - S6 readback excludes non-required fields
  - S6 listen-timeout floor enforcement
  - unclear confirmation path uses yes/no retry prompt
- Added operational note in `PROJECT_STATE.md`:
  - track VAD/background-noise sensitivity calibration for real-world phone environments

## 2026-03-27 — fsm-build branch (platform integration runbook added)

- Added platform control-plane integration runbook for VoiceOps user/tenant/key/billing orchestration:
  - `internal-docs/PLATFORM_API_INTEGRATION_RUNBOOK_2026-03-27.md`
- Runbook is anchored to current VoiceOps truth and explicitly keeps existing VoiceOps Postgres wiring unchanged.
- Includes:
  - current available provisioning/auth endpoints
  - control-plane vs execution-plane ownership split
  - phased rollout and failure handling strategy
  - security and idempotency requirements for cross-VM platform calls

## 2026-03-27 — fsm-build branch (Voxtream2 Studio registry voice source fix)

- Implemented Voxtream2 voice loading from the Voice Substrate Studio registry (cross-VM source of truth):
  - `services/backend/app/services/tts/voice_registry.py`
    - fetches from `{AETHER_VOICE_HTTP_BASE}/v1/tts/studio/voices`
    - sends `X-Tenant-Id: default`
    - filters to `runtime_target == voxtream2_realtime`
    - requires non-null `reference_audio_path`
    - maps registry entries to VoiceOps voice option shape
- Updated `/api/v1/agents/tts/voices` to merge static registry + Studio Voxtream2 voices:
  - `services/backend/app/api/routes/agents.py`
- Extended API schema to expose Voxtream2 reference audio metadata:
  - `services/backend/app/schemas/agent.py` (`reference_audio_path`)
- Removed Qwen/Voxtream2 compatibility bleed-through in frontend defaults:
  - `services/frontend/lib/operator-builder.js`
  - `services/frontend/app/agents/page.js`
  - Qwen preset voices no longer advertise `voxtream2_realtime` support
- Added/updated backend tests:
  - `services/backend/tests/test_tts_voice_registry.py`
    - runtime-target filtering
    - reference-audio required behavior
    - merge de-duplication
- Verification:
  - `cd services/backend && pytest -q tests/test_tts_voice_registry.py tests/test_agent_runtime.py tests/test_state_controller.py`
  - Result: `48 passed`

## 2026-03-26 — fsm-build branch (Voxtream2 option integration pass)

- Added `voxtream2_realtime` to backend TTS voice/model compatibility registry:
  - `services/backend/app/services/tts/voice_registry.py`
  - included in provider-backed Qwen/asset voice model compatibility set
- Added `voxtream2_realtime` to frontend TTS model dropdown options used by inbound/outbound builders:
  - `services/frontend/lib/operator-builder.js`
- Added `voxtream2_realtime` to agent editor TTS model dropdown and aligned duplicated voice compatibility model set:
  - `services/frontend/app/agents/page.js`
- Updated backend registry test expectations:
  - `services/backend/tests/test_tts_voice_registry.py`
- Verification:
  - `cd services/backend && pytest -q tests/test_tts_voice_registry.py tests/test_agent_runtime.py tests/test_state_controller.py`
  - Result: `46 passed`

## 2026-03-26 — fsm-build branch (0.7 readback/terminal-state fix pass)

- Investigated `logs/working-logs-0.7.md` and fixed three concrete issues:
  - late `asr.transcript` events were still being handled after transition to `S7`, causing extra recovery prompts after goodbye
  - readback in `S6` could speak callback numbers as large-magnitude numbers instead of digit-by-digit
  - `organization` behaved as implicitly required in intake flow, creating noisy captures and awkward readback content
- Updated `services/backend/app/services/state_controller/controller.py`:
  - ignore ASR transcripts in terminal states (`S7`, `Esc`)
  - guard `_handle_empty_transcript()` in terminal states
  - clear `last_prompted_field` when entering `S6` confirmation/readback
  - format callback numbers for readback as spaced digits (e.g. `8 1 2 3 6 3 2 4 2 4`)
- Updated `services/backend/app/services/agent_runtime/runtime.py`:
  - `missing_required_fields()` now treats organization/company fields as optional by default
  - can be re-enabled as required with `policy_config.runtime.require_organization=true`
- Added tests:
  - terminal-state transcript ignore
  - S6 readback callback digit formatting
  - optional-organization missing-field behavior + runtime override behavior
- Verification:
  - `cd services/backend && pytest -q tests/test_agent_runtime.py tests/test_state_controller.py tests/test_fsm_consumers.py tests/test_stream_ingester.py tests/test_stream_event_schemas.py`
  - Result: `108 passed`

## 2026-03-26 — fsm-build branch (0.6 first-turn overlap fix pass)

- Investigated `logs/working-logs-0.6.md` and found two first-turn issues:
  - quick empty ASR finals triggered immediate spoken recovery prompts (`"I didn't hear anything there."`), creating overlap pressure
  - prompted-field extraction was too broad and could capture unrelated required fields from noisy utterances
- Updated `services/backend/app/services/state_controller/controller.py`:
  - added `last_listen_started_at` and `empty_transcript_count` tracking
  - first quick empty transcript now silently re-opens `asr.start_listen` (no immediate TTS interruption)
  - subsequent empty transcripts use rotating field-aware recovery wording
  - added 12s listen floor for `name` capture turns
- Updated `services/backend/app/services/agent_runtime/runtime.py`:
  - when a `prompted_field` is active, extraction now targets only that field
  - improved noisy name fallback parsing for short snippets (e.g., `"Why, Mary,"`) while avoiding long non-name utterances
- Added tests:
  - `services/backend/tests/test_state_controller.py`:
    - quick empty transcript restarts listen silently
  - `services/backend/tests/test_agent_runtime.py`:
    - prompted-field-only extraction behavior
    - noisy phrase name extraction
- Verification:
  - `cd services/backend && pytest -q tests/test_agent_runtime.py tests/test_state_controller.py tests/test_fsm_consumers.py tests/test_stream_ingester.py tests/test_stream_event_schemas.py`
  - Result: `104 passed`

## 2026-03-26 — fsm-build branch (silence/talk-over fix pass)

- Investigated `logs/working-logs-0.5.md` and confirmed false silence recovery prompts were firing while caller speech was still in-flight to final ASR transcript.
- Added ASR partial heartbeat publishing in `services/backend/app/services/asr/consumer.py`:
  - forwards `partial_transcript` events as `asr.transcript` with `is_final=false`
  - deduplicates repeated partial text
  - publishes a final `asr.transcript` whenever speech occurred (even with empty final text)
- Updated `services/backend/app/services/state_controller/controller.py`:
  - non-final `asr.transcript` now extends `silence_deadline` instead of triggering response generation
  - added dynamic listen timeout floors:
    - greeting listen floor: `12s`
    - phone/callback capture listen floor: `16s`
  - replaced repeated fixed connection-check phrase with rotating field-aware/general recovery prompts
  - added `prompted_field` to `state_ctrl.asr.start_listen` logs
- Updated `services/backend/app/services/streams/event_schemas.py` docstring for `ASRTranscriptPayload` to reflect partial+final semantics.
- Added/updated tests:
  - `services/backend/tests/test_state_controller.py` now verifies partial transcript behavior (deadline extension, no premature TTS)
- Verification:
  - `cd services/backend && pytest -q tests/test_state_controller.py tests/test_fsm_consumers.py tests/test_stream_ingester.py tests/test_stream_event_schemas.py`
  - Result: `87 passed`

## 2026-03-26 — fsm-build branch (live call polish pass)

- Established new known-good baseline from `logs/working-logs-huge-win-0.4.md` (call id `0d03c5d4-bc7a-4b84-9e58-f56fede68fb2`):
  - voice/model stayed consistent through full TTS path (`bf_isabella` + `kokoro_realtime`)
  - FSM call loop remained stable with successful multi-turn intake
- Tuned silence timing to reduce premature "trouble hearing you" recovery prompts:
  - `services/backend/app/services/state_controller/controller.py`
    - `silence_timeout_seconds` changed from `8.0` to `10.0`
  - `services/backend/app/services/realtime/stream_ingester.py`
    - `END_OF_TURN_SILENCE_FRAMES` changed from `30` to `40`
  - `services/backend/app/services/realtime/session_manager.py`
    - `END_OF_TURN_SILENCE_FRAMES` changed from `30` to `40` (kept legacy path aligned)
- Tightened live-phone LLM speaking style constraints to reduce filler/chuckle artifacts and trailing fragments:
  - `services/backend/app/services/agent_runtime/runtime.py` (`build_llm_system_prompt`)
  - Added explicit instructions: no chuckles/stage directions/sound effects, avoid filler words, avoid trailing ellipses, keep responses short.
- Verification:
  - `cd services/backend && pytest -q tests/test_state_controller.py tests/test_fsm_consumers.py tests/test_stream_ingester.py`
  - Result: `48 passed`

## 2026-03-25 — fsm-build branch (Phase 3 consumers complete)

### Phase 3 — FSM Pipeline: All Consumers Built

All five components of the FSM pipeline are now implemented, tested (84 tests pass), and wired into `stream_ingester.handle_ws()`:

| Component | File | Tests |
|---|---|---|
| StreamIngester | `app/services/realtime/stream_ingester.py` | `test_stream_ingester.py` (14) |
| StreamPublisher | `app/services/streams/publisher.py` | `test_stream_event_schemas.py` (38) |
| StateController | `app/services/state_controller/controller.py` | `test_state_controller.py` (23) |
| ASR Consumer | `app/services/asr/consumer.py` | (smoke: covered by ingester tests) |
| TTS Consumer | `app/services/tts/consumer.py` | (smoke: covered by ingester tests) |
| LLM Consumer | `app/services/llm/consumer.py` | `test_fsm_consumers.py` (4) |
| Audit Consumer | `app/services/audit/consumer.py` | `test_fsm_consumers.py` (5) |

**Hard-listen guarantee is enforced in StateController:**
- `_emit_tts()` is a no-op if `asr_listening=True` (logged as warning)
- `_emit_asr_start_listen()` is a no-op if `pending_tts_id` is set
- Both guards are unit-tested in `test_state_controller.py`

**Phase 3 LLM path (inline):**
The State Controller calls `AgentRuntime.generate_response()` inline and publishes `llm.extract`+`llm.extracted` to the stream for observability. The LLM Consumer is written but NOT wired into `handle_ws()` in Phase 3. Phase 4: start LLM Consumer task + remove inline path from State Controller.

**Each call starts 5 asyncio tasks:**
1. `tts_drain` — forwards μ-law audio from `tts_audio_queue` to Twilio media events
2. `state_ctrl` — FSM driver (S0→S7), emits `tts.speak` / `asr.start_listen`
3. `asr_consumer` — listens for `asr.start_listen`, drains audio queue, publishes `asr.transcript`
4. `tts_consumer` — listens for `tts.speak`, streams TTS audio, publishes `tts.complete`
5. `audit_consumer` — reads all events, writes per-call `fsm_events.jsonl`

**Feature flag still off by default:** `FSM_PIPELINE_ENABLED=false` — live calls are unaffected.

---

## 2026-03-25 — fsm-build branch

### Phase 2 Addendum (pre-Phase-3 gates)

**Addition 1 — Config & secrets hygiene (BLOCKING gate, now clear):**
- Refactored `services/backend/app/core/config.py` into a fully grouped `Settings` class with logical sections: App, Database, Redis, Twilio, Aether Voice, LLM, Telemetry.
- All fields have sensible defaults. `extra='ignore'` set — unknown `.env` vars are silently dropped.
- Added new FSM Redis settings: `redis_call_stream_prefix`, `redis_call_state_hash_prefix`, `redis_stream_maxlen`, and five consumer group name fields (`redis_cg_state_controller`, `redis_cg_asr`, `redis_cg_tts`, `redis_cg_llm`, `redis_cg_audit`).
- Added `Settings.log_resolved()` — logs all resolved settings at startup with secret redaction (first 4 chars + `****`). Called from `app.on_event('startup')` in `main.py`.
- Added `Settings.per_call_stream_key(session_id)` and `per_call_state_key(session_id)` helpers for FSM key construction.
- Confirmed zero `os.getenv()` / `os.environ` calls outside `config.py`.
- Rewrote `.env.example` — fully grouped, commented, includes all new FSM vars.

**Addition 2 — FSM Configurator stub (non-blocking, done):**
- Added `fsm_config` field to the Inbound Workflow Builder form (frontend).
- `buildAgentPayload` now persists `fsm_config` inside `workflow_dsl.inbound_builder.fsm_config`.
- `formFromAgent` reads it back on edit load.
- Added collapsed "Call flow configuration (advanced)" section in the builder UI — shows `fsm_config` as a read-only code block when expanded.
- Added `// FUTURE` comment block pointing to `FSM/voiceops_inbound_state_machine.svg`.

**Addition 3 — Stream event schema contract (BLOCKING gate, now clear):**
- Created `services/backend/app/services/streams/` package.
- Created `event_schemas.py` — Pydantic models for all 15 FSM event types on `voice:calls:{session_id}`.
- Includes: `FSMEventBase` envelope, typed payload models per event, typed event wrappers with `Literal` discriminators, `AnyFSMEvent` union for deserialization dispatch, `make_event()` factory helper.
- Exports `ALL_EVENT_TYPES`, `STATE_CONTROLLER_COMMANDS`, `STATE_CONTROLLER_TRIGGERS` frozensets for consumer filtering.

## 2026-03-17
- Fixed Twilio `connected` media stream event handling in the live WebSocket dispatcher.
- Fixed Twilio `mark` media stream event handling in the live WebSocket dispatcher.
- Hardened the WebSocket event loop so unknown Twilio media stream events log an anomaly and `continue` instead of breaking the call loop.
- Added `enable_thinking: false` for `omnicoder` and `qwen3.5*` telephony calls via `extra_body.chat_template_kwargs`.
- Expanded `strip_control_markup()` so TTS sanitization removes reserved tokens, thinking tags, tool-call markup, and code fences.
- Applied output sanitization to both the live TTS path and transcript persistence.
- Recorded the first successful end-to-end live call on `2026-03-17`:
  - 140 seconds total duration
  - 6 caller turns
  - 7 agent turns
  - all required fields captured
  - zero anomalies

## 2026-03-14
- Integrated VoiceOps with the external Aether Voice realtime gateway contract for turn-based live telephony.
- Replaced placeholder ASR/TTS plumbing with session-based realtime ASR and Kokoro realtime TTS clients.
- Added Twilio media transcoding path between `mulaw/8k` telephony audio and gateway `pcm_s16le/16k` ASR + `wav/24k` TTS.
- Added VAD-based caller turn detection and per-turn ASR/TTS orchestration in the telephony session manager.
- Added output sanitization for model control markup before sending text to TTS.
- Added new `AETHER_VOICE_*` configuration surface for the public gateway contract.
- Preserved loopback-only host exposure model expected by the existing NGINX reverse-proxy topology.
- Recorded the first successful live end-to-end phone call checkpoint and created `CALL_POLISH_LOG.md` to track post-plumbing polish work.
- Added first-pass live-call polish for required-field intake:
  - field-aware opening prompt
  - retry-limited name/phone/issue capture
  - structured per-call summaries and dispositions
  - compact debug summary exposure in the calls UI
  - dedicated `POLISH_TODO.md` for live-call tuning only

## 2026-03-05
- Built initial end-to-end `Aether VoiceOps` MVP stack (FastAPI + Next.js + Postgres/Redis + Prometheus).
- Implemented required API surface, Twilio webhooks, realtime websocket endpoint, and tenant-scoped RBAC/auth.
- Added SQLAlchemy models + Alembic initial migration (`20260305_0001`).
- Added forms/workflow, analytics summary, audit event tracking, and telephony abstraction.
- Added deployment docs/runbook and architecture blueprint docs.
- Added external-infra compose mode and bundled compose mode.
- Added manual DB bootstrap SQL scripts for deterministic superuser-driven setup:
  - `infra/sql/00_recreate_voiceops_db.sql`
  - `infra/sql/01_voiceops_schema_and_stamp.sql`
- Removed automatic DB migration execution from startup command in compose files (backend now starts app directly).
- Fixed bootstrap password failure mode by changing password hashing scheme to `pbkdf2_sha256` and validating auth payload constraints.
- Added blue/green deployment assets:
  - `docker-compose.blue.yml`
  - `docker-compose.green.yml`
  - `docs/blue-green-runbook.md`
  - `infra/nginx/voiceops-upstream-*.conf`
  - `infra/scripts/switch_voiceops_color.sh`
