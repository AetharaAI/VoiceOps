You are a principal engineer building “Aether VoiceOps”: a multi-tenant, self-hosted, AI-first voice agent platform similar to GoHighLevel’s voice/automation features, but built as a reusable voice-agent pattern deployable across many client companies.

HARD REQUIREMENTS (non-negotiable)
1) Must support inbound and outbound phone calls.
2) Must support real-time, streaming voice interaction with barge-in (user can interrupt TTS).
3) Must support multi-tenant (many client orgs) with per-tenant configuration.
4) Must integrate with existing services:
   - ASR service: Whisper v3 large (SysTrain variant) exposed as HTTP endpoint(s).
   - TTS service: Kokoro + existing TTS Chatterbox(tts.aetherpro.us/docs) server exposed as HTTP endpoint(s).
* I have kokoro and systran/whisper models in block storage already.
* Chatterbox-TTS-Server is live at tts.aetherpro.us/docs
5) Must be production-grade: structured logs, metrics, traces, retries, rate limits, audit trail, recordings policy.
6) Must be self-hostable with Docker Compose (later K8s), and sovereign-by-default (no forced SaaS dependencies).
7) Provide a web UI for:
   - tenant onboarding
   - configuring voice agents (scripts, tools, business rules)
   - forms builder (intake forms)
   - call logs/transcripts
   - analytics (conversion, containment, booking rate, avg handle time)
8) Provide an API-first backend (FastAPI preferred) with OpenAPI/Swagger.
9) Provide a working MVP path that can be delivered quickly, then iterated.

GOAL
Create a reusable “Voice Agent Blueprint” that can be cloned per client:
- Each client can define: phone numbers, business hours, escalation rules, scripts, tools (calendar booking, CRM writeback), compliance settings, and one or more “agent personas”.
- System should allow deploying multiple agents per tenant (e.g., Sales agent, Support agent, After-hours agent).

ARCHITECTURE OVERVIEW
Implement a modular system with these services:

A) telephony-gateway
- Primary adapter: Twilio (support Twilio Voice inbound/outbound; Media Streams via WebSocket).
- Abstract interface so we can add other carriers later (Vonage, SignalWire).
- Responsibilities:
  - inbound call webhook handler
  - outbound call initiation API
  - websocket bridge for bidirectional audio streaming
  - DTMF capture
  - call status events
  - optional call recording toggles per tenant

B) realtime-orchestrator (Voice Session Manager)
- Central session state machine:
  - session start → greet → listen → transcribe partials → decide turns → speak → interrupt handling → end
- Must support:
  - VAD (voice activity detection) for turn detection
  - partial transcripts (incremental ASR) and final transcript segments
  - barge-in: if user starts speaking, immediately stop TTS playback, flush outgoing audio buffer
  - latency budget: target < 700ms perceived response after user stops speaking (best-effort)
- Tool calling:
  - booking, CRM, knowledgebase lookup, ticket creation, SMS follow-up, email follow-up
- Safety:
  - tenant-configured allowed actions, confirmation requirements, fallback to human handoff

C) asr-client
- Integrates with existing ASR endpoints.
- Support streaming mode:
  - If ASR endpoint is not streaming, implement micro-batching: send short chunks (e.g., 200–400ms) and stitch.
- Must output:
  - partial tokens / partial transcript
  - final segments with timestamps
  - confidence score when available

D) tts-client
- Integrates with existing TTS endpoints (Kokoro + chatbot server).
- Must support streaming audio output (chunked transfer) OR simulate streaming by generating audio then chunking.
- Must support “stop” mid-playback when barge-in occurs.

E) agent-runtime
- LLM router (can call local models or API models, but must be pluggable).
- Prompting strategy:
  - system prompt template
  - per-tenant script + policy + tools
  - per-call context: caller id, call reason, form fields, prior interactions
- Must include deterministic “workflow guardrails”:
  - a state machine / checklist for required fields (e.g., name, phone, appointment type)
  - enforce business hours logic
  - enforce escalation conditions (anger, repeated failure, sensitive topics)

F) workflow-engine
- Declarative workflow DSL stored per tenant:
  - intake form schema (fields, validation)
  - call flows (nodes: ask, confirm, branch, tool_call, handoff)
  - post-call actions (send SMS/email, create CRM record, schedule follow-up)
- UI must allow editing these without code.

