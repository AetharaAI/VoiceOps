Yes. And your instinct about the **kill switch / bypass** is dead right.

If you are touching a live business number, the client portal needs one brutally simple control:

**Agent Mode**

* **ON** = route through AI flow
* **BYPASS** = send directly to their fallback destination / normal ringing path
* maybe later **AFTER-HOURS ONLY** = only AI outside business hours

That is not a nice-to-have. That is a trust feature.

If something breaks, if they get nervous, if they have a weird promotion day, if they just want humans only for a few hours, they need a safe way out that does not require you to wake up, find coffee, and SSH into something. That belongs in Client Portal v1. Your current API already has the tenant/config scaffolding to support this kind of control plane extension. 

Here’s the clean RFC-style version.

---

# AetherPro Operations Fabric

## Client Portal v1 RFC

### Purpose

Client Portal v1 is the external, tenant-safe control plane for **Syndicate AI Voice Agents**. It gives each customer a constrained interface to manage business-facing configuration, view operational results, and safely control live call routing without exposing internal admin tools, model internals, or platform-wide controls.

### Relationship to Existing System

Client Portal v1 is built on top of the existing VoiceOps multi-tenant API surface, which already includes:

* auth
* tenants
* phone numbers
* business hours
* routing rules
* agents
* calls
* forms
* analytics
* telephony webhooks 

Portal v1 does not replace the internal operator/admin layer. It exposes only a tenant-scoped subset of the system.

---

## 1. Goals

### Primary goals

* Give clients a safe self-service portal
* Reduce onboarding friction
* Reduce support dependency for basic business config changes
* Increase trust by providing visibility and emergency control
* Keep live business phone operations safe with a clear bypass path
* Reuse existing VoiceOps tenant/config primitives instead of rebuilding from scratch

### Secondary goals

* Improve retention through visibility and ownership
* Create a product-grade customer experience
* Establish the external surface of the broader Operations Fabric

---

## 2. Non-goals

Portal v1 will **not** include:

* raw admin console functionality
* platform-wide tenant visibility
* model/provider switching
* full prompt editing
* internal debug traces
* arbitrary workflow editing
* infra/operator controls
* platform-wide analytics
* billing engine replacement
* support automation runtime

This is a customer portal, not your root shell with rounded corners.

---

## 3. User Roles

### tenant_owner

Full control over tenant-safe settings, users, notifications, routing mode, summaries, and analytics.

### tenant_manager

Can manage most business config and review operations, but cannot change billing/admin ownership.

### tenant_viewer

Read-only access to summaries, analytics, and selected business settings.

### platform_admin

Internal only. Not exposed in the client portal role picker.

---

## 4. Core Modules

## 4.1 Dashboard

Landing page for tenant users.

### Purpose

Show the customer whether the system is healthy, active, and worth paying for.

### Widgets

* Agent status
* Current mode: ON / BYPASS / AFTER-HOURS ONLY
* Today’s call totals
* Recent captured leads
* Escalations
* Avg handle time
* Recent summaries
* Last config change
* Quick action buttons

### Quick actions

* Enable AI
* Bypass AI
* Set After-Hours Only
* View recent calls
* Edit business hours
* Edit escalation contacts

---

## 4.2 Business Profile

Tenant-owned business metadata.

### Fields

* Public business name
* Legal business name
* Primary contact
* Billing contact
* Website
* Service area
* Time zone
* Main business number
* After-hours instructions
* Emergency categories
* Summary recipients

### Notes

This should be editable without touching the internal admin panel.

---

## 4.3 Agent Mode / Safe Routing Control

This is the most important client control.

### Modes

* **AI Enabled**
* **Bypass to Human / Default Route**
* **After-Hours Only**

### Optional later modes

* AI Overflow Only
* Maintenance Mode
* Emergency Transfer Only

### Requirements

* mode changes must be immediate or near-immediate
* changes must be logged in audit history
* client must see confirmation of active mode
* there must always be a fallback destination on file before AI can be enabled for live traffic

### Why it matters

If something breaks during business hours, the client must be able to revert routing without waiting on support.

---

## 4.4 Business Hours

Powered by existing business-hours config primitives. 

### Functions

* view current hours
* edit hours
* holiday override later
* after-hours behavior preview
* show effective schedule in local time

### Notes

This belongs in the portal because clients change it more often than they think.

---

## 4.5 Escalation & Contacts

Customer-owned fallback and routing targets.

### Fields

* primary escalation number
* after-hours escalation number
* emergency transfer number
* SMS summary recipients
* email summary recipients
* manager notification list

### Rules

* validate number formats
* do not allow empty critical routing contacts when AI is enabled
* all changes get audit logged

---

## 4.6 Call Settings

Tenant-safe call handling preferences.

### Fields

* services offered
* service areas
* emergency categories
* must capture appointment requests: yes/no
* transfer emergency calls live: yes/no
* require callback summary: yes/no
* caller qualification fields
* “must never say” notes
* approved special instructions

### Not exposed

* raw agent persona internals
* provider/model configuration
* full workflow DSL

