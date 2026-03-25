# Aether VoiceOps

- Project: `Aether VoiceOps` at `voice.aetherpro.us`
- Architecture: Next.js 16 frontend, FastAPI backend, Postgres multi-tenant persistence, Valkey streams, Prometheus metrics, all deployed with Docker Compose on OVHcloud `C3-32`
- Voice pipeline: Twilio WebSocket -> ASR at `asr.aetherpro.us` -> LLM via `api.aetherpro.tech`/LiteLLM (`omnicoder` and `minicpm-v`) -> TTS at `asr.aetherpro.us` -> Twilio media stream

## Key Files
- `services/backend/app/services/realtime/session_manager.py`: live call loop, Twilio media stream dispatcher, ASR/LLM/TTS orchestration
- `services/backend/app/services/agent_runtime/runtime.py`: agent runtime, LLM routing, model overrides
- `services/backend/app/services/realtime/audio.py`: audio helpers and `strip_control_markup()` sanitizer
- `services/backend/app/api/routes/webhooks.py`: Twilio inbound, outbound, fallback, and status webhook handling

## Critical Rules
- Never touch Postgres migrations, bootstrap SQL, or database provisioning paths without explicit approval.
- All Twilio media stream events must be handled or safely passed through. Unknown events must never kill the call loop.
- `omnicoder` and `qwen3.5*` telephony calls require `enable_thinking: false` via `extra_body.chat_template_kwargs`.
- Any text that can reach TTS must be sanitized through `strip_control_markup()`.

## Dual-Model Direction
- `omnicoder`: primary live conversation model for the phone call
- `minicpm-v`: planned stream consumer for structured field population and secondary extraction
- Valkey/Redis Streams are the event backbone for that planned split-runtime architecture

## FSM Build (branch: fsm-build — Phase 3 COMPLETE)
- All 5 FSM pipeline consumers are built and tested (84 tests pass).
- Each call gets a per-call stream: `voice:calls:{session_id}`
- Event schema contract: `services/backend/app/services/streams/event_schemas.py`
- State Controller is the only service that may emit `tts.speak` and `asr.start_listen` — hard-listen guarantee.
- Pipeline components:
  - `services/streams/event_schemas.py` — 15 typed event schemas (Pydantic)
  - `services/realtime/stream_ingester.py` — StreamIngester: VAD → 5 asyncio tasks per call
  - `services/state_controller/controller.py` — FSM S0→S7, hard-listen, inline AgentRuntime (Phase 3)
  - `services/asr/consumer.py` — ASRConsumer: listens for `asr.start_listen`, drains audio, publishes `asr.transcript`
  - `services/tts/consumer.py` — TTSConsumer: listens for `tts.speak`, streams TTS, publishes `tts.complete`
  - `services/llm/consumer.py` — LLMConsumer: Phase 3 stub only (NOT wired into handle_ws yet)
  - `services/audit/consumer.py` — AuditConsumer: writes `{call_log_root}/{call_id}/fsm_events.jsonl`
- Feature flag `FSM_PIPELINE_ENABLED` (default: `false`) — live calls unaffected until shadow mode enables it.
- FSM docs and diagrams: `FSM/` directory (audit, transition plan, state machine SVG, architecture SVG)
- Do NOT merge `fsm-build` to `main` until migration phase D (single monitored call) passes.
- Phase 4 next: wire LLMConsumer task, decouple inline LLM from State Controller.