G) persistence layer
- PostgreSQL as source of truth.
- Redis/Valkey for realtime session cache + rate limiting + pubsub (optional).
- Store:
  - tenants, users, roles
  - agents, prompts, tools configuration
  - phone numbers, routing rules, business hours
  - calls, transcripts, recordings metadata, evaluations, outcomes
  - forms, submissions
  - integrations (calendar, CRM, webhooks)
- Provide schema migrations.

H) observability
- Structured JSON logs across services (correlation id = call_id + session_id).
- Metrics: calls/min, ASR latency, TTS latency, LLM latency, containment rate, booking rate, error rate.
- Tracing: OpenTelemetry optional but preferred.

SECURITY / MULTI-TENANCY
- Auth:
  - JWT auth for UI/API; RBAC (owner/admin/agent/analyst).
- Tenant isolation:
  - every record scoped by tenant_id
  - guard all queries
- Secrets:
  - per-tenant encrypted integration secrets
- Compliance toggles per tenant:
  - call recording on/off
  - redaction of PII in logs
  - retention windows

FUNCTIONAL FEATURES (MVP)
1) Inbound calls:
   - Configure a tenant phone number
   - Route to a selected agent based on business hours + rules
   - Real-time conversation with ASR+TTS
   - Capture transcript + outcome

2) Outbound calls:
   - API endpoint to trigger call:
     - tenant_id, to_number, agent_id, optional campaign_id, optional context payload
   - After call, store transcript + outcome

3) Forms-to-Call workflow:
   - UI form builder for intake
   - When form submitted, agent can:
     - call user, or
     - schedule a call, or
     - send SMS link, based on workflow
   - Store submission linked to call(s)

4) Appointment booking tool:
   - Provide an integration interface:
     - “calendar provider” pluggable; implement a generic webhook-based booking first
   - Agent can propose times, confirm, then book.

5) Human handoff:
   - If escalation triggered:
     - transfer call to a real number OR create an urgent ticket + SMS a human.
   - Must log why escalation happened.

REALTIME AUDIO DETAILS
- Use a websocket media stream to receive PCM audio frames from telephony provider.
- Normalize sample rate (8k/16k) and format.
- Implement jitter buffer and backpressure.
- Maintain an “audio out” pipeline for TTS playback:
  - chunk and stream audio back to provider
- Barge-in:
  - if VAD detects speech while speaking, immediately stop playback, cancel pending TTS, switch to listening.

API SPEC (must implement)
- POST /tenants
- POST /agents
- PUT /agents/{id}/config
- POST /calls/outbound
- POST /forms
- POST /forms/{id}/submit
- GET /calls
- GET /calls/{id}
- GET /analytics/summary
- Webhooks:
  - /webhooks/telephony/inbound
  - /webhooks/telephony/status
  - websocket endpoint: /ws/telephony/{call_id}

UI SPEC (must implement)
- Login
- Tenant dashboard:
  - phone numbers
  - business hours
  - routing rules
- Agent builder:
  - persona + script + required fields + tools toggles
- Forms builder:
  - drag/drop fields (or simple schema editor)
- Calls:
  - list, detail, transcript playback, outcome tags
- Analytics:
  - basic KPIs

DELIVERABLES
1) Repo structure with services folders + shared libs.
2) Docker Compose for local dev.
3) Database schema (SQLAlchemy) + migrations.
4) FastAPI backend with OpenAPI.
5) Web UI (React/Next.js preferred) consuming the API.
6) A “hello-world tenant” demo: configure number, agent, take inbound call, book a fake appointment.
7) A runbook: environment variables, setup steps, test flow, troubleshooting.

CONSTRAINTS / DECISIONS
- Must be written so that telephony provider is swappable.
- Must not hardcode credentials; everything from env + tenant secrets.
- Must be built to later support:
  - realtime streaming ASR native
  - multiple concurrent calls per tenant
  - campaign dialing
  - call scoring / evaluation
  - RAG knowledgebase plugin

IMPLEMENTATION PLAN
Provide a phased plan:
Phase 0: skeleton + DB + auth + tenant model
Phase 1: inbound call + realtime streaming + transcripts
Phase 2: outbound calls + forms + workflow rules
Phase 3: booking + handoff + analytics
Include time/complexity notes and explicit interfaces.

OUTPUT FORMAT
- Start with a high-level diagram (text-based).
- Then provide detailed module specs.
- Then database schema tables.
- Then API endpoints with request/response models.
- Then key state machines (voice session).
- Then docker-compose and env var lists.
- Then minimal UI routes/components.
- Then a testing strategy and demo script.
Do not produce placeholder fluff; produce concrete, implementable specs and stubs.
