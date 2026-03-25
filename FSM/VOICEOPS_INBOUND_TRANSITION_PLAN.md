# VoiceOps Inbound — Transition Plan

**Status:** Phase 2 — PENDING APPROVAL. No code changes until approved.
**Based on:** `VOICEOPS_INBOUND_AUDIT.md` (2026-03-25)

---

## Target Architecture Summary

Each call gets a single Redis Stream: `voice:calls:{session_id}`

```
Twilio WebSocket
       │
       ▼
  [Stream Ingester]  ─── publishes events ──▶  voice:calls:{session_id}
                                                        │
                          ┌─────────────────────────────┼──────────────────────────────┐
                          ▼                             ▼                              ▼
                 [State Controller]            [ASR Consumer]              [TTS Consumer]
                 Consumer group: ctrl          Consumer group: asr         Consumer group: tts
                          │                             │                              │
                  ONLY emits:                   reacts to:                    reacts to:
                  tts.speak                     asr.start_listen              tts.speak
                  asr.start_listen              publishes:                    publishes:
                  state.transition              asr.transcript                tts.complete
                          │
                  [LLM Consumer]
                  Consumer group: llm
                  reacts to:
                  llm.extract / llm.classify
                  publishes:
                  llm.extracted / llm.intent
```

Hard-listen guarantee: `tts.speak` can only come from the State Controller. The State Controller only emits `tts.speak` after receiving `asr.transcript` or `timeout.silence`. ASR only starts when it receives `asr.start_listen` from the State Controller.

---

## Current vs Target: Component Mapping

### What can be kept (minimal changes)

| Component | Current file | What to keep |
|---|---|---|
| Twilio webhook handler | `webhooks.py` | Keep as-is. It creates the Call record and returns TwiML. Add: emit `call.incoming` event to the per-call stream after DB commit. |
| Agent resolution | `inbound_routing.py` | Keep entirely. Runs before stream exists; result is payload data on `call.incoming`. |
| ASR client | `asr/client.py` | Keep entirely. It becomes a consumer service that reacts to `asr.start_listen` events and publishes `asr.transcript`. |
| TTS client | `tts/client.py` | Keep entirely. It becomes a consumer service that reacts to `tts.speak` events and publishes `tts.complete`. |
| Audio conversion | `realtime/audio.py` | Keep entirely — `mulaw_to_pcm16`, `resample_pcm16`, `pcm16_to_mulaw`, `wav_to_pcm16`. |
| Agent runtime: LLM call | `agent_runtime/runtime.py` `generate_response()` | Keep the HTTP call logic. LLM consumer subscribes to `llm.extract`/`llm.classify` and publishes `llm.extracted`/`llm.intent`. |
| Agent runtime: field extraction | `agent_runtime/runtime.py` `capture_required_fields()` | Keep. Moved into LLM consumer. |
| Event sink: file logging | `telephony/event_sink.py` | Keep file logging. Redis publishing is upgraded — events now go to per-call stream. |
| Call, Agent, TranscriptSegment models | `models/models.py` | Keep all ORM models unchanged. |
| Config | `core/config.py` | Add: `redis_call_stream_prefix`, `redis_stream_consumer_group_*`. |
| Inbound Workflow Builder frontend | `frontend/app/inbound/page.js` | Keep. Add: state/lane configuration (see §Config Changes). |

### What must be rewritten

| Component | Current file | Reason |
|---|---|---|
| `VoiceSessionManager` | `realtime/session_manager.py` | This is the monolith. The entire WebSocket handler, VAD loop, barge-in, turn-taking, LLM dispatch, and TTS dispatch are co-located. This becomes the **Stream Ingester**: a thin WebSocket handler that converts Twilio frames to events on the per-call stream. All downstream logic is removed. |
| `VoiceSession` dataclass | `session_manager.py` (top) | Session state moves out of memory and into stream event history + a Redis Hash for live FSM state. |
| Turn-taking logic | `session_manager.py` `process_audio_frame()`, `finalize_caller_turn()` | Replaced by FSM in State Controller. |
| `agent_runtime.build_llm_system_prompt()` | `runtime.py` | System prompt must be rewritten for the 7-state FSM. Each FSM state has its own prompt template. |
| `agent_runtime.build_opening_prompt()` | `runtime.py` | Replaced by FSM S1 → emit `tts.speak` with fixed greeting → wait for `tts.complete` → emit `asr.start_listen`. |

### What must be created (new modules)

