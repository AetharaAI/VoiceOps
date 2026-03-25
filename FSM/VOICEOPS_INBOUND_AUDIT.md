# VoiceOps Inbound Call Audit

**Audited:** 2026-03-25
**Branch:** main
**Scope:** Full inbound call path — webhook through TTS delivery
**Method:** Direct source reading of all files in the inbound call path. No guessing.

---

## 1. Twilio Webhook Handler

**File:** [`services/backend/app/api/routes/webhooks.py`](services/backend/app/api/routes/webhooks.py)
**Function:** `inbound_call()` — POST `/webhooks/telephony/inbound` (line 22)

**Call entry sequence:**

1. Twilio POSTs form data: `From`, `To`, `CallSid`, plus metadata fields (`CallerName`, `StirVerstat`, etc.)
2. `build_inbound_webhook_payload()` parses and normalizes the form — produces `InboundWebhookPayload`
3. If `?call_id=` query param is present: this is a callback on an existing outbound call — existing `Call` record is reused and updated
4. Otherwise (new inbound call): `resolve_inbound_agent()` is called to determine which agent handles the call (see §8 for routing details)
5. A new `Call` record is created in Postgres with:
   - `direction = inbound`, `status = ringing`
   - `from_number`, `to_number`, `external_call_id` (= Twilio CallSid)
   - `context_payload.telephony` with resolution metadata, webhook payload, correlation_id, timestamps
6. A TwiML `<Connect><Stream url="wss://..."/>` response is returned to Twilio
7. **Nothing audio-related happens at this point.** The webhook only creates the record and hands off to WebSocket.

The WebSocket URL format is: `wss://{PUBLIC_BASE_URL}/api/v1/ws/telephony/{call_id}`

WebSocket handler: `telephony_ws()` (line 405) — delegates immediately to `session_manager.handle_ws()`

---

## 2. Greeting Flow

**File:** [`services/backend/app/services/realtime/session_manager.py`](services/backend/app/services/realtime/session_manager.py)
**Functions:** `handle_ws()` (line 1169), `send_tts()` (line 263)

**Greeting source:**

The greeting is **always a fixed TTS string** — never LLM-generated. It is determined in `agent_runtime.build_opening_prompt()` ([`runtime.py`](services/backend/app/services/agent_runtime/runtime.py), line 146):

```python
def build_opening_prompt(self, *, agent: Agent, collected_fields: dict) -> AgentTurn:
    custom_greeting = self.opening_greeting_for_agent(agent=agent)
    # opening_greeting comes from agent.policy_config.runtime.opening_greeting
    if custom_greeting:
        response_text = custom_greeting
    else:
        response_text = f'Hello, this is {agent.name}. How can I help today?'
    return AgentTurn(response_text=response_text, llm_mode='scripted', response_source='scripted_greeting')
```

**Trigger:** Greeting fires when Twilio sends the `start` event on the WebSocket (`handle_ws()` line 1246). This is the first event after stream setup.

**What happens after greeting:**

```python
# session_manager.py line 1281
await self.send_tts(websocket, session, agent, opening_turn.response_text, ...)
await db.commit()
# --- loop immediately continues to next event ---
```

`send_tts()` does NOT await TTS completion. It creates a background asyncio task:

```python
# session_manager.py line 408
session.tts_task = asyncio.create_task(_stream())
```

The main WebSocket event loop immediately returns to `while True:` and begins processing `media` events. **The system does not wait for the greeting TTS to finish before entering the listening state.** There is no "yield after greeting" transition.

---

## 3. ASR Integration

**File:** [`services/backend/app/services/asr/client.py`](services/backend/app/services/asr/client.py)
**Integration model:** Streaming WebSocket to Aether Voice ASR API

**Audio path:**

```
Twilio media event (base64 μ-law, 8kHz, 160 bytes/frame, 20ms per frame)
  → base64 decode
  → mulaw_to_pcm16() → PCM16 @ 8kHz
  → webrtcvad.Vad.is_speech() (VAD mode 2)
  → resample_pcm16() → PCM16 @ 16kHz
  → ASRStream.send_audio_frame() → base64-encoded JSON → ASR WebSocket
```

**ASR start condition:**

