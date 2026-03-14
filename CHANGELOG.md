# Changelog

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
