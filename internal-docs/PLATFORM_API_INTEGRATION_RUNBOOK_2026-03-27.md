# Platform API Integration Runbook

## Purpose

This runbook defines how `platform.aetherpro.us` should integrate with VoiceOps so users, tenant access, API keys, and billing can be managed from one control plane.

Primary rule for this app:
- **Do not change VoiceOps Postgres URL for this integration.**
- VoiceOps already runs on the managed Postgres instance you control.

This document is focused on practical, low-risk integration order before high user volume.

## Current Truth (Verified in VoiceOps)

VoiceOps already has:
- Tenant model (`tenants` table)
- User model (`users` table, tenant-scoped unique email)
- JWT auth login path
- Platform-admin-gated bootstrap/tenant creation

Current routes in this repo:
- `POST /api/v1/auth/bootstrap` (requires `X-Platform-Admin-Key`)
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/tenants` (requires `X-Platform-Admin-Key`)
- `GET /api/v1/tenants/me`

Current auth behavior:
- Access tokens are VoiceOps-signed JWTs
- Tenant context is bound to user in JWT + DB lookup

## System Ownership Split

`platform.aetherpro.us` owns:
- customer/org onboarding UX
- global user directory and membership orchestration
- API key lifecycle UI and policy
- Stripe + payment lifecycle
- subscription plan state and entitlement policy

`voice.aetherpro.us` (VoiceOps) owns:
- telephony operations runtime
- agent config/runtime
- call state and artifacts
- tenant-scoped operational data
- local auth enforcement for VoiceOps APIs

Rule:
- Platform is control plane.
- VoiceOps is execution plane.

## Non-Goals for This Phase

- No cross-app Postgres rewiring for VoiceOps.
- No migration of VoiceOps operational tables into platform DB.
- No high-risk auth replacement in one cutover.

## Integration Architecture

### 1. User and tenant provisioning (now)

Platform provisions tenants/users in VoiceOps through admin endpoints.

Flow:
1. Platform creates customer/org in platform DB.
2. Platform calls VoiceOps bootstrap/provision endpoint(s).
3. VoiceOps creates/updates tenant + owner/admin user.
4. Platform stores mapping:
- `platform_org_id -> voiceops_tenant_id`
- `platform_user_id -> voiceops_user_id`

### 2. SSO/token brokering (next)

Preferred direction:
- Platform is identity authority.
- Platform issues short-lived signed broker token.
- VoiceOps exchanges broker token for VoiceOps JWT (tenant-scoped).

Interim accepted:
- Platform can continue to use VoiceOps native login for internal/admin flows.

### 3. Billing and entitlements (parallel)

Platform owns Stripe and plan state.
VoiceOps consumes entitlement snapshot (read-only) to enforce:
- feature access
- volume caps
- premium model access

Recommended transport:
- platform -> VoiceOps signed webhook for entitlement updates
- plus periodic pull reconciliation job

## Required Data Contracts

### Platform -> VoiceOps (minimum)

Tenant upsert payload:
- `external_org_id` (platform ID)
- `name`
- `slug`
- `plan`
- `status` (`active`, `past_due`, `suspended`, `canceled`)

User upsert payload:
- `external_user_id` (platform ID)
- `tenant_id` (VoiceOps UUID)
- `email`
- `full_name`
- `role` (`owner`, `admin`, `agent`, `analyst`)
- `is_active`

Entitlement payload:
- `tenant_id`
- `max_concurrent_calls`
- `max_monthly_minutes`
- `enabled_tts_models`
- `enabled_features`
- `effective_at`

### VoiceOps -> Platform (minimum)

Usage/billing events:
- call started/completed
- call duration seconds
- model lane used
- billable unit totals

Audit events:
- user invited/deactivated
- role changed
- auth failures threshold crossed

## API Strategy (Pragmatic)

### Phase A: Use existing endpoints + small adapter

Use current routes now:
- `POST /api/v1/auth/bootstrap`
- `POST /api/v1/tenants`

Add a thin platform adapter service to normalize retries, idempotency keys, and mapping storage.

### Phase B: Add explicit provisioning endpoints in VoiceOps

Add dedicated routes (recommended):
- `PUT /api/v1/platform/tenants/{external_org_id}`
- `PUT /api/v1/platform/users/{external_user_id}`
- `POST /api/v1/platform/entitlements/sync`

All protected by:
- `X-Platform-Admin-Key` now
- platform service JWT / mTLS later

## Security Requirements

- Never use localhost for cross-VM calls.
- TLS required for all platform <-> VoiceOps traffic.
- Include request idempotency key on provisioning writes.
- Record immutable audit logs for tenant/user entitlement changes.
- Rotate platform admin key on fixed schedule.

## Postgres Policy (VoiceOps)

For this integration, VoiceOps DB connection stays as-is.

Do:
- keep current managed Postgres connection for VoiceOps
- add only minimal columns/tables required for external mapping and entitlements

Do not:
- move VoiceOps to a different DB URL as part of this integration
- run broad schema rewrites during provisioning rollout

## Rollout Plan

1. Create platform->VoiceOps adapter with retry + idempotency.
2. Provision one internal test tenant end-to-end.
3. Verify login and tenant scoping (`/auth/me`, `/tenants/me`).
4. Add entitlement sync endpoint and deny-path checks.
5. Enable Stripe plan->entitlement mapping in platform.
6. Shadow usage event export for billing validation.
7. Cut over first paid tenant.

## Failure Handling Rules

- `401/403`: auth/key problem, do not retry blindly.
- `409`: duplicate slug/user conflict, resolve mapping and retry idempotently.
- `422`: payload contract drift, block rollout until fixed.
- `5xx`: exponential backoff + dead-letter queue.

## Operational Checklist

Before production cutover:
- [ ] platform org/user IDs mapped to VoiceOps IDs
- [ ] idempotent provisioning writes validated
- [ ] entitlement deny paths tested
- [ ] Stripe webhook replay tested
- [ ] billing event reconciliation report in place
- [ ] rollback runbook tested on staging

## Example cURL (Current Endpoints)

Bootstrap tenant + owner (existing):

```bash
curl -sS https://voice.aetherpro.us/api/v1/auth/bootstrap \
  -H 'Content-Type: application/json' \
  -H 'X-Platform-Admin-Key: <platform_admin_key>' \
  -d '{
    "tenant_name": "Acme Services",
    "tenant_slug": "acme-services",
    "email": "owner@acme.com",
    "full_name": "Acme Owner",
    "password": "<strong-password>"
  }'
```

Create tenant directly (existing):

```bash
curl -sS https://voice.aetherpro.us/api/v1/tenants \
  -H 'Content-Type: application/json' \
  -H 'X-Platform-Admin-Key: <platform_admin_key>' \
  -d '{
    "name": "Acme Services",
    "slug": "acme-services",
    "recording_enabled": false,
    "pii_redaction_enabled": true,
    "retention_days": 90
  }'
```

## Decision Summary

- You are making this change at the right stage, before scale.
- Keep VoiceOps DB wiring stable.
- Centralize user/key/payment control in platform.
- Integrate via explicit contracts and phased rollout, not a one-shot rewrite.
