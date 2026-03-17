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
