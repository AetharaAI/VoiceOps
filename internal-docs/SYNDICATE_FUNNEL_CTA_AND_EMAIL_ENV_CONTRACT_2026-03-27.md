# Syndicate Funnel CTA + Email Env Contract

## Purpose

This is the handoff contract for wiring the live funnel page CTA + notifications in the `syndicate/syndicateai` node app.

Current known state:
- Slack webhook notification path is already wired in code.
- Email path needs env-backed provider config and runtime validation.

This document is implementation-focused for Codex on the live VM.

## 1) CTA Contract (Public Demo Path)

### Canonical values

- `DEMO_PHONE_NUMBER_E164=+18127212341`
- `DEMO_CALL_ENTRYPOINT=tel:+18127212341`
- `CTA_MODE=call_now` (default)

### Allowed CTA modes

- `call_now`
- `request_callback`
- `schedule_demo`

### Behavior by mode

- `call_now`:
  - CTA opens phone dial (`tel:`) on mobile and displays number on desktop.
  - Keep form submit path available for lead capture fallback.
- `request_callback`:
  - CTA submits lead form and marks lead as callback requested.
- `schedule_demo`:
  - CTA routes to scheduler or scheduling form path.

### Required lead payload fields

- `name`
- `phone`
- `email` (optional but recommended)
- `company` (optional)
- `message` or `use_case`
- `source` (must include page/source tag)

### Required metadata fields

- `cta_mode`
- `demo_phone_number`
- `timestamp_iso`
- `landing_variant` (if A/B variants exist)

## 2) Notification Contract

### Slack (already wired)

Required env:
- `SLACK_WEBHOOK_URL=<secret>`

Suggested optional env:
- `SLACK_CHANNEL_LABEL=syndicate-funnel`
- `SLACK_NOTIFY_ENABLED=true`

### Email (to wire now)

Choose one provider path. Recommended: Resend.

## 3) Email Provider Contract (Recommended: Resend)

### Required env

- `EMAIL_NOTIFY_ENABLED=true`
- `EMAIL_PROVIDER=resend`
- `RESEND_API_KEY=<secret>`
- `EMAIL_FROM=alerts@yourdomain.com`
- `EMAIL_TO_LEADS=you@yourdomain.com`
- `EMAIL_REPLY_TO=ops@yourdomain.com`

### Optional env

- `EMAIL_SUBJECT_PREFIX=[Syndicate Funnel]`
- `EMAIL_TO_BACKUP=second@yourdomain.com`

## 4) Email Provider Contract (SMTP fallback)

If not using Resend:

- `EMAIL_NOTIFY_ENABLED=true`
- `EMAIL_PROVIDER=smtp`
- `SMTP_HOST=<host>`
- `SMTP_PORT=587`
- `SMTP_SECURE=false`
- `SMTP_USER=<user>`
- `SMTP_PASS=<secret>`
- `EMAIL_FROM=alerts@yourdomain.com`
- `EMAIL_TO_LEADS=you@yourdomain.com`
- `EMAIL_REPLY_TO=ops@yourdomain.com`

## 5) Notification Logic Requirements

For each valid lead submit:

1. Persist lead (DB path).
2. Send Slack notification (best effort with error capture).
3. Send Email notification (best effort with error capture).
4. Return success to client if DB persist succeeded, even if one notifier fails.
5. Log notifier failures with redacted secrets.

Do not block lead capture on Slack/email transient failures.

## 6) Email Content Contract

Subject:
- `[Syndicate Funnel] New Demo Lead - {{name}}`

Body must include:
- name
- phone
- email
- company
- use case/message
- CTA mode
- source/page
- created timestamp

## 7) Security + Secrets Rules

- Never print full webhook URL or API keys in logs.
- Redact values in app startup logs.
- Keep secrets only in `.env` on node (not committed).
- Before paid customer launch:
  - rotate Slack webhook
  - rotate email provider API key
  - verify log redaction

## 8) Validation Checklist (Live VM)

1. Set env vars for selected provider.
2. Restart node service.
3. Submit one test lead from funnel.
4. Verify:
- lead persisted in DB
- Slack notification received
- Email notification received
- API response success
5. Submit one malformed lead and confirm validation errors are clean.
6. Confirm no secret leakage in logs.

## 9) Copy/Paste Env Blocks

### Resend block

```env
DEMO_PHONE_NUMBER_E164=+18127212341
DEMO_CALL_ENTRYPOINT=tel:+18127212341
CTA_MODE=call_now

SLACK_NOTIFY_ENABLED=true
SLACK_WEBHOOK_URL=__SET_ME__
SLACK_CHANNEL_LABEL=syndicate-funnel

EMAIL_NOTIFY_ENABLED=true
EMAIL_PROVIDER=resend
RESEND_API_KEY=__SET_ME__
EMAIL_FROM=alerts@__YOUR_DOMAIN__
EMAIL_TO_LEADS=__YOUR_EMAIL__
EMAIL_REPLY_TO=ops@__YOUR_DOMAIN__
EMAIL_SUBJECT_PREFIX=[Syndicate Funnel]
```

### SMTP block

```env
DEMO_PHONE_NUMBER_E164=+18127212341
DEMO_CALL_ENTRYPOINT=tel:+18127212341
CTA_MODE=call_now

SLACK_NOTIFY_ENABLED=true
SLACK_WEBHOOK_URL=__SET_ME__
SLACK_CHANNEL_LABEL=syndicate-funnel

EMAIL_NOTIFY_ENABLED=true
EMAIL_PROVIDER=smtp
SMTP_HOST=__SET_ME__
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=__SET_ME__
SMTP_PASS=__SET_ME__
EMAIL_FROM=alerts@__YOUR_DOMAIN__
EMAIL_TO_LEADS=__YOUR_EMAIL__
EMAIL_REPLY_TO=ops@__YOUR_DOMAIN__
EMAIL_SUBJECT_PREFIX=[Syndicate Funnel]
```

## 10) Message To Send Your Live-VM Codex

Use this exact instruction:

```text
Implement the funnel CTA + notifications using the contract in:
internal-docs/SYNDICATE_FUNNEL_CTA_AND_EMAIL_ENV_CONTRACT_2026-03-27.md

Requirements:
- Keep Slack path as already wired.
- Add email notify path with provider switch (resend first, smtp fallback).
- Make all notifier sends best-effort after DB persistence.
- Redact secrets in logs.
- Return a short verification report after one live test submit.
```
