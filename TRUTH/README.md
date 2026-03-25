# TRUTH Documentation System

## Purpose
This folder defines the documentation standard for production systems operated on these VMs.

These docs are meant to prevent drift between:
- what is deployed
- what operators believe is deployed
- what agents assume is deployed

Use this system in every serious repo.

## Canonical Files

### `AGENTS.md`
Use for:
- agent/operator instructions
- repo-specific working rules
- deployment workflow
- environment and coordination notes

Do not use it for:
- long historical logs
- secrets
- speculative roadmap writing

Example:
- what the repo is
- where it runs
- what rules the agent must follow
- which docs must always stay updated

### `PROJECT_STATE.md`
Use for:
- current implementation status
- what is live
- what is incomplete
- important active files
- recommended next steps

Do not use it for:
- deep historical chronology
- broad architecture philosophy

Example:
- feature X is live
- feature Y is still mock-driven
- deploy target is `/var/www/service-name`

### `CHANGELOG.md`
Use for:
- dated record of material changes
- merges, deploys, auth changes, infra changes, API changes

Do not use it for:
- duplicate project-state prose
- open questions

Example:
- `2026-03-21`: merged feature branch into `main`, published new bundle, added Passport auth

### `TRUTH.md`
Use for:
- terse snapshot of current reality
- public URLs
- repo names
- infra location
- active production facts
- operator mechanics

Do not use it for:
- verbose narrative
- every minor implementation detail

Example:
- site URL
- backend URL
- instance type
- Tailscale IP
- current production truth

## Update Triggers
Update the canonical docs whenever:
- a live feature is added or removed
- a deploy path changes
- a public URL changes
- auth behavior changes
- a branch is merged and published
- infra/host/runtime facts change
- operator workflow changes

Minimum rule:
- if production truth changed, update `TRUTH.md`
- if repo behavior changed, update `PROJECT_STATE.md`
- if the change matters historically, update `CHANGELOG.md`
- if the agent should behave differently now, update `AGENTS.md`

## Suggested Workflow
1. Make or verify the change.
2. Update `AGENTS.md`, `PROJECT_STATE.md`, `CHANGELOG.md`, and `TRUTH.md`.
3. Build/restart/deploy as needed.
4. Verify the live result.
5. Commit and push.

## Templates
- `AGENTS.template.md`
- `PROJECT_STATE.template.md`
- `CHANGELOG.template.md`
- `TRUTH.template.md`

Copy these into the repo root of a new production system and fill them in immediately.