In `process_audio_frame()` (line 1093), when `not session.caller_turn_active`:
- Each frame is tested with VAD
- If `consecutive_voiced_frames >= MIN_SPEECH_FRAMES` (= **2 frames = 40ms**): `_start_asr_turn()` is called
- Pre-speech frames (last 10) are immediately flushed to the ASR stream to avoid clipping the beginning of speech

**ASR end condition:**

When `session.caller_turn_active`:
- All frames are forwarded to ASR regardless of VAD result
- Silence frames are counted: `consecutive_silence_frames`
- When `consecutive_silence_frames >= END_OF_TURN_SILENCE_FRAMES` (= **30 frames = 600ms**): `finalize_caller_turn()` is called

**What happens after transcript:**

`finalize_caller_turn()` (line 980):
1. Calls `stream.end_stream()` → signals ASR to finalize
2. Awaits `stream.wait_for_final(timeout=5.0)` — blocks until ASR returns final transcript
3. If transcript is empty or ASR errors: `_recover_missing_field()` → fires recovery TTS
4. If transcript has content: persists `TranscriptSegment`, then calls `agent_runtime.generate_response()`
5. Response goes to `_handle_agent_turn()` → `send_tts()` → TTS task fires

---

## 4. LLM Integration

**File:** [`services/backend/app/services/agent_runtime/runtime.py`](services/backend/app/services/agent_runtime/runtime.py)
**Function:** `generate_response()` (line 264)

**When LLM is called:** After every successful ASR transcript in `finalize_caller_turn()`.

**Decision tree inside `generate_response()`:**
1. Escalation check: if transcript contains `{'lawyer', 'sue', 'cancel now', 'human', 'manager', 'angry'}` → immediate scripted escalation response, no LLM call
2. `capture_required_fields()`: regex/heuristic extraction of name, phone, issue from transcript
3. If `llm_provider in {'api', 'openai'}` and `llm_endpoint` is set: LLM call is made
4. Otherwise: scripted fallback (prompt next missing field, or generic "How can I help?")

**LLM system prompt** (built by `build_llm_system_prompt()`, line 180):

```python
f'{agent.persona}\n\n'
f'Script: {agent.script}\n'
f'Policy: {agent.policy_config}\n'
f'Context: {context}\n'  # = call.context_payload
f'Detected intent: {detected_intent}\n'
f'Collected fields: {collected_fields}\n'
f'Missing required fields: {missing_fields}\n'
f'Current extraction target: {active_field}\n\n'
'You are responding on a live phone call. Speak naturally, briefly, and conversationally.\n'
...
'Return only the exact spoken reply text for the next turn.'
```

**LLM controls conversation flow?** No. The LLM is a response generator only. It produces a text string. All flow control (turn-taking, field tracking, retry logic, escalation, session lifecycle) is handled by the `VoiceSessionManager`. The LLM has no loop control, no memory of conversation history (no `messages` array — only system prompt + single user utterance per call). If LLM is unconfigured or fails, scripted fallback takes over silently.

**Provider config:** `agent.policy_config.runtime.llm_provider` (default `'openai'`), `agent.policy_config.runtime.llm_model` (default `'omnicoder'`), endpoint from `settings.llm_endpoint`. Calls are synchronous HTTP via `httpx.AsyncClient(timeout=25)`.

---

## 5. TTS Integration

**File:** [`services/backend/app/services/tts/client.py`](services/backend/app/services/tts/client.py)

**TTS service:** Aether Voice API, Kokoro realtime model
**Default model:** `kokoro_realtime`
**Default voice:** `af_bella`
**Config:** Per-agent via `agent.policy_config.runtime.{tts_model, tts_voice, tts_provider}`

**Audio return path:**

```
TTS service → WebSocket → WAV chunks
  → wav_to_pcm16() + resample_pcm16() → PCM16 @ 8kHz
  → pcm16_to_mulaw() → μ-law 8kHz
  → base64 encode → Twilio media event (640 bytes/chunk)
  → sent via websocket.send_json()
```

After all chunks: Twilio mark event `{event: 'mark', mark: {name: 'tts_done'}}` is sent. This is a log marker only — there is no callback, no state transition triggered by receiving the mark ACK.

**Guard against TTS firing during ASR listening?**

There is no hard guard. The `session.speaking` flag is set `True` while TTS streams and `False` when done. When `process_audio_frame()` is called and `not session.caller_turn_active`, if VAD fires → `_start_asr_turn()` is called → which checks `session.speaking` and calls `stop_tts_for_barge_in()` if True. This is the **barge-in mechanism** — it cancels TTS when the caller speaks. There is no mechanism that prevents the ASR + LLM + TTS pipeline from firing while a different TTS is still playing, other than this cancellation path.

