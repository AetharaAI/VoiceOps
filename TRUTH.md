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
- Verified live mapped demo/business number: `+18127212341`
- Verified mapped live agent on deploy VM at inspection time: `Carla - Skilled Trades & Services`

## Save-Path Truth
- Inbound workflow save is not a single operation.
- The builder performs:
  1. agent create/update
  2. phone-number reassignment
- A workflow can save while number remapping fails.
- Before the `2026-06-26` local frontend fix, malformed JSON in the inbound builder could feel like a dead save because the page surfaced failure poorly.
- Deployment inspection on `2026-06-26` showed the live mapped agent for `+18127212341` did not reflect the newly attempted demo workflow save.

## Known Live Demo Gaps
- Recent real calls to `+18127212341` were reaching the correct route but outcomes were mostly `failed_intake`, with one `partial_intake`.
- Recent live traces reported:
  - `empty_transcript`
  - `silence_or_dead_air_turn`
  - barge-in / talk-over anomalies
- These are runtime polish issues after routing, not evidence that Twilio ingress is broken.

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
