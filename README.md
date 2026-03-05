# Aether VoiceOps

Multi-tenant, self-hosted voice-agent platform designed as a GoHighLevel-class competitor foundation.

## Repository Layout
```text
.
├── services
│   ├── backend        # FastAPI, SQLAlchemy, Alembic, realtime orchestration
│   └── frontend       # Next.js control plane
├── infra
│   └── prometheus     # Metrics scrape config
├── docs
│   ├── runbook.md
│   └── voice-agent-blueprint.md
├── docker-compose.yml
└── .env.example
```

## Core Features Implemented
- Inbound + outbound call APIs and telephony webhooks
- Realtime websocket media endpoint with barge-in cancellation behavior
- Multi-tenant auth/RBAC and tenant-scoped data model
- Agent builder + configurable required fields/tools/workflow
- Forms builder and forms-to-call workflow trigger
- Call logs + transcript segments + analytics summary
- Audit trail and encrypted tenant integration secrets schema
- Structured logs + Prometheus metrics

## Quick Start
```bash
cp .env.example .env
docker compose up --build
```

- API docs: http://localhost:8000/docs
- UI: http://localhost:3000

## Demo Path
1. Bootstrap tenant from `/login` (requires `PLATFORM_ADMIN_KEY`).
2. Create an agent from `/agents`.
3. Add phone number from `/dashboard`.
4. Create and submit form from `/forms`.
5. Inspect calls/transcripts from `/calls`.
6. Review KPI summary from `/analytics`.

## Notes
- Telephony provider interface is swappable (`services/backend/app/services/telephony/providers.py`).
- ASR/TTS endpoints are externalized via environment variables.
- Current runtime targets Docker Compose; service boundaries are prepared for K8s migration.