---

## 6. Turn-Taking

**No explicit state machine exists.** Turn-taking is controlled by two boolean flags on `VoiceSession`:

| Flag | Meaning | Set True | Set False |
|---|---|---|---|
| `session.speaking` | TTS is streaming | `send_tts()` → `_stream()` starts | `_stream()` finally block completes |
| `session.caller_turn_active` | ASR stream is open | `_start_asr_turn()` | `finalize_caller_turn()` |

**Flow within a single turn:**

```
VAD fires → _start_asr_turn() [caller_turn_active=True, asr_stream opened]
  → frames forwarded to ASR
  → 30 silence frames → finalize_caller_turn() [caller_turn_active=False, asr_stream closed]
    → wait for ASR final transcript (up to 5s)
    → generate_response() [LLM call, up to 25s]
    → _handle_agent_turn() → send_tts() [speaking=True, tts_task=create_task]
    → return (finalize_caller_turn returns)
      → media frames still arrive, VAD runs, no ASR turn active yet
      → when caller speaks → barge-in OR (if TTS done) new ASR turn starts
```

**The pipeline inside `finalize_caller_turn()` is sequential:** ASR finalization → LLM → TTS launch. It is awaited from `process_audio_frame()` at line 1143, which means no other media frames are processed during the LLM call. Once TTS is launched as a task and `finalize_caller_turn()` returns, the media loop resumes.

**No silence timeout after TTS finishes.** If the caller never speaks after an agent turn, nothing happens. The `INITIAL_DEAD_AIR_SECONDS = 6` check only logs a telemetry anomaly — it does not trigger any recovery action.

---

## 7. Redis Usage

**File:** [`services/backend/app/services/telephony/event_sink.py`](services/backend/app/services/telephony/event_sink.py)
**Config:** [`services/backend/app/core/config.py`](services/backend/app/core/config.py)

Redis is used **exclusively for event logging and observability** — not for session state, turn-taking, routing, or coordination.

**Current Redis streams:**

| Stream key | Content |
|---|---|
| `voiceops:call_events` | All events (every event type) |
| `voiceops:call_transcripts` | Events prefixed `transcript.*` only |
| `voiceops:call_extractions` | Events of type `call.extraction.ready` |
| `voiceops:call_actions` | Events of type `call.action.ready` |

**Publishing:** Fire-and-forget via `loop.create_task(self._publish_to_streams(event))`. Failures are logged as warnings and silently discarded. Publishing is gated by `settings.redis_streams_enabled`.

**No consumer groups exist** in the current codebase. Nothing reads from these streams.

**What Redis is NOT used for (currently):**
- Session state (lives in `VoiceSession` dataclass, in-memory per process)
- Routing decisions (Postgres query in `resolve_inbound_agent()`)
- Turn-taking coordination (boolean flags on in-memory session)
- Per-call Redis keys (none exist)

---

## 8. Inbound Workflow Config

**Frontend:** [`services/frontend/app/inbound/page.js`](services/frontend/app/inbound/page.js)

**UI fields and their storage:**

| UI Field | Stored in |
|---|---|
| Agent Name | `agent.name` |
| Opening Greeting (TTS text) | `agent.policy_config.runtime.opening_greeting` |
| Business Context (persona) | `agent.persona` AND `agent.workflow_dsl.inbound_builder.business_context` |
| Operator Goal (script) | `agent.script` AND `agent.workflow_dsl.inbound_builder.goal` |
| Assigned Model (LLM) | `agent.policy_config.runtime.llm_model` |
| TTS Lane (model) | `agent.policy_config.runtime.tts_model` |
| Voice | `agent.policy_config.runtime.tts_voice` |
| Required Fields (JSON) | `agent.required_fields` |
| Action Config (JSON) | `agent.tools_config` AND `agent.workflow_dsl.inbound_builder.action_config` |
| CRM Mapping (JSON) | `agent.workflow_dsl.inbound_builder.crm_mapping` |
| Assigned Phone Number | `PhoneNumber.agent_id` FK |

**How config is loaded during a live call:**

