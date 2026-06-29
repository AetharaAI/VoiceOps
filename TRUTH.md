# TRUTH.md

## Identity
- Project: `VOICE-AGENTS` / VoiceOps
- Purpose: multi-tenant telephony control plane for inbound/outbound AI voice agents
- Public UI: `https://voice.aetherpro.us`
- Runtime pair: Next.js frontend + FastAPI backend

## Repo And Deployment Truth
- Workstation repo root: `/home/cory/Documents/VOICE-AGENTS`
- Verified live deployment checkout: `/home/ubuntu/aether-nodes/VoiceOps`
- Verified live deployment baseline branch on `b3-32`: `deploy/b3-32-voiceops-baseline-2026-06-26`
- Verified baseline commit on deployment VM: `d52411cb3514012b2355bddde1573065a0eb7da8`
- Verified active compose on deployment VM: `/home/ubuntu/aether-nodes/VoiceOps/docker-compose.recovery.yml`

## Runtime Truth
- Frontend container: `voiceops-frontend-recovery`
- Backend container: `voiceops-backend-recovery`
- Frontend runs `npm run dev` behind nginx on the recovery deployment
- Backend runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Loopback exposure on deploy VM:
  - frontend: `127.0.0.1:3102`
  - backend: `127.0.0.1:8102`
- Public ingress is nginx via `/etc/nginx/sites-enabled/voiceops-recovery.conf`

## Live Routing Truth
- Twilio public paths intentionally remain open:
  - `/api/v1/webhooks/telephony/`
  - `/api/v1/ws/telephony/`
- Public app/admin/API exposure was hardened on the deploy VM on `2026-06-26`
- Restricted app/admin/API ingress in `voiceops-recovery.conf` allows Tailnet `100.64.0.0/10` plus rotating operator public IPs; as of `2026-06-29` the allowlist holds `73.145.240.8`, `73.145.242.40`, `73.145.241.211` (Xfinity rotates these — Tailnet access via the node tailnet IP `100.92.18.20` is the rotation-proof path)
- Verified live mapped demo/business number: `+18127212341`
- Verified mapped live agent on deploy VM before demo rewrite: `Carla - Skilled Trades & Services`
- Verified live mapped agent after direct recovery-DB update on `2026-06-26`: `Mary's Beauty Spa - Medspa Demo`
- Verified live runtime on `+18127212341` now points to:
  - model: `grm2.6-plus`
  - TTS lane: `voxtream2_realtime`
  - voice: `cj_clone_male`

## Save-Path Truth
- Inbound workflow save is not a single operation.
- The builder performs:
  1. agent create/update
  2. phone-number reassignment
- A workflow can save while number remapping fails.
- Before the `2026-06-26` local frontend fix, malformed JSON in the inbound builder could feel like a dead save because the page surfaced failure poorly.
- Deployment inspection on `2026-06-26` initially showed the live mapped agent for `+18127212341` did not reflect the newly attempted demo workflow save.
- Direct recovery-DB remediation was then applied to the already-mapped agent row so the live `721` line now carries the Mary's Beauty Spa demo workflow without requiring manual UI re-entry.

## Known Live Demo Gaps
- Recent real calls to `+18127212341` were reaching the correct route but outcomes were mostly `failed_intake`, with one `partial_intake`.
- Recent live traces reported:
  - `empty_transcript`
  - `silence_or_dead_air_turn`
  - barge-in / talk-over anomalies
- These are runtime polish issues after routing, not evidence that Twilio ingress is broken.

## Observed Root Cause For Mary's Demo Line
- Verified on `2026-06-26`: the step-on regression on `+18127212341` is not primarily a stale route, stale DB mapping, or broken save-cache path.
- The live recovery DB is updating and the mapped agent row is being read by the runtime.
- The strongest observed change was a lane switch on the same mapped agent:
  - earlier better-behaving sample: `kokoro_realtime` + `bf_emma`
  - later degraded sample: `voxtream2_realtime` + clone/studio voice
- Live backend telemetry showed:
  - Kokoro greeting first audio around `~449ms`
  - Voxtream2 greeting first audio around `~5036ms`
- That added startup latency creates dead air, late interrupt handling, and retry churn that feels like the agent is stepping on the caller.
- Live telephony baseline remains `kokoro_realtime` until Voxtream2 is re-qualified for interruptible PSTN calls.

## Runtime Path Truth
- Verified live `b3-32` env on `2026-06-26`: `FSM_PIPELINE_ENABLED=false`
- Public Twilio media on the recovery deployment is still using the legacy `session_manager` path, not the Phase 3 FSM pipeline.
- Current Mary/Syndicate barge-in difference is therefore not explained by one number being on the new FSM while the other is not.

## Local Fix Verified On Workstation
- Added inbound JSON validation before submit for:
  - `required_fields`
  - `action_config`
  - `crm_mapping`
  - `fsm_config`
- Added visible status card near top of inbound builder.
- Added explicit distinction between:
  - workflow saved
  - workflow saved but number mapping failed
  - workflow saved with no number assigned
- Local verification:
  - `npm run build` in `services/frontend` passed on `2026-06-26`
- Local lint command is currently stale:
  - `npm run lint` invokes `next lint`, which fails under the current Next.js 16 setup before linting code.
