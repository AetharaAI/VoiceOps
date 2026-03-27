# Platform To AetherVoice-X Integration Requirements

## Why this document exists

This is the implementation checklist for connecting your future `platform.aetherpro.us` to `AetherVoice-X` so platform-issued API keys work reliably.

This doc is intentionally focused on connectivity, auth, and shared key lifecycle.

## Current truth (verified in code)

1. `AetherVoice-X` currently defaults to its own Docker Postgres service.
- `docker-compose.yml` defines `postgres` service.
- `.env.example` default: `POSTGRES_URL=postgresql://voice:voice@postgres:5432/aether_voice`.

2. Gateway already validates API keys.
- `X-API-Key` is hashed (`sha256`) and checked against `api_keys.key_hash` where `is_active=true`.

3. Key-management APIs are not implemented yet.
- No public route in this repo for create/list/revoke API keys.

4. Auth mode currently supports optional local operation.
- `AUTH_MODE=optional` allows anonymous fallback in current local/operator flow.

## What this means for your platform

You are correct: if platform creates keys in a database that AetherVoice-X cannot read, AetherVoice-X cannot validate those keys.

So you need one of these patterns:

## Pattern A (recommended now): Shared Postgres auth data

Use one Postgres instance (or cluster) reachable by:
- platform service
- AetherVoice-X gateway

Both can use separate databases/schemas, but the key table used for validation must be accessible to gateway.

### Minimal shape

- Platform writes key metadata and `key_hash`.
- AetherVoice-X reads key metadata and validates request headers.

## Pattern B (later): Dedicated auth service

- Platform owns key lifecycle in its own DB.
- AetherVoice-X calls an auth service (or caches signed key tokens) instead of direct DB lookup.

This is cleaner long-term but more moving parts now.

## Immediate implementation plan (practical)

### Step 1: Move AetherVoice-X off local compose Postgres (optional but recommended)

Set `POSTGRES_URL` in AetherVoice-X `.env` to your managed Postgres endpoint.

Example:

```env
POSTGRES_URL=postgresql://<user>:<pass>@<managed-host>:5432/<db_name>
```

If doing this, you can keep local `postgres` container disabled for production profile.

### Step 2: Keep/extend the required auth tables

AetherVoice-X already expects:
- `tenants`
- `api_keys` with columns:
  - `id`
  - `tenant_id`
  - `key_hash`
  - `label`
  - `is_active`

Add these fields now for platform-grade lifecycle:
- `scopes` (TEXT[] or JSONB)
- `expires_at` (TIMESTAMPTZ)
- `created_by` (TEXT/UUID)
- `revoked_at` (TIMESTAMPTZ)
- `last_used_at` (TIMESTAMPTZ)

## Step 3: Update gateway auth lookup logic (required for scoped keys)

Current code returns fixed broad scopes for any valid API key.

You need to change this so gateway loads scopes from DB row per key.

Target behavior:
- key row contains scopes and active/expiry state
- gateway enforces endpoint scopes from key row
- expired/revoked key => 401

## Step 4: Build platform key lifecycle API

Platform should expose endpoints like:
- `POST /api-keys` create
- `GET /api-keys` list
- `POST /api-keys/{id}/revoke`

Creation flow:
1. generate plaintext key once
2. hash with SHA-256
3. store only hash
4. return plaintext once to operator

## Step 5: Enforce strict auth in production

Set on AetherVoice-X:

```env
AUTH_MODE=strict
```

This prevents anonymous fallback and forces key/JWT usage.

## Step 6: Tenant model decision

Decide now whether you run:
- single-tenant (all your products share one tenant)
- multi-tenant (per customer or per product tenant)

If multi-tenant, platform must map each key to correct tenant and scope set.

## Step 7: Cross-VM connectivity rule

If platform VM and AetherVoice-X VM are separate:
- do not use localhost between them
- use public/private routable hostnames
- enforce TLS
- restrict inbound firewall/security groups by source

## Required contract between platform and AetherVoice-X

At request time, AetherVoice-X needs to determine:
- key is valid
- key belongs to active tenant
- key has required scope for endpoint
- key is not expired/revoked

If those four are true, request proceeds.

## Minimal “ready” definition

You are API-key ready for platform launch when all are true:

1. `AUTH_MODE=strict` in production.
2. AetherVoice-X gateway validates keys against shared auth data.
3. Key scopes are loaded per key (not hardcoded broad scopes).
4. Platform can create, list, revoke keys.
5. Rotated/revoked keys stop working immediately (or within defined cache TTL).
6. Tenant and scope failures return clear 401/403 responses.

## What to tell Codex in other repos

Use this exact prompt:

```text
Integrate this app with AetherVoice-X using gateway-only API calls and platform-issued API keys.
Assume key lifecycle is owned by platform.aetherpro.us.
Implement strict auth usage (X-API-Key), do not rely on anonymous mode.
Ensure all calls use routable hostnames (no localhost cross-VM).
If app needs voice lists, source from /v1/tts/studio/voices and filter by runtime_target.
Return explicit handling for 401/403/409/5xx.
```

## Notes specific to your current setup

- VoiceOps/SyndicateAI can share a managed Postgres with platform.
- AetherVoice-X can either:
  - join that same Postgres for auth tables, or
  - keep separate app DB and read keys from an auth schema/service.

Start with shared Postgres auth tables first. It is the fastest path that matches your current infra reality.