---

## 4.7 Forms & Intake

Built on your existing form endpoints. 

### Functions

* view intake forms
* view submissions
* basic required-field control
* submission export later
* business-specific capture preferences

### Why

This helps onboarding and lets clients control what data they care about without you hand-editing every little thing.

---

## 4.8 Summaries & Recent Activity

Operational visibility.

### Views

* recent call summaries
* callback-needed items
* recent escalations
* recent submissions
* outbound campaign activity later

### Notes

This is one of the features that makes the system feel real to the client.

---

## 4.9 Analytics

Backed by your current analytics summary surface. 

### Metrics for v1

* total calls
* completed calls
* escalation count/rate
* avg handle time
* captured leads
* recent daily trend
* maybe containment rate if you trust the metric enough to expose it

### Not for v1

* platform-wide fleet metrics
* deep observability
* infra metrics
* raw trace/event internals

---

## 4.10 Team Access

Basic tenant user management.

### Functions

* add user
* remove user
* assign role
* manage summary recipients
* view last login later

### Constraints

* no one can elevate to platform_admin
* tenant_owner retains final control
* audit log all membership changes

---

## 5. Audit Log

Every client-facing change should land here.

### Track

* who changed it
* what changed
* previous value
* new value
* timestamp
* tenant id

### Required events

* mode change
* hours change
* escalation contact change
* recipient change
* call setting change
* form setting change
* user role change

This will save your ass later.

---

## 6. API Boundary Strategy

### Keep internal/admin endpoints separate from tenant-safe endpoints

Even if they share backend services, the contract must be different.

### Existing reusable primitives

Use the current endpoints and models where they already fit:

* `/api/v1/tenants/me`
* `/api/v1/phone-numbers`
* `/api/v1/business-hours`
* `/api/v1/routing-rules`
* `/api/v1/forms`
* `/api/v1/forms/{form_id}/submit`
* `/api/v1/calls`
* `/api/v1/calls/{call_id}`
* `/api/v1/analytics/summary` 

### New portal-oriented endpoints to add

Suggested examples:

* `GET /api/v1/portal/dashboard`
* `GET /api/v1/portal/business-profile`
* `PUT /api/v1/portal/business-profile`
* `GET /api/v1/portal/agent-mode`
* `PUT /api/v1/portal/agent-mode`
* `GET /api/v1/portal/escalation-contacts`
* `PUT /api/v1/portal/escalation-contacts`
* `GET /api/v1/portal/summaries`
* `GET /api/v1/portal/audit-log`
* `GET /api/v1/portal/team`
* `POST /api/v1/portal/team`
* `PUT /api/v1/portal/team/{user_id}`

Portal routes should be tenant-safe by design.

---

## 7. Data Model Additions

### Needed first-class objects

* tenant_users
* tenant_roles
* escalation_contacts
* notification_recipients
* business_profile
* portal_preferences
* audit_log
* routing_mode_state

### Optional later

* holidays
* service_catalog
* intake_schema_versions
* summary_templates
* notification_rules

---

## 8. Fail-Safe / Reliability Requirements

### Mandatory

Every live tenant must have:

* fallback route configured
* current routing mode visible
* manual bypass available
* audit trail for mode changes

### Recommended

* last health check visible
* “last successful AI handled call” timestamp
* warning banner if fallback route is missing
* warning banner if required contacts are incomplete

This is the part that turns “cool demo” into “safe enough to run on a real business line.”

---

## 9. UI Navigation for Portal v1

### Sidebar

* Dashboard
* Business Profile
* Call Settings
* Business Hours
* Contacts & Escalations
* Summaries
* Forms
* Analytics
* Team
* Audit Log

### Top action bar

* AI Enabled / Bypass / After-Hours Only
* Save changes
* Contact support
* Last sync time

---

## 10. Delivery Phases

## Phase 1

Minimum viable client portal.

* auth
* dashboard
* business profile
* business hours
* escalation contacts
* agent mode toggle
* analytics snapshot
* recent summaries

## Phase 2

Operational self-service.

* forms/submissions
* team access
* audit log
* richer call settings
* notification recipients

## Phase 3

Broader Operations Fabric extension.

* inbox/email/chat channels
* richer workflow surfaces
* event history
* customer-safe automations
* deeper reporting

---

## 11. Product Framing

### Internal name

**AetherPro Operations Fabric**

### Customer-facing product

**Syndicate AI Voice Agents Portal**

That way the customer sees a simple product, while you preserve the deeper architecture internally.

---

## 12. Immediate Board Items

Put these on your board exactly:

* finalize legal packet
* setup docusign and payment links
* tighten conversational flow
* define portal v1 modules
* add agent mode: on / bypass / after-hours only
* add escalation contact model
* add audit log for tenant changes
* expose business hours + recipients in client UI
* close first customer before broadening scope

That’s the real order.

If you want, next I’ll do the **API/schema diff** for Portal v1: which new tables/endpoints you need, and which existing VoiceOps endpoints you can reuse unchanged.

