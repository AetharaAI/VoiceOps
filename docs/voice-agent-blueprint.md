# Aether VoiceOps Blueprint

## High-Level Diagram
```text
PSTN <-> Twilio Voice <-> telephony-gateway (webhooks/ws)
                               |
                               v
                        realtime-orchestrator
                   (session state + barge-in + VAD)
                        |       |         |
                        |       |         +--> tts-client -> Kokoro/Chatterbox
                        |       +------------> asr-client -> Whisper v3 endpoint
                        +--------------------> agent-runtime -> LLM router + tools
                                              |
                                              +--> workflow-engine (forms/call flows)

UI (Next.js) <-> FastAPI API <-> PostgreSQL (SoT)
                        |
                        +-> Redis/Valkey (session cache, rate limit)
                        +-> Metrics/Logs/Traces
```

## Module Specs
- `telephony-gateway`
  - Twilio webhook ingestion for inbound and status callbacks.
  - Outbound call initiation through provider abstraction.
  - WebSocket media bridge endpoint.
- `realtime-orchestrator`
  - Voice session state machine and jitter/micro-batch handling.
  - Barge-in: cancels active TTS task when caller speech detected.
  - Transcript persistence with final segments.
- `asr-client`
  - HTTP chunk transcription with micro-batching fallback.
  - Emits text + confidence when available.
- `tts-client`
  - Chunked streaming output and fallback packet generation.
  - Interrupt-compatible via task cancellation.
- `agent-runtime`
  - Per-agent persona/script/policy prompt context.
  - Guardrails: required field collection, escalation keyword checks.
  - Tool intent output for booking/CRM actions.
- `workflow-engine`
  - Declarative DSL storage and execution for form submit + post-call actions.
- `persistence`
  - SQLAlchemy models with tenant scoping and Alembic migration.
- `observability`
  - JSON logs, Prometheus metrics, correlation id middleware.

## Database Tables
- `tenants`, `users`
- `agents`, `phone_numbers`, `business_hours`, `routing_rules`
- `calls`, `transcript_segments`, `recordings`
- `forms`, `form_submissions`
- `integration_secrets`, `audit_events`, `kpi_events`

## API Endpoints
- `POST /api/v1/tenants`
- `POST /api/v1/agents`
- `PUT /api/v1/agents/{id}/config`
- `POST /api/v1/calls/outbound`
- `POST /api/v1/forms`
- `POST /api/v1/forms/{id}/submit`
- `GET /api/v1/calls`
- `GET /api/v1/calls/{id}`
- `GET /api/v1/analytics/summary`
- `POST /api/v1/webhooks/telephony/inbound`
- `POST /api/v1/webhooks/telephony/status`
- `WS /api/v1/ws/telephony/{call_id}`

## Voice Session State Machine
```text
session_start -> greet -> listen -> transcribe -> decide -> speak -> listen
                                           |                    |
                                           +--> escalate/handoff+

Barge-in path:
  speak + caller_speech_detected -> stop_tts -> listen

terminal:
  completed | failed | escalated
```

## Compose + Env
- Compose stack: `db`, `redis`, `backend`, `frontend`, `prometheus`
- Env file: `.env.example`
- Key vars:
  - DB/Redis: `POSTGRES_*`, `REDIS_URL`
  - Telephony: `TWILIO_*`, `PUBLIC_BASE_URL`
  - ASR/TTS: `ASR_ENDPOINT`, `TTS_ENDPOINT`
  - Security: `SECRET_KEY`, `PLATFORM_ADMIN_KEY`, `TENANT_SECRET_KEY`

## UI Routes
- `/login`
- `/dashboard`
- `/agents`
- `/forms`
- `/calls`
- `/analytics`

## Testing Strategy
- API smoke tests (health, auth bootstrap/login, tenant-scoped CRUD)
- Workflow tests (form submit -> outbound call record)
- Realtime tests (websocket media event ingestion and transcript insert)
- Provider contract tests (Twilio adapter request format)
- Load tests for concurrent calls and ASR/TTS latency budgets

## Phased Plan
- Phase 0 (1-2 weeks): auth, tenant model, RBAC, schema/migrations, API skeleton, UI login/dashboard.
- Phase 1 (2-4 weeks): inbound calls, websocket media stream, transcript persistence, barge-in handling.
- Phase 2 (2-3 weeks): outbound calls, forms builder/submit workflows, declarative routing rules.
- Phase 3 (2-4 weeks): booking webhook tool, human handoff automation, analytics hardening and eval pipelines.
