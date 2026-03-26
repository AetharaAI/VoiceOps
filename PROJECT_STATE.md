# Project State (Persistent Context)

## Current Status
- VoiceOps is live behind NGINX at `voice.aetherpro.us`.
- Backend and frontend are healthy.
- API docs reachable at `/docs`.
- Manual DB provisioning is in place and considered canonical for current deployment.
- Realtime voice loop is now connected to the external Aether Voice gateway contract.
- Live call pipeline is functional end-to-end as of `2026-03-17`.
- First successful polished live E2E call completed on `2026-03-17`:
  - 140 seconds total duration
  - 6 caller turns
  - 7 agent turns
  - all required fields captured
  - zero anomalies
- The system is now in `functional-with-polish-remaining` state rather than `plumbing incomplete`.
- New known-good FSM call baseline captured on `2026-03-26` in `logs/working-logs-huge-win-0.4.md`:
  - Voice selection remained consistent end-to-end (`bf_isabella`, `kokoro_realtime`)
  - Conversation reached intelligent multi-turn behavior with field capture
  - Remaining polish issue observed: premature silence recovery prompts and occasional choppy truncation
- Follow-up call trace `logs/working-logs-0.5.md` showed talk-over due to silence timeout firing before final ASR transcript arrival during longer caller utterances.
- Current mitigation (implemented on `2026-03-26`):
  - ASR partial transcripts are now emitted into FSM stream (`asr.transcript` with `is_final=false`)
  - State Controller extends listen deadline on non-final transcripts instead of responding
  - listen window is now dynamic (`12s` greeting floor, `16s` phone/callback floor)
  - silence recovery prompts now rotate and prefer field-aware wording instead of repeating a fixed phrase

## Deployment Mode (Current)
- Runtime: Docker Compose (`docker-compose.yml`) on CPU gateway node.
- External services: PostgreSQL + Valkey run in separate containers on same host/network.
- External network: `aether_net`.
- Host exposure model:
  - services bind on `127.0.0.1` host ports only
  - NGINX is the only public ingress
  - container processes still listen on `0.0.0.0` internally so Docker can forward traffic correctly

## Database Policy
- Canonical setup path is manual SQL migration via superuser scripts:
  - `infra/sql/00_recreate_voiceops_db.sql`
  - `infra/sql/01_voiceops_schema_and_stamp.sql`
- Startup must NOT run migrations automatically in current production mode.
- `alembic_version` is stamped to `20260305_0001` when using manual SQL script.

## Security/Secrets Notes
- `PLATFORM_ADMIN_KEY` is used as `X-Platform-Admin-Key` header.
- `TENANT_SECRET_KEY` is platform encryption seed, not tenant slug.
- Rotate exposed tokens/keys and never commit live secrets.

## LLM/Model Routing
- OpenAI-compatible gateways supported.
- Required env for that mode:
  - `LLM_PROVIDER=openai`
  - `LLM_ENDPOINT=<chat completions endpoint>`
  - `LLM_API_KEY=<key>`
  - `LLM_MODEL=<model-name>`
- Current reported operator state:
  - primary live LLM is `omnicoder`
  - `minicpm-v` remains available and is planned as the secondary stream consumer for structured field extraction
  - `qwen3.5*` and `omnicoder` telephony calls must send `enable_thinking: false` via `extra_body.chat_template_kwargs`

## Known Current Operational Constraints
- Frontend currently runs `next dev` in container for speed of iteration; production hardening should move this to build/start mode.
- Manual DB migration path is authoritative until migration pipeline is reintroduced safely.
- Call flow is functional but still needs polish:
  - ASR silence detection and retry timing still need refinement under real PSTN pauses
  - outbound field-collection flow still needs cleanup against real-call behavior
  - dual-model stream consumer integration is not implemented yet
- Reverse proxy assumptions matter:
  - NGINX expects backend/frontend on loopback host bindings
  - removing host loopback bindings breaks current proxy topology
- Twilio media stream handling has been hardened:
  - `connected` and `mark` are explicit passthrough events
  - unknown Twilio stream events must be logged and ignored, never treated as fatal

## Infrastructure Status
- Valkey streams are connected and publishing structured call/transcript events.
- Postgres is stable under the manual bootstrap path and remains the canonical persistence layer.
- Prometheus scraping is active for backend metrics.

## Active Branch: fsm-build

Phase 3 (FSM Pipeline) is **COMPLETE** on the `fsm-build` branch. All 84 tests pass. Feature flag `FSM_PIPELINE_ENABLED=false` keeps live calls unaffected. Main is not touched.

### Phase 3 build order — ALL COMPLETE:
1. `voice:calls:{session_id}` stream schema — **DONE** (`services/streams/event_schemas.py`, 38 tests)
2. Stream Ingester — refactor to thin event emitter + 5-task startup — **DONE** (`services/realtime/stream_ingester.py`, 14 tests)
3. State Controller — FSM S0→S7, hard-listen guarantee — **DONE** (`services/state_controller/controller.py`, 23 tests)
4. ASR Consumer — event-driven ASRClient wrapper — **DONE** (`services/asr/consumer.py`)
5. TTS Consumer — event-driven TTSClient wrapper + barge-in — **DONE** (`services/tts/consumer.py`)
6. LLM Consumer — Phase 3 stub (NOT wired; State Controller calls AgentRuntime inline) — **DONE** (`services/llm/consumer.py`)
7. Audit Consumer — per-call JSONL event log — **DONE** (`services/audit/consumer.py`)
8. Inbound Workflow Builder — lane config, FSM config stub — **DONE** (visual editor deferred)
9. Migration phases A→E (shadow → full cutover) — **PENDING**

### Phase 4 (next):
- Wire LLM Consumer task into `handle_ws()`; remove inline `generate_response()` from State Controller
- Add `pending_transcript` field to `CallFSMState` so State Controller awaits `llm.extracted` before emitting TTS
- Migration phases A→E: shadow mode (dual-write) → metric gate → cutover

### Immediate Next Priorities
1. Enable `FSM_PIPELINE_ENABLED=true` in staging and run shadow mode (A→B).
2. Validate `2026-03-26` timing tune in live calls:
   - `silence_timeout_seconds` increased `8.0 -> 10.0`
   - end-of-turn silence threshold increased `30 -> 40` frames in both FSM + legacy paths
   - live LLM phone prompt tightened to reduce filler/chuckle-like outputs and trailing fragments
   - partial-transcript heartbeat and dynamic listen timeout behavior validated against long phone-number capture turns
3. Wire LLM Consumer into `handle_ws()` (Phase 4 LLM decoupling).
4. Add end-to-end call smoke-test automation and transcript validation.
5. Move frontend from `next dev` container to production build/start path.
