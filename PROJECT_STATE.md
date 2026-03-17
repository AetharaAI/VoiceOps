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
  - ASR silence detection and retry tuning still need refinement
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

## Immediate Next Priorities
1. Tune ASR silence handling, retry prompts, and turn timing using live call traces from `CALL_POLISH_LOG.md`.
2. Improve outbound call field-collection flow and first-turn reliability.
3. Add end-to-end call smoke-test automation and transcript validation.
4. Integrate the dual-model stream consumer path with `minicpm-v` on top of existing Valkey streams.
5. Move the frontend from `next dev` container runtime to a production build/start path when polish stabilizes.