| Module | Responsibility |
|---|---|
| `services/state_controller/` | FSM process. Consumer group `ctrl`. Reads ALL events from per-call stream. Maintains FSM state in Redis Hash. Emits `asr.start_listen`, `tts.speak`, `state.transition`. Only service that can emit these two commands. |
| `services/stream_ingester/` | Thin WebSocket handler replacing `VoiceSessionManager`. Converts Twilio events to stream entries: `call.incoming` (on webhook), audio frames as raw bytes in a side-channel, VAD results as `vad.voice_detected` / `vad.silence_detected` events. |
| `services/asr_consumer/` | Consumer group `asr`. Waits for `asr.start_listen`. Opens ASR stream to Aether Voice. Sends audio frames. On ASR final result: emits `asr.transcript`. |
| `services/tts_consumer/` | Consumer group `tts`. Waits for `tts.speak`. Calls Aether Voice TTS. Streams audio back to Twilio via the WebSocket (needs call reference). On completion: emits `tts.complete`. |
| `services/llm_consumer/` | Consumer group `llm`. Waits for `llm.extract` or `llm.classify`. Runs LLM call. Publishes `llm.extracted` (with field values) or `llm.intent` (with classified lane). |
| `services/audit_consumer/` | Consumer group `audit`. Subscribes to all events. Writes `.jsonl` and Postgres TranscriptSegments. Publishes `audit.log` on completion. |

---

## 7-State FSM: State Definitions and Transitions

### States

| State | Name | Entry condition | Actions on entry |
|---|---|---|---|
| S0 | Call Incoming | `call.incoming` event | Start ANI lookup async (emit `llm.extract` with ANI lookup task); emit `state.transition → S1` |
| S1 | Greeting | `state.transition → S1` | Emit `tts.speak` with fixed greeting text from agent config |
| S2 | Name Capture | `tts.complete` from S1; `asr.transcript` from S2 with no name yet | Emit `asr.start_listen`; on transcript: emit `llm.extract` for name |
| S3 | Intent Capture | Name captured or skipped | Emit `tts.speak` (ask intent); `asr.start_listen`; on transcript: emit `llm.classify` |
| S4a/b/c | Detail Capture | `llm.intent` → lane A/B/C | Lane-specific field prompts; `asr.start_listen` after each `tts.speak` |
| S5 | Contact Capture | All lane fields captured | Confirm ANI or prompt alt number |
| S6 | Readback + Confirm | All fields captured | Read back all details; Y/N loop |
| S7 | Close + Log | Confirmed or max retries | Goodbye TTS; write audit blob; emit `call.ended` |
| Esc | Escalation | Frustration or timeout at any state | Warm transfer TTS; escalate; emit `call.ended` |

### Hard-listen guarantee (State Controller rules)

```
RULE 1: Only emit tts.speak after:
    - Entry into a new state (S1, S2, S3, S4*, S5, S6, S7, Esc)
    - Receiving asr.transcript (response to caller)
    - Receiving timeout.silence (recovery prompt)

RULE 2: Only emit asr.start_listen after:
    - tts.complete received for the last tts.speak in current state

RULE 3: Never emit tts.speak if:
    - Last event was asr.start_listen and no asr.transcript has been received
    - (i.e., while ASR is active)
```

### Frustration and timeout escalation

| Trigger | Condition | Action |
|---|---|---|
| `timeout.silence` | No `vad.voice_detected` within N seconds of `asr.start_listen` | State Controller emits recovery TTS or escalates after threshold |
| `escalate.frustration` | LLM consumer detects frustration signal in transcript | State Controller transitions to Esc |
| Max retries | Same field fails N times | State Controller skips field or transitions to Esc |

---

## Migration Path

### Phase A: Observability (zero behavior change)

**Can be done now, before any FSM work.**

1. Modify `event_sink._publish_to_streams()` to ALSO write to `voice:calls:{call_id}` in addition to the existing global streams. Use `XADD` with `MAXLEN ~` trim.
2. Add a Redis Hash `voice:calls:{call_id}:state` with fields: `fsm_state`, `collected_fields_json`, `prompted_field`, `session_id`.
3. Nothing else changes. Existing system continues running. Redis now has per-call streams for inspection.

**Validates:** Redis per-call streams work, stream data structure is correct, no consumer conflicts.

### Phase B: ASR and TTS consumers in shadow mode

**Run new consumers in parallel with old system, but they don't affect call flow.**

1. Deploy `asr_consumer` and `tts_consumer` as new processes.
2. They subscribe to `voice:calls:*` streams but take no action — they observe and log.
3. Compare their observed event sequence against ground-truth `.jsonl` files.

**Validates:** Consumer group XREADGROUP mechanics, event ordering, no data loss.

### Phase C: State Controller in shadow mode

1. Deploy `state_controller` as a consumer but in read-only mode — it computes FSM transitions but does not emit `tts.speak` or `asr.start_listen`.
2. Log what it WOULD have emitted. Compare against what the old system actually did.

**Validates:** FSM logic correctness, state transition sequences, edge cases.

