# Aether VoiceOps Runbook

## 1) Prerequisites
- Docker + Docker Compose
- Twilio Voice number (for live PSTN tests)
- Reachable URL for Twilio webhooks (ngrok, cloud LB, or domain)
- Existing ASR and TTS endpoints

## 2) Bootstrap
1. Copy env file:
   ```bash
   cp .env.example .env
   ```
2. Set required values in `.env`:
   - `SECRET_KEY`
   - `PLATFORM_ADMIN_KEY`
   - `TENANT_SECRET_KEY`
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`
   - `ASR_ENDPOINT`, `TTS_ENDPOINT`
3. Start stack:
   ```bash
   docker compose up --build
   ```

## 3) Core URLs
- API Docs: `http://localhost:8000/docs`
- UI: `http://localhost:3000`
- Metrics: `http://localhost:8000/metrics`
- Prometheus: `http://localhost:9090`

## 4) Hello-World Tenant Demo
1. Open UI `/login` and run **Bootstrap Tenant**.
2. Create an agent in `/agents`.
3. Add a phone number in `/dashboard` tied to the agent ID.
4. Create a form in `/forms` with workflow `on_submit.action = call_now` and `agent_id`.
5. Submit the form with `{ "phone": "+1555..." }`.
6. Check `/calls` for outbound call record and transcript segments.

## 5) Twilio Inbound Setup
1. Configure Twilio voice webhook URL:
   - `POST https://<public-domain>/api/v1/webhooks/telephony/inbound`
2. Configure status callback:
   - `POST https://<public-domain>/api/v1/webhooks/telephony/status`
3. Ensure websocket endpoint reachable by Twilio stream:
   - `wss://<public-domain>/api/v1/ws/telephony/{call_id}`

## 6) Troubleshooting
- 401/403 in UI:
  - verify token is in browser localStorage key `voiceops_token`
  - verify role for route
- DB migration failures:
  - check `POSTGRES_*` values and restart `db`
- Calls not dialing:
  - verify Twilio credentials and outbound caller ID
- Empty transcripts:
  - verify `ASR_ENDPOINT` receives audio payload and returns `{ text: ... }`
- No TTS audio:
  - verify `TTS_ENDPOINT` supports POST JSON `{text,voice,format}`

## 7) Security Controls
- RBAC enforced at API layer (owner/admin/agent/analyst)
- Tenant scoping on persisted records
- Audit trail (`audit_events`)
- Per-tenant recording + redaction + retention toggles
- Integration secrets encrypted in DB

## 8) Ops Notes
- Current deploy target is Docker Compose; K8s manifests can be added with same service boundaries.
- Telephony provider abstraction lives under `app/services/telephony/providers.py`.
