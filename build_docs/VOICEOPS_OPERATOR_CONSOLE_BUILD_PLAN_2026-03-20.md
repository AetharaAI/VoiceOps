# VoiceOps Operator Console Build Plan

## 1. Exact Schema / Entity Changes Needed

### Canonical product entities

1. `agents`
   - Continue as the runtime-owned conversational entity.
   - Future normalized additions:
     - `workflow_type`: `inbound` | `shared_runtime`
     - `display_goal`
     - `greeting_mode`
     - `knowledge_sources`
     - `transfer_rules`
     - `after_hours_policy`
     - `voicemail_policy`
     - `crm_mapping`
     - `action_map`
   - Small-slice staging rule:
     - Store builder-specific config under `workflow_dsl.inbound_builder` now, so the operator split can ship without blocking on a full migration.

2. `outbound_campaigns`
   - New first-class entity.
   - Fields:
     - `id`
     - `tenant_id`
     - `agent_id`
     - `name`
     - `caller_id_number`
     - `lead_source`
     - `objective`
     - `opening_line`
     - `qualification_fields`
     - `objection_guidance`
     - `booking_target`
     - `retry_rules`
     - `voicemail_config`
     - `handoff_rules`
     - `crm_mapping`
     - `model_config`
     - `tts_config`
     - `is_active`
     - `created_at`
     - `updated_at`

3. `phone_numbers`
   - Keep current mapping for inbound answering.
   - Future addition:
     - route profile metadata for timeout, forwarding, after-hours, and voicemail behavior.

4. `calls`
   - Keep current table.
   - Continue using:
     - `campaign_id` for outbound association
     - `context_payload` for call-time context snapshot
     - `outcome_tags` for operator-visible state
   - Future additions:
     - `route_kind`
     - `response_mode`
     - `prompt_snapshot_id`
     - `cost_summary`

5. `transcript_segments`
   - Keep as-is.

6. Redis streams
   - Current call event stream stays the backbone for the operator console.
   - Expand with three logical stream lanes:
     - `voiceops:call_events`
     - `voiceops:call_extractions`
     - `voiceops:call_actions`
   - Consumers:
     - OCR / document parser
     - small extraction model
     - CRM connector

## 2. Exact UI / Page Structure

### Primary operator surfaces

1. `/inbound`
   - Purpose:
     - configure who answers
     - configure how the call opens
     - configure what gets extracted
     - configure what actions the agent is allowed to execute
   - Sections:
     - `Inbound Workflow Builder`
     - `Assigned Number`
     - `Greeting & Live Runtime`
     - `Business Context`
     - `Required Extraction Targets`
     - `Action Execution`
     - `CRM Capture Mapping`
     - `Existing Inbound Workflows`
   - Required operator fields:
     - workflow name
     - inbound number
     - greeting mode
     - opening greeting
     - persona / business context
     - objective / operator guidance
     - required fields JSON
     - action policy JSON
     - CRM mapping JSON
     - live model
     - TTS lane
     - voice

2. `/outbound`
   - Purpose:
     - configure reusable outbound campaign behavior
     - separate outbound logic from inbound answering logic
   - Sections:
     - `Outbound Campaign Builder`
     - `Campaign Identity`
     - `Lead / Targeting`
     - `Conversation Objective`
     - `Qualification`
     - `Retry / Voicemail / Handoff`
     - `CRM Writeback`
     - `Runtime Selection`
     - `Existing Campaigns`
   - Required operator fields:
     - campaign name
     - assigned agent
     - caller ID number
     - lead source
     - objective
     - opening line
     - qualification fields
     - objection guidance
     - booking target
     - retry rules
     - voicemail config
     - handoff rules
     - CRM mapping
     - model
     - TTS lane
     - voice

3. `/calls`
   - Keep as the observability surface.
   - Make it the runtime truth page:
     - transcript
     - llm mode
     - response source
     - intent
     - decision events
     - call/campaign association

## 3. Exact Call-State / Runtime Flow

### Inbound

1. number resolves to inbound workflow
2. greeting is delivered
   - prerecorded or fixed TTS is allowed here
3. from first caller turn onward:
   - audio -> ASR -> transcript -> LLM -> tool selection and/or text -> TTS
4. required fields are extraction targets, not a blocking pre-LLM gate
5. actions emitted from conversation:
   - transfer
   - schedule
   - SMS
   - CRM writeback
   - webhook
6. scripted backend text is fallback only

### Outbound

1. operator or workflow triggers outbound campaign
2. campaign + agent + runtime snapshot are written to the call context
3. greeting / opener is delivered
4. live turn loop starts immediately after the callee responds:
   - audio -> ASR -> LLM -> tools/TTS
5. qualification and booking happen through natural dialogue
6. outcomes and extracted fields are written to call artifacts and streams

## 4. Exact Logging / Observability Fields To Surface In UI

### Per call

- `direction`
- `route`
- `agent_name`
- `campaign_name`
- `llm_mode`
- `response_source`
- `detected_intent`
- `greeting_mode`
- `llm_model`
- `tts_model`
- `tts_voice`
- `required_fields_missing`
- `required_fields_captured`
- `tool_calls`
- `fallback_reason`
- `transfer_target`
- `voicemail_detected`
- `asr_latency_ms`
- `llm_latency_ms`
- `tts_latency_ms`
- `token_usage`
- `cost_estimate`

### Operator event trail

- `call.started`
- `call.greeting.sent`
- `call.llm.request.start`
- `call.llm.request.end`
- `call.llm.request.fail`
- `call.intent.detected`
- `call.required_fields.missing`
- `call.required_fields.collected`
- `call.fallback.engaged`
- `call.response.generated`
- `call.response.spoken`
- `call.tool.invoked`
- `call.tool.completed`

## 5. Exact File-By-File Implementation Map

### Backend

- `services/backend/app/models/models.py`
  - add `OutboundCampaign`
- `services/backend/app/schemas/campaign.py`
  - new create/update/response models
- `services/backend/app/api/routes/campaigns.py`
  - CRUD for outbound campaigns
- `services/backend/app/api/router.py`
  - include campaign routes
- `services/backend/app/api/routes/calls.py`
  - allow outbound calls to resolve campaign context
- `services/backend/alembic/versions/*`
  - add outbound campaign table

### Frontend

- `services/frontend/components/nav.js`
  - split operator navigation to Inbound / Outbound
- `services/frontend/app/inbound/page.js`
  - inbound workflow builder
- `services/frontend/app/outbound/page.js`
  - outbound campaign builder
- `services/frontend/app/calls/page.js`
  - surface campaign linkage and runtime state
- `services/frontend/app/globals.css`
  - support new navigation and workflow layout
- `services/frontend/lib/operator-builder.js`
  - shared runtime selectors, JSON parsing, labels

## 6. Smallest Safe Vertical Slice To Implement First

1. Ship dedicated `/inbound` and `/outbound` pages.
2. Reuse current `Agent` runtime for inbound.
3. Add first-class `OutboundCampaign` persistence and API.
4. Wire outbound call creation to campaign context when present.
5. Keep `/calls` as the operator observability page.

### Why this slice first

- It fixes product shape immediately.
- It does not break the current telephony runtime.
- It creates a real outbound artifact instead of another generic agent.
- It keeps the LLM/TTS selectors exposed on both sides.
- It leaves room for the next stage:
  - richer inbound routing
  - Redis extraction consumers
  - CRM/document automation
