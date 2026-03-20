You’re tracking fine. The move is:

**Don’t invent the pattern. Extract it from systems that already close calls, log data, and don’t fall apart.**

And yes, your current UI/runtime is upside down.

Also, on the session question: I can use what’s in this conversation and what you paste/show me here, but I can’t just freely roam all your other chat tabs like a raccoon in the attic.

## What the successful systems are actually doing

Across **GoHighLevel, Salesforce, Retell, and Vapi**, the overlap is pretty clear:

1. **Inbound and outbound are separate workflows**

   * HighLevel documents inbound routing separately and explicitly ties it to phone-number behavior, forwarding, timeout, and voicemail handling. ([HighLevel Support Portal][1])
   * Retell requires agent/number binding and says that number configuration governs both inbound and outbound behavior. ([Retell AI][2])
   * Vapi’s phone docs treat inbound and outbound as first-class call types, not one mashed-together screen. ([Vapi][3])
   * Salesforce separates service voice, dialer, and high-volume outbound patterns. ([Salesforce][4])

2. **The voice agent is connected to business actions, not just talking**

   * Vapi ships default tools like `transferCall`, `endCall`, `sms`, `dtmf`, and `apiRequest`, which is the right model: the agent speaks, but it also does things. ([Vapi][5])
   * Retell supports transfer flows, webhooks, outbound calls, and post-call structured analysis/extraction. ([Retell AI][6])
   * Salesforce emphasizes real-time transcription, recommendations, call logging, and outbound call flows. ([Developer][7])
   * HighLevel positions Voice AI as handling calls naturally while collecting customer information for follow-up. ([HighLevel Support Portal][8])

3. **There is always a routing / transfer / fallback layer**

   * HighLevel cares about forwarding, timeout, and voicemail collision. That means telephony routing is not optional plumbing; it is product logic. ([HighLevel Support Portal][1])
   * Vapi has call forwarding and assistant-based warm transfer with hold handling and failed-transfer scenarios. ([Vapi][9])
   * Retell has dedicated transfer-call tooling and call-transfer nodes. ([Retell AI][6])
   * Salesforce supports transfer/routing APIs and formal outbound/transfer flows in Service Cloud Voice setups. ([Salesforce Documentation][10])

4. **Personalization and per-call context are injected dynamically**

   * Vapi uses dynamic variables per call so prompts and first messages are contextualized at runtime. ([Vapi][11])
   * Retell supports dynamic variables for context-specific agent behavior. ([Retell AI][12])
   * Salesforce centers the call inside CRM records and record-linked context. ([Salesforce][13])
   * HighLevel is natively CRM/workflow-oriented, not just “agent prompt in a box.” ([HighLevel Support Portal][14])

5. **They all produce structured call artifacts**

   * Salesforce: real-time transcription, logs, notes, and AI recommendations/summaries. ([Developer][7])
   * Retell: post-call analysis with summary, sentiment/status, custom extraction, token usage, and webhook events. ([Retell AI][15])
   * HighLevel: call logs and collected customer info are part of the product story. ([HighLevel Support Portal][16])

## The baseline pattern you should copy

This is the shared skeleton:

**A. Channel layer**

* phone number
* inbound/outbound mode
* forwarding
* timeout
* voicemail detection
* transfer destinations

**B. Conversation layer**

* greeting / opener
* objective
* business context
* tone / persona
* knowledge access
* escalation policy
* compliance constraints

**C. Action layer**

* book appointment
* transfer call
* send SMS
* collect fields
* update CRM
* trigger webhook/API
* end call / follow-up disposition

**D. Data layer**

* transcript
* summary
* extracted fields
* outcome / status
* recording link
* latency + token usage
* call cost

That’s the pattern. Same bones, different lipstick.

## What this means for your product

You do **not** need to match GoHighLevel feature-for-feature by Monday. That’s how people end up building a flaming cathedral.

You need to match the **operational shape** by Monday.

### Version 1 that is sellable

Build exactly two operator surfaces:

### 1) Inbound Agent

Fields:

* Agent name
* Assigned phone number(s)
* Greeting mode

  * prerecorded
  * TTS fixed greeting
  * generated greeting
* Business description
* Goal
* Knowledge sources
* Required fields to collect

  * name
  * company
  * callback
  * reason for call
  * appointment intent
  * urgency
* Transfer rules
* After-hours behavior
* Voicemail behavior
* SMS follow-up template
* CRM mapping
* Model selection
* Voice selection

### 2) Outbound Campaign

Fields:

* Campaign name
* Caller ID / outbound number
* Lead source / list
* Goal
* Opening line
* Qualification fields
* Objection-handling guidance
* Booking target
* Voicemail drop behavior
* Retry rules
* Human handoff rules
* CRM writeback mapping
* Model selection
* Voice selection

That split alone fixes half your product confusion.

## Runtime you actually need

Your runtime should be:

**Audio in → ASR → transcript → LLM with call state + agent config + CRM context → tool call or speech output → TTS → audio out**

Not:
**audio in → if/else spaghetti → canned text → TTS**

That second one is just an IVR wearing a fake mustache.

## What to tell Codex

Use this as the structured brief.