1. `handle_ws()` runs a Postgres query for the `Agent` by `call.agent_id` (line 1177)
2. The full `Agent` ORM object is passed to every runtime function throughout the call
3. `agent_runtime.opening_greeting_for_agent()` reads `agent.policy_config.runtime.opening_greeting`
4. `agent_runtime.tts_voice_for_agent()` / `tts_model_for_agent()` read from `agent.policy_config.runtime`
5. `agent_runtime.build_llm_system_prompt()` reads `agent.persona`, `agent.script`, `agent.policy_config`
6. `_inbound_builder_config()` reads `agent.workflow_dsl.inbound_builder` for crm_mapping, action_config at call end
7. `agent.required_fields` drives field extraction and prompt selection throughout the call

The `greeting_mode` field is stored in `agent.workflow_dsl.inbound_builder.greeting_mode` but is **not currently read by the runtime** — the system always uses fixed TTS regardless of this setting.

---

## 9. Session Lifecycle

**Per-call data captured:**

**In-memory (VoiceSession, lost if process crashes):**
- `session_id` (UUID), `call_id`, `tenant_id`
- `collected_fields` (dict of extracted field values)
- `prompted_field`, `field_retry_counts`
- `notable_errors`, `caller_turns`, `agent_turns`
- `llm_mode`, `detected_intent`, `last_response_source`
- `last_asr_partial`, `last_asr_final`, `last_recovery_prompt`
- `telemetry: CallTelemetry` (timestamped event log, latency snapshots)

**Persisted to Postgres:**
- `Call` record: status transitions, outcome, escalation_reason, started_at, ended_at
- `Call.outcome_tags`: the full call summary dict (written at call end by `_finalize_call_summary()`)
- `TranscriptSegment` records: one per caller/agent/dtmf turn, with speaker, text, is_final, started_ms, ended_ms

**Persisted to filesystem:**
- `.jsonl` files in `logs/calls/{YYYY-MM-DD}/` — one file per call
- Filename: `{direction}-{phone_fragment}-{call_sid}-{timestamp}.jsonl`
- Append-only, one JSON event per line, flushed on every write
- Events: all webhook events, telemetry marks, transcript events, LLM request start/end, TTS events, call.summary.final at end

**Persisted to Redis Streams:**
- All events published to `voiceops:call_events` and type-specific streams as fire-and-forget

**Session end trigger:** Twilio sends `stop` event → `_drain_active_turn()` → `_finalize_call_summary()` → `close_call()` (flushes and closes `.jsonl` file) → `self.sessions.pop(call_id)`. Or on exception: same cleanup in finally block, status set to `failed`.

---

## 10. Known Bug: System Talks Over the Caller

**Reported behavior:** After the greeting plays, the system does not properly yield to listen for the caller's response — it talks over them.

**Root cause: the greeting TTS is non-blocking and the VAD runs immediately on incoming audio with no TTS-completion guard.**

### Specific code path

**Step 1 — Greeting fires as a background task:**

```python
# session_manager.py line 1281
await self.send_tts(websocket, session, agent, opening_turn.response_text, ...)
# send_tts() → asyncio.create_task(_stream())  ← non-blocking, returns immediately
await db.commit()
# Main loop continues to next event ← greeting TTS is running concurrently
```

**Step 2 — Media frames arrive immediately from Twilio:**

Twilio begins streaming audio frames from the moment the WebSocket stream starts. Frames arrive during and after TTS playback. Each frame goes through `process_audio_frame()`.

**Step 3 — VAD fires too early (2-frame threshold = 40ms):**

```python
# session_manager.py line 1122–1127
if not session.caller_turn_active:
    session.pre_speech_frames.append(frame_mulaw)
    if is_speech:
        session.consecutive_voiced_frames += 1
        if session.consecutive_voiced_frames >= MIN_SPEECH_FRAMES:  # = 2 frames
            await self._start_asr_turn(session=session, websocket=websocket)
```

`MIN_SPEECH_FRAMES = 2` means **40ms of detected audio** triggers ASR start. This fires on:
- Line noise / packet artifacts during TTS
- The caller speaking in response to the greeting while TTS is still playing (barge-in)
- Any audio transient in the first moments of the stream

**Step 4 — `_start_asr_turn()` cancels the TTS (barge-in):**

```python
# session_manager.py line 410–412
async def _start_asr_turn(self, *, session, websocket):
    if session.speaking:
        await self.stop_tts_for_barge_in(websocket, session)
    # ... opens ASR stream
```

