# Changelog

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