```text
We are rebuilding the voice product around the baseline pattern used by successful systems like GoHighLevel, Salesforce, Retell, and Vapi.

Core rule:
Inbound and outbound are separate products with shared telephony plumbing, not a single agent editor.

Required architecture:

1. Separate backend entities
- inbound_agents
- outbound_campaigns
- phone_numbers
- call_routes
- call_runs
- call_transcripts
- call_extractions
- call_actions
- crm_mappings

2. Separate UI surfaces
A) Inbound Agent Builder
- assign phone number(s)
- greeting config
- business context
- objective
- knowledge source config
- required field extraction
- transfer rules
- voicemail/timeout/after-hours behavior
- SMS follow-up template
- CRM mapping
- model + voice selection

B) Outbound Campaign Builder
- campaign objective
- lead source/list
- opener
- qualification fields
- objection handling guidance
- booking target
- retry logic
- voicemail behavior
- transfer/escalation rules
- CRM mapping
- model + voice selection

3. Real conversational runtime
After greeting, every turn must run:
audio -> ASR -> transcript -> LLM -> tools and/or TTS -> audio
The configured LLM must generate the response text.
Hard-coded scripted responses may exist only as explicit fallback mode.

4. Tool/action layer
Support these action types:
- transfer_call
- end_call
- send_sms
- create_or_update_contact
- create_note
- schedule_appointment
- api_request/webhook
- mark_outcome

5. Observability
Per call, store and expose:
- inbound vs outbound
- transcript
- model used
- prompt/context snapshot
- model output
- extracted fields
- tool calls
- transfer events
- voicemail detection
- ASR latency
- LLM latency
- TTS latency
- token usage
- cost

6. UX principle
Do not build for the implementer.
Build for an operator who needs to configure, test, and deploy a phone workflow without reading source code.
```

## What to prioritize by ROI

Ranked:

**1. Fix runtime so the LLM actually drives the conversation**

* Highest ROI
* Without this, the product is fake

**2. Split inbound and outbound**

* Highest UX ROI
* Removes mental chaos and bad config bleed

**3. Add structured extraction + CRM writeback**

* This is what makes it worth money

**4. Add transfer / voicemail / timeout handling**

* This is what makes it usable in production

**5. Add observability**

* This is what lets you debug and sell with confidence

## Monday plan

By Monday, the goal is not “complete voice platform.”
The goal is:

**Sellable voice MVP**

* real LLM conversation
* one clean inbound builder
* one clean outbound builder
* field extraction
* CRM writeback
* transfer/fallback
* usable call logs

If your stack cannot do that cleanly by Monday, your backup plan is rational:
use GoHighLevel as a **revenue bridge**, not as your home. HighLevel already has inbound flow handling, CRM/workflow integration, and embedded Voice AI positioning. ([HighLevel Support Portal][1])

That’s not surrender. That’s refusing to let pride slow cash flow.

Next move after this: I can turn this into a **page-by-page product spec** for Codex with exact screens, fields, backend entities, and call-state logic.

[1]: https://help.gohighlevel.com/support/solutions/articles/155000003431-inbound-call-flow-for-voice-ai-calls " Set up Inbound Call Flow for Voice AI calls in HighLevel : HighLevel Support Portal "
[2]: https://docs.retellai.com/deploy/outbound-call "Outbound Calls (Make Calls) - Retell AI"
[3]: https://docs.vapi.ai/quickstart/phone "Phone calls | Vapi"
[4]: https://help.salesforce.com/s/articleView?id=sales.voice_dialer.htm&language=en_US&type=5&utm_source=chatgpt.com "Sales Dialer"
[5]: https://docs.vapi.ai/tools/default-tools "Default Tools | Vapi"
[6]: https://docs.retellai.com/build/single-multi-prompt/transfer-call?utm_source=chatgpt.com "Transfer call"
[7]: https://developer.salesforce.com/docs/atlas.en-us.voice_developer_guide.meta/voice_developer_guide/voice_example_set_up_transcription.htm?utm_source=chatgpt.com "Set Up Call Transcription | Service Cloud Voice ..."
[8]: https://help.gohighlevel.com/support/solutions/articles/155000003911-ai-voice-agents-overview " AI Employee Voice Call Capabilities : HighLevel Support Portal "
[9]: https://docs.vapi.ai/call-forwarding?utm_source=chatgpt.com "Call Forwarding"
[10]: https://resources.docs.salesforce.com/latest/latest/en-us/sfdc/pdf/support_voice_pt_amazon_connect.pdf?utm_source=chatgpt.com "Get Started with Service Cloud Voice with Partner ..."
[11]: https://docs.vapi.ai/assistants/dynamic-variables "Variables | Vapi"
[12]: https://docs.retellai.com/build/dynamic-variables?utm_source=chatgpt.com "Dynamic Variables"
[13]: https://help.salesforce.com/s/articleView?id=sales.voice_intro.htm&language=en_US&type=5&utm_source=chatgpt.com "Guidelines for Making and Receiving Calls"
[14]: https://help.gohighlevel.com/support/solutions/articles/155000002294-what-are-workflow-actions-complete-list-?utm_source=chatgpt.com "A List of Workflow Actions"
[15]: https://docs.retellai.com/api-references/create-phone-call "Create Phone Call - Retell AI"
[16]: https://help.gohighlevel.com/support/solutions/articles/155000005900-call-logs-for-voice-ai-agents?utm_source=chatgpt.com "Call Logs for Voice AI Agents"