The greeting TTS is cancelled mid-play. The system is now in ASR listening mode.

**Step 5 — Silence detection fires after 600ms (`END_OF_TURN_SILENCE_FRAMES = 30`):**

After the barge-in, if the caller pauses or if the captured audio was a transient (not real speech), 30 silence frames (600ms) trigger `finalize_caller_turn()`. The transcript is typically empty or partial.

**Step 6 — Empty transcript → immediate recovery TTS:**

```python
# session_manager.py line 1023–1036
if not transcript or not transcript.text.strip():
    await self._recover_missing_field(
        ...
        retry_reason=self._retry_reason_from_transcript(session=session, transcript_text=''),
        ...
    )
    return
```

`_recover_missing_field()` fires a TTS recovery prompt ("I didn't hear anything there. Could you...") — **while the caller is still actively trying to respond to the greeting.**

**Step 7 — The cycle repeats:**

Each recovery TTS again fires as a non-blocking task. VAD fires on the next transient. Another barge-in. Another empty transcript. Another recovery prompt. The system and the caller end up speaking over each other indefinitely.

### Secondary contributing factor

Even in the non-barge-in case (caller waits silently for TTS to finish), there is **no post-TTS silence timeout**. The system never proactively re-prompts the caller. If the caller speaks after a natural pause but the 600ms VAD silence threshold fires during a mid-sentence pause, `finalize_caller_turn()` runs on a partial utterance, producing a partial or low-confidence transcript → recovery TTS.

### Summary of the bug

| Root cause | Location |
|---|---|
| TTS fires as `create_task` (non-blocking) — loop continues immediately | `send_tts()` line 408 |
| VAD threshold is 2 frames (40ms) — fires on any transient | `MIN_SPEECH_FRAMES = 2`, line 37 |
| No check: "am I playing the greeting? do not start ASR yet" | `process_audio_frame()` line 1122 |
| Silence threshold is 600ms — fires on any mid-sentence pause | `END_OF_TURN_SILENCE_FRAMES = 30`, line 38 |
| No post-TTS yield: no mechanism to transition from "TTS done" to "now listen" | entire `handle_ws()` loop |
| No hard listen guarantee: TTS can fire at any point in the pipeline | `send_tts()` has no guard for "am I in listening state?" |

---

## File Index (Inbound Call Path)

| File | Role |
|---|---|
| [`services/backend/app/api/routes/webhooks.py`](services/backend/app/api/routes/webhooks.py) | Twilio webhook + WebSocket route handler |
| [`services/backend/app/services/telephony/inbound_routing.py`](services/backend/app/services/telephony/inbound_routing.py) | Agent resolution, phone number normalization |
| [`services/backend/app/services/realtime/session_manager.py`](services/backend/app/services/realtime/session_manager.py) | Main WebSocket handler, all turn logic, VAD, barge-in |
| [`services/backend/app/services/realtime/audio.py`](services/backend/app/services/realtime/audio.py) | μ-law/PCM conversion, resampling, WAV parsing |
| [`services/backend/app/services/agent_runtime/runtime.py`](services/backend/app/services/agent_runtime/runtime.py) | LLM calls, greeting, field extraction, recovery prompts |
| [`services/backend/app/services/asr/client.py`](services/backend/app/services/asr/client.py) | Aether Voice ASR WebSocket client |
| [`services/backend/app/services/tts/client.py`](services/backend/app/services/tts/client.py) | Aether Voice TTS WebSocket client |
| [`services/backend/app/services/telephony/event_sink.py`](services/backend/app/services/telephony/event_sink.py) | Redis Streams + file event logging |
| [`services/backend/app/services/telephony/telemetry.py`](services/backend/app/services/telephony/telemetry.py) | CallTelemetry: timestamped in-call event log |
| [`services/backend/app/models/models.py`](services/backend/app/models/models.py) | Call, Agent, TranscriptSegment ORM models |
| [`services/backend/app/core/config.py`](services/backend/app/core/config.py) | Settings: Redis URLs, TTS/ASR/LLM config, stream names |
| [`services/frontend/app/inbound/page.js`](services/frontend/app/inbound/page.js) | Inbound Workflow Builder UI |
| [`services/frontend/lib/operator-builder.js`](services/frontend/lib/operator-builder.js) | Shared form helpers, voice options, model options |
