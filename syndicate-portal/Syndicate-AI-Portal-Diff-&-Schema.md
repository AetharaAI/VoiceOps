
## Recommended host split

Use this pattern:

* `voice.aetherpro.us` → internal/operator/dev/docs/admin surface
* `voice.syndicateai.co` → customer-facing portal + branded access point

That gives you:

* cleaner branding externally
* less risk of mixing admin and client UX
* room to keep internal docs/tools ugly and useful

Now the useful part.

# Portal v1 API / schema diff

## Extension only. No destructive changes.

Your current API already exposes reusable foundations for tenant auth, tenant self-read, phone numbers, business hours, routing rules, forms, calls, analytics, agents, and telephony webhook flow. 

So the move is:

* **reuse existing endpoints where possible**
* **add portal-safe endpoints for client controls**
* **add supporting tables/models for portal-only concerns**
* **leave current VoiceOps endpoints intact**

---

# 1. Existing endpoints to reuse unchanged

These are already good substrate endpoints and should stay:

## Auth / tenant identity

* `POST /api/v1/auth/bootstrap`
* `POST /api/v1/auth/login`
* `GET /api/v1/auth/me`
* `POST /api/v1/tenants`
* `GET /api/v1/tenants/me` 

## Tenant config

* `GET /api/v1/phone-numbers`
* `POST /api/v1/phone-numbers`
* `GET /api/v1/business-hours`
* `PUT /api/v1/business-hours`
* `GET /api/v1/routing-rules`
* `POST /api/v1/routing-rules` 

## Forms / intake

* `GET /api/v1/forms`
* `POST /api/v1/forms`
* `POST /api/v1/forms/{form_id}/submit` 

## Calls / summaries / metrics foundation

* `GET /api/v1/calls`
* `GET /api/v1/calls/{call_id}`
* `GET /api/v1/call-logs/latest`
* `GET /api/v1/call-logs/by-call-sid/{call_sid}`
* `GET /api/v1/analytics/summary` 

These are already enough to power a big chunk of the portal.

---

# 2. New portal endpoints to add

These should be **additive**, tenant-safe, and customer-facing.

## Dashboard

### `GET /api/v1/portal/dashboard`

Purpose: one round-trip summary for the client portal home screen.

Returns:

* tenant summary
* current agent mode
* today/7-day metrics
* recent summaries
* recent escalations
* config completeness flags
* health/fallback status

This endpoint should aggregate existing calls + analytics + tenant config into one client-safe object.

---

## Business profile

### `GET /api/v1/portal/business-profile`

### `PUT /api/v1/portal/business-profile`

Fields:

* legal_business_name
* public_business_name
* website
* timezone
* service_area_summary
* primary_contact_name
* primary_contact_email
* primary_contact_phone
* after_hours_instructions

This is distinct from raw tenant internals. It’s the customer-managed profile layer.

---

## Agent mode / kill switch

### `GET /api/v1/portal/agent-mode`

### `PUT /api/v1/portal/agent-mode`

This is the critical one.

Enum:

* `enabled`
* `bypass`
* `after_hours_only`

Optional later:

* `overflow_only`
* `maintenance`

Payload:

* `mode`
* `fallback_destination`
* `reason` optional
* `changed_by`

This should not mutate your core telephony architecture destructively. It should act like a high-priority routing override.

---

## Escalation contacts

### `GET /api/v1/portal/escalation-contacts`

### `PUT /api/v1/portal/escalation-contacts`

Fields:

* primary_escalation_number
* emergency_escalation_number
* after_hours_number
* sms_summary_recipients[]
* email_summary_recipients[]

This is separate from raw routing rules because customers think in people/numbers, not policy objects.

---

## Call settings

### `GET /api/v1/portal/call-settings`

### `PUT /api/v1/portal/call-settings`

Fields:

* services_offered[]
* emergency_categories[]
* transfer_emergencies_live
* capture_appointment_requests
* must_never_say[]
* special_instructions
* required_intake_fields[]

This is the client-safe business policy layer.

---

## Summaries

### `GET /api/v1/portal/summaries`

### `GET /api/v1/portal/summaries/{summary_id}`

Likely backed by:

* call logs
* call detail
* form submissions
* maybe derived summary records later

---

## Team

### `GET /api/v1/portal/team`

### `POST /api/v1/portal/team`

### `PUT /api/v1/portal/team/{user_id}`

### `DELETE /api/v1/portal/team/{user_id}`

Roles:

* owner
* manager
* viewer

This is separate from platform admin auth.

---

## Audit log

### `GET /api/v1/portal/audit-log`

Query params:

* limit
* since
* actor
* event_type

This is portal-only visibility into changes.

---

# 3. New tables / models to add

These are the minimum additive schema pieces.

## `tenant_users`

Purpose: customer portal users tied to a tenant.

Fields:

