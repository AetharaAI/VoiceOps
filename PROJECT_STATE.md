# Project State (Persistent Context)

## Current Status
- VoiceOps is live behind NGINX at `voice.aetherpro.us`.
- Backend and frontend are healthy.
- API docs reachable at `/docs`.
- Manual DB provisioning is in place and considered canonical for current deployment.
- Realtime voice loop is now connected to the external Aether Voice gateway contract.
- First successful live phone test completed on `2026-03-14`:
  - outbound call placed from VoiceOps
  - Twilio leg connected
  - agent answered with live voice
  - caller speech was captured and agent attempted field intake
- The system is now in `working-but-needs-polish` state rather than `plumbing incomplete`.

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
  - primary live LLM currently set to `minicpm-v`
  - alternate available model is `qwen3.5-9b`
  - broader dual-model / Redis Streams idea is deferred until call polish stabilizes

## Known Current Operational Constraints
- Frontend currently runs `next dev` in container for speed of iteration; production hardening should move this to build/start mode.
- Manual DB migration path is authoritative until migration pipeline is reintroduced safely.
- Call flow is functional but not polished:
  - first-turn behavior can pause awkwardly
  - ASR misses / retries can cause repeated name prompts
  - greeting is still backend-driven rather than fully script-driven
  - barge-in / turn timing needs tuning against real phone audio
- Reverse proxy assumptions matter:
  - NGINX expects backend/frontend on loopback host bindings
  - removing host loopback bindings breaks current proxy topology

## Immediate Next Priorities
1. Stabilize live call polish using real call traces from `CALL_POLISH_LOG.md`.
2. Improve first-turn ASR capture, retry behavior, and required-field collection prompts.
3. Move greeting/opening behavior into configurable agent script or dedicated opening prompt.
4. Add end-to-end call smoke test automation and transcript validation.
5. Revisit dual-model Redis Streams orchestration only after single-agent call flow is reliable.
