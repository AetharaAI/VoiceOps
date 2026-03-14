# Project State (Persistent Context)

## Current Status
- VoiceOps is live behind NGINX at `voice.aetherpro.us`.
- Backend and frontend are healthy.
- API docs reachable at `/docs`.
- Manual DB provisioning is in place and considered canonical for current deployment.

## Deployment Mode (Current)
- Runtime: Docker Compose (`docker-compose.yml`) on CPU gateway node.
- External services: PostgreSQL + Valkey run in separate containers on same host/network.
- External network: `aether_net`.

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

## Known Current Operational Constraints
- Frontend currently runs `next dev` in container for speed of iteration; production hardening should move this to build/start mode.
- Manual DB migration path is authoritative until migration pipeline is reintroduced safely.

## Immediate Next Priorities
1. Blue/green rollout process for zero-downtime deploys.
2. UI polish + tenant onboarding UX hardening.
3. End-to-end call smoke test automation.
4. Secret rotation and backup/restore runbooks.
5. SLOs + alerts (latency/error rate/call success).
