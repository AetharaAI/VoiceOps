# RFC: Syndicate AI Voice Agents Portal v1

## Status
Draft

## Owner
AetherPro Technologies LLC

## Related Systems
- Aether VoiceOps API
- AetherPro Operations Fabric (emerging internal platform layer)
- Syndicate AI customer-facing product surface

## Summary
Build a tenant-safe customer portal for Syndicate AI Voice Agents as an extension of the existing Aether VoiceOps multi-tenant backend. The portal will be branded and exposed at `voice.syndicateai.co` while reusing and extending the existing VoiceOps API and data model. This is an additive architecture change, not a rewrite.

## Goals
- Create a customer-facing control plane for Syndicate AI Voice Agents
- Reuse existing tenant-aware VoiceOps primitives
- Keep internal admin/operator tools separate from customer-facing controls
- Provide safe self-service for business configuration
- Provide a live fail-safe mode switch for customer trust and operational safety
- Reduce onboarding/support burden

## Non-Goals
- Rewriting VoiceOps core services
- Exposing internal operator/admin tooling to customers
- Exposing provider/model/runtime controls
- Building a full workflow builder
- Replacing billing systems
- Replacing internal observability tooling

## Product Boundary
### Internal
- Aether VoiceOps API
- operator/admin surfaces
- raw call logs, traces, provider controls, infra tooling

### External
- Syndicate AI Voice Agents Portal
- tenant-safe business configuration
- summaries
- analytics
- forms/submissions
- team access
- mode control (enabled / bypass / after-hours only)

## Deployment Model
### Public Hostnames
- `voice.aetherpro.us` → internal/operator/dev/docs/admin surface
- `voice.syndicateai.co` → customer-facing portal

### Infrastructure
Both hostnames may resolve to the same VM public IP. Reverse proxy routing will separate the applications by hostname and/or path. Shared physical placement is acceptable and preferred for low-latency internal service calls.

### Internal Services
- `voiceops-api`
- `portal-app`
- `postgres`
- `valkey`
- reverse proxy

### Networking
Portal-to-API communication should occur over the same VM private network or proxied internal routes. Same-machine deployment reduces operational complexity but does not remove the need for clean auth and route separation.

## Existing VoiceOps API Primitives to Reuse
- auth
- tenants
- phone numbers
- business hours
- routing rules
- forms
- calls
- analytics

## New Portal Modules
- Dashboard
- Business Profile
- Agent Mode
- Business Hours
- Contacts & Escalations
- Call Settings
- Summaries
- Forms
- Analytics
- Team Access
- Audit Log

## Critical Control: Agent Mode
Expose a simple customer-safe routing control:
- `enabled`
- `bypass`
- `after_hours_only`

This mode must be tenant-scoped, auditable, and effective in the live routing decision path.

## New API Endpoints
- `GET /api/v1/portal/dashboard`
- `GET /api/v1/portal/business-profile`
- `PUT /api/v1/portal/business-profile`
- `GET /api/v1/portal/agent-mode`
- `PUT /api/v1/portal/agent-mode`
- `GET /api/v1/portal/escalation-contacts`
- `PUT /api/v1/portal/escalation-contacts`
- `GET /api/v1/portal/call-settings`
- `PUT /api/v1/portal/call-settings`
- `GET /api/v1/portal/summaries`
- `GET /api/v1/portal/team`
- `POST /api/v1/portal/team`
- `PUT /api/v1/portal/team/{user_id}`
- `DELETE /api/v1/portal/team/{user_id}`
- `GET /api/v1/portal/audit-log`

## Schema Additions
### `tenant_users`
Tenant-scoped customer portal users.

### `business_profiles`
Customer-facing business metadata.

### `routing_mode_state`
Tenant-scoped control of enabled / bypass / after-hours-only mode.

### `escalation_contacts`
Recipients and fallback contacts.

### `call_settings`
Tenant-safe business policy settings for live call handling.

### `audit_log`
Track all tenant-facing configuration changes.

## Role Model
- `tenant_owner`
- `tenant_manager`
- `tenant_viewer`
- `platform_admin` (internal only)

## UI Route Map
- `/login`
- `/dashboard`
- `/business-profile`
- `/call-settings`
- `/business-hours`
- `/contacts`
- `/summaries`
- `/forms`
- `/analytics`
- `/team`
- `/audit-log`

## Safe Routing Behavior
When a live call arrives:
1. resolve tenant
2. resolve current routing mode
3. if mode is `bypass`, route to fallback destination
4. if mode is `after_hours_only` and current time is within business hours, bypass AI
5. otherwise continue standard AI call handling

## Implementation Phases

### Phase 1
- portal auth/session
- dashboard
- business profile
- business hours
- escalation contacts
- agent mode toggle
- analytics snapshot
- recent summaries

### Phase 2
- team access
- audit log
- call settings
- forms/submissions
- richer notifications

### Phase 3
- broader Operations Fabric integration
- inbox/email/chat adapters
- customer-safe automations
- richer event history

## Open Questions
- Whether portal auth should reuse existing auth tables directly or layer tenant users separately
- Whether fallback destination lives at phone-number level, tenant level, or both
- Whether summaries should be materialized separately or derived from call logs
- Whether portal API routes live inside the current VoiceOps service or a gateway layer

## Recommendation
Implement as a separate customer-facing repo served at `voice.syndicateai.co`, backed by the existing VoiceOps backend and additive portal endpoints. Preserve the current VoiceOps core as the stable internal substrate.