* id
* tenant_id
* email
* full_name
* password_hash or external_auth_subject
* status
* created_at
* updated_at
* last_login_at

## `tenant_user_roles`

Fields:

* id
* tenant_user_id
* role (`owner`, `manager`, `viewer`)
* created_at

Could be folded into `tenant_users.role` at first if you want to move fast.

---

## `business_profiles`

Fields:

* tenant_id
* legal_business_name
* public_business_name
* website
* timezone
* service_area_summary
* primary_contact_name
* primary_contact_email
* primary_contact_phone
* after_hours_instructions
* updated_at

This keeps customer-facing business profile separate from raw tenant row concerns.

---

## `routing_mode_state`

This is your safe override layer.

Fields:

* tenant_id
* mode (`enabled`, `bypass`, `after_hours_only`)
* fallback_destination
* updated_by
* updated_at

This is the cleanest way to add the kill switch without hacking random flags into unrelated tables.

---

## `escalation_contacts`

Fields:

* id
* tenant_id
* contact_type (`primary`, `emergency`, `after_hours`, `sms_summary`, `email_summary`)
* value
* label
* enabled
* created_at
* updated_at

You could also normalize recipient lists here instead of baking arrays into business_profiles.

---

## `call_settings`

Fields:

* tenant_id
* services_offered_json
* emergency_categories_json
* transfer_emergencies_live
* capture_appointment_requests
* must_never_say_json
* special_instructions
* required_intake_fields_json
* updated_at

Fastest route is JSON-backed config, then normalize later only if needed.

---

## `audit_log`

Fields:

* id
* tenant_id
* actor_type (`platform_admin`, `tenant_user`, `system`)
* actor_id
* event_type
* object_type
* object_id
* previous_value_json
* new_value_json
* created_at

Non-negotiable if customers can change live behavior.

---

# 4. Existing endpoints that may need light extension

Not replacement. Just enhancement.

## `/api/v1/phone-numbers`

Add optional fields in response/model:

* `fallback_destination`
* `agent_mode_supported`
* `current_mode`

Only if that fits your current shape cleanly.

## `/api/v1/business-hours`

Probably reusable as-is for portal UI. 

## `/api/v1/routing-rules`

Keep internal/admin-oriented.
Do not expose raw rule complexity to customers unless you build a simplified view.

## `/api/v1/calls` and `/api/v1/call-logs/latest`

Good for portal data source, but you may want a portal-specific summarized facade so the client UI doesn’t have to understand internal call-log shapes. 

---

# 5. UI route map for `voice.syndicateai.co`

Recommended app routes:

* `/login`
* `/dashboard`
* `/business-profile`
* `/call-settings`
* `/business-hours`
* `/contacts`
* `/summaries`
* `/forms`
* `/analytics`
* `/team`
* `/audit-log`

Top control bar:

* status badge
* AI Enabled / Bypass / After-Hours Only
* last updated time
* support contact

This is the clean customer shell.

---

# 6. Safe mode / bypass logic

Your concern is correct: if the AI path breaks, customer needs a fast out.

So operationally:

## Portal control

Customer toggles:

* Enabled
* Bypass
* After-Hours Only

## Backend behavior

Do **not** make this a manual human workflow.
This should resolve in the live call-routing decision path.

Pseudologic:

1. load tenant
2. load current routing_mode_state
3. if `bypass` → return direct fallback route / normal ringing path
4. if `after_hours_only` and current time is business hours → bypass
5. else continue AI flow

That is clean and reversible.

---

# 7. Recommended implementation order

## Phase 1

* `tenant_users`
* `business_profiles`
* `routing_mode_state`
* `escalation_contacts`
* `audit_log`
* portal auth/session
* dashboard
* business profile page
* business hours page
* contacts page
* agent mode toggle

## Phase 2

* call settings
* summaries view
* team management
* richer analytics
* forms/submissions

## Phase 3

* email/chat adapters
* notification rules
* deeper workflow surfaces
* customer-safe automations

---

# 8. What not to expose in portal v1

Leave these internal:

* `/api/v1/agents/{agent_id}/config`
* `/api/v1/llm/models`
* `/api/v1/tts/voices`
* raw telephony webhook surfaces
* full routing-rule internals unless simplified
* provider/model/runtime knobs 

Customers do not need a screwdriver set inside the cockpit.

---

# 9. Final recommendation

Yes:

* build portal on `voice.syndicateai.co`
* keep current VoiceOps internals intact
* add a thin portal API layer and supporting tables
* treat this as **extension, not rewrite**

Best one-line framing:

**Syndicate AI Voice Agents Portal is the customer-facing control plane built on top of the existing AetherPro VoiceOps multi-tenant substrate.**

That’s the right architecture and the right product story.

If you want, next I’ll write this as a **paste-ready engineering RFC markdown file** with sections for goals, non-goals, endpoints, schema additions, rollout phases, and open questions.

