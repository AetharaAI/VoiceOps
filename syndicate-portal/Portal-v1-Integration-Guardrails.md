# Syndicate Portal v1 Integration Guardrails

## Purpose
Build the customer-facing Syndicate Portal in a separate repo without destabilizing VoiceOps production behavior.

This document defines the minimum technical guardrails, endpoint boundaries, and launch checks.

## Hard Constraints
- Do not rewrite VoiceOps core call flow, Twilio webhook handling, or FSM internals for portal v1.
- Do not expose internal/admin controls in customer UI.
- Do not expose platform bootstrap paths (`x-platform-admin-key`) to browser clients.
- Keep portal changes additive and reversible.

## OpenAPI Reality Check (from `voiceops-openapi.json`)
- Existing reusable APIs exist for auth, tenant read, phone numbers, business hours, routing rules, forms, calls, call logs, analytics, and agents.
- `portal/*` endpoints do not exist yet and must be added intentionally.
- Existing user role enum is currently:
  - `owner`
  - `admin`
  - `agent`
  - `analyst`
- Proposed portal roles (`tenant_owner`, `tenant_manager`, `tenant_viewer`) require either:
  - mapping layer to current roles, or
  - additive new role model.

## Recommended Boundary: BFF Pattern
Use a portal backend/BFF in the new repo:
- Browser talks only to `portal-bff`.
- `portal-bff` calls VoiceOps API.
- `portal-bff` enforces allowlist and payload shaping.

Why:
- Prevents accidental client-side access to dangerous endpoints.
- Keeps future role mapping and response shaping centralized.
- Allows strict audit logging for portal actions.

## VoiceOps Endpoint Policy

### Allowlist (Portal v1 read/write)
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/tenants/me`
- `GET /api/v1/business-hours`
- `PUT /api/v1/business-hours`
- `GET /api/v1/routing-rules` (read only unless needed)
- `GET /api/v1/forms`
- `GET /api/v1/calls`
- `GET /api/v1/calls/{call_id}`
- `GET /api/v1/call-logs/latest`
- `GET /api/v1/analytics/summary`

### Denylist (Not exposed to portal clients)
- `POST /api/v1/auth/bootstrap`
- `POST /api/v1/tenants`
- All `/api/v1/webhooks/telephony/*`
- `POST /api/v1/calls/outbound` (until explicitly productized)
- Agent/provider/runtime internals (`/api/v1/agents*`) unless intentionally wrapped in safe portal endpoints

## Critical Safety Feature: Agent Mode
Portal v1 should include a tenant-safe routing override with audit:
- `enabled`
- `bypass`
- `after_hours_only`

Implementation guidance:
- Use additive table/state (e.g., `routing_mode_state`) keyed by `tenant_id`.
- Evaluate mode in live routing decision path with high priority.
- Require fallback destination to exist before allowing `enabled`.
- Every mode change must write audit entry with actor, previous value, next value, timestamp.

## “Do Not Break VoiceOps” Rollout Plan

### Phase A: Read-only portal
- Login/session
- Dashboard from existing analytics/calls/forms
- No mutating controls except maybe profile drafts in portal DB

### Phase B: Safe writes
- Business hours edit
- Escalation contacts
- Mode control with bypass default
- Audit log enabled

### Phase C: Controlled expansion
- Team access
- Forms preferences
- Additional summaries and exports

## Launch Gates (Must Pass Before Customer Use)
- Tenant isolation test:
  - tenant A cannot read/write tenant B records.
- Endpoint exposure test:
  - denylisted endpoints are unreachable via portal.
- Mode switch test:
  - toggle `enabled -> bypass -> after_hours_only` and verify routing behavior.
- Fallback safety test:
  - bypass routes to valid destination every time.
- Recovery test:
  - if portal service is down, VoiceOps call handling continues.
- Audit test:
  - all portal writes emit audit records with actor and delta.
- Regression test:
  - existing VoiceOps internal/admin UX still works unchanged.

## Operational Checklist
- Separate repo for portal app and portal BFF.
- Separate deploy unit (same VM is fine) behind hostname `voice.syndicateai.co`.
- Keep VoiceOps API as stable substrate at `voice.aetherpro.us`.
- Pin portal against versioned OpenAPI snapshot and run contract checks in CI.
- Add feature flag for mode-control enforcement path for controlled rollout.

## Recommended First Build Order (Practical)
1. Portal auth/session + `me` + tenant identity.
2. Read-only dashboard from existing analytics/calls/call-logs.
3. Business hours + escalation contacts.
4. Agent mode (with audit + fallback validation).
5. Team management and audit log views.

---

If this guardrail doc conflicts with implementation convenience, keep production safety first and defer features.
