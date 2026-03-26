# Changelog

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