### Phase D: Hard cutover (single call, monitored)

1. Route one test call (internal number) through the new stack.
2. `stream_ingester` replaces `VoiceSessionManager` for that call.
3. State controller is live — emits real `tts.speak` and `asr.start_listen` commands.
4. Old system continues handling all other calls.

**Validates:** End-to-end audio path, hard-listen guarantee works, no talking-over-caller bug.

### Phase E: Full cutover

1. Route all new calls through new stack.
2. Old `VoiceSessionManager` kept in codebase but not instantiated.
3. Monitor for 48 hours. If stable, remove old code.

---

## Configuration Changes Required

### Agent model / Inbound Workflow Builder

The current agent config has no lane concept and no multi-state prompt config. New required fields:

```json
{
  "workflow_dsl": {
    "workflow_type": "inbound_fsm",
    "inbound_builder": {
      "greeting_mode": "tts_fixed",
      "greeting_text": "Hi, this is Alex with Sunrise HVAC. Who am I speaking with today?",
      "fsm_config": {
        "lanes": {
          "A": { "label": "Service Request", "fields": ["problem_description", "service_address", "urgency"] },
          "B": { "label": "Schedule Window", "fields": ["preferred_date", "preferred_time"] },
          "C": { "label": "Existing Job", "fields": ["job_number_or_description"] }
        },
        "silence_timeout_seconds": 8,
        "frustration_escalation_enabled": true,
        "max_retries_per_field": 2,
        "contact_capture": { "confirm_ani": true, "prompt_alt_if_missing": true }
      }
    }
  }
}
```

**Frontend changes:**
- Add lane A/B/C configuration section to Inbound Workflow Builder
- Add silence timeout setting
- Add frustration escalation toggle
- `greeting_mode` field is already present but currently ignored by the runtime — wire it up

### Redis configuration (new keys)

| Key | Type | Purpose |
|---|---|---|
| `voice:calls:{session_id}` | Stream | Per-call event stream |
| `voice:calls:{session_id}:state` | Hash | Live FSM state (fsm_state, collected_fields_json, last_event_id) |
| `voice:calls:{session_id}:audio` | Stream or PubSub | Raw audio frames from ingester → ASR consumer (alternative: direct WebSocket passthrough) |

**Consumer groups to create on first call:**

- `voice:ctrl` — State Controller
- `voice:asr` — ASR Consumer
- `voice:tts` — TTS Consumer
- `voice:llm` — LLM Consumer
- `voice:audit` — Audit Consumer

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Redis down → call fails | State Controller caches current FSM state in memory; can continue call with degraded (no audit) mode. Reconnect on next heartbeat. |
| ASR consumer crashes mid-call | State Controller receives no `asr.transcript` → `timeout.silence` fires → escalate gracefully |
| TTS consumer crashes mid-call | State Controller receives no `tts.complete` → timeout fires → ASR start bypassed → escalate |
| Out-of-order events on stream | XREADGROUP delivers in FIFO order per stream. State Controller processes sequentially per call. No out-of-order risk within a single stream. |
| Audio channel: frames can't go through Redis efficiently (64kbps = ~64KB/s per call) | Audio frames are NOT put on the Redis Stream. The Ingester maintains a direct async channel (asyncio.Queue or WebSocket) to the ASR Consumer. Only control events go on the stream. |
| Multiple State Controller replicas on same call | Consumer groups in Redis guarantee exactly-once delivery per group. Only one ctrl consumer handles a given call's stream entries. |
| Latency: stream events add hops | Measured: XADD → XREADGROUP round trip on local Redis is <1ms. Adds <5ms total per turn. Acceptable. |
| Old and new system writing to same Postgres tables | During parallel run (phases A-C): no conflict — new shadow consumers are read-only. Phase D: new stack writes TranscriptSegments. Old stack disabled for that call. |

---

## What Phase 3 Implementation Looks Like

When approved, implementation order is:

1. **`voice:calls:{session_id}` stream schema** — define all event types and field contracts
2. **Stream Ingester** — refactor `VoiceSessionManager` to thin event emitter; keep VAD, audio conversion
3. **State Controller** — FSM logic, S0→S7, escalation paths; hard-listen enforcement
4. **ASR Consumer** — wrap existing `ASRClient` with event-driven trigger/response
5. **TTS Consumer** — wrap existing `TTSClient` with event-driven trigger/response + Twilio audio write-back
6. **LLM Consumer** — wrap existing `AgentRuntime.generate_response()` with event-driven trigger/response
7. **Audit Consumer** — thin wrapper around existing `call_event_sink` file + Postgres writes
8. **Inbound Workflow Builder updates** — lane config, FSM config fields in frontend
9. **Migration through phases A→E**
