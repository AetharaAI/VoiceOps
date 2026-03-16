# Call Polish Log

This file tracks live-call behavior after the realtime telephony loop became operational.

It exists to preserve known-good checkpoints and make polish work resumable across sessions.

## Checkpoint: First Successful Live Call

- Date: `2026-03-14`
- Status: `success with polish issues`
- Source: operator placed a live outbound call to self from the VoiceOps UI
- Result:
  - call rang and connected
  - agent spoke on the phone
  - live ASR captured caller speech at least partially
  - the agent attempted intake behavior based on configured required fields
  - end-to-end sovereign telephony path is now proven

## Known-Good System State At This Checkpoint

- VoiceOps frontend and backend are running behind NGINX at `voice.aetherpro.us`
- Docker host bindings are loopback-only and expected by the current NGINX proxy setup
- Realtime call path is:
  - `Twilio media stream -> VoiceOps telephony websocket -> Aether Voice realtime ASR -> VoiceOps agent runtime / LLM -> Aether Voice realtime TTS -> Twilio media`
- Aether Voice gateway integration uses:
  - `AETHER_VOICE_HTTP_BASE`
  - `AETHER_VOICE_WS_BASE`
  - realtime ASR session start + websocket stream
  - realtime Kokoro TTS session start + websocket stream

## Operator-Observed Behavior From First Call

- There was a slight pause after answer before the interaction settled.
- The agent asked for the caller's full name.
- The system repeatedly said it did not catch the caller's name and asked again.
- The overall flow worked, but the intake loop was not yet smooth enough for production use.

## Current Likely Polish Targets

1. First-turn timing after answer:
   - reduce awkward pause
   - verify greeting timing versus caller saying "hello"
2. ASR robustness on short answers:
   - names are short, easily missed, and often spoken immediately after the prompt
   - retry logic may currently trigger too aggressively
3. Required-field loop behavior:
   - avoid repetitive "I didn't catch that" loops
   - allow softer recovery phrasing
   - consider confirmation behavior after partial capture
4. Greeting / opening strategy:
   - current opener is backend-generated
   - should likely move to agent-configurable opening behavior
5. Real-call transcript review:
   - inspect actual transcript segments from `/calls`
   - determine whether misses are ASR-side, turn-detection-side, or prompt-timing-side

## Immediate Next Work Session

1. Reproduce with 3-5 additional calls.
2. Inspect saved transcript segments and compare them with what the caller actually said.
3. Tune first-turn handling and retry thresholds.
4. Decide whether to keep hard prompt gating or allow freer first utterances before field enforcement.

## Polish Pass: 2026-03-14 Lock And Polish

### Changes Made

- Replaced the generic first greeting with an opening prompt that immediately asks for the first missing required field.
- Added field-aware intake capture logic for:
  - `name`
  - `phone` / callback number
  - `issue` / service request style fields
- Added retry limits and graceful fallback behavior for missed required fields.
- Reduced turn-finalization delay to make the call feel less paused between speaker turns.
- Added structured call summaries with:
  - `call_id`
  - `timestamp`
  - `duration_seconds`
  - `fields_captured`
  - `missing_fields`
  - `final_disposition`
  - `notable_errors`
- Added deterministic final dispositions:
  - `success`
  - `partial_intake`
  - `failed_intake`
  - `transfer_needed`
- Added call detail exposure for the structured summary in the existing calls UI.
- Preserved the current ASR/TTS service boundaries and did not expand architecture.

### Validation Completed

- Backend/app compile pass succeeded.
- Targeted backend tests passed for:
  - intake prompt / capture behavior
  - spoken-digit phone extraction
  - realtime audio helper path

### Live Retest Status

- Code-level polish pass complete.
- Fresh live-call retest still required after deployment to confirm:
  - fewer repeated retries on caller name
  - smoother first-turn timing
  - cleaner structured summaries on real calls

## Deferred Architecture Idea

- Dual-model orchestration with Redis Streams is intentionally deferred.
- The current priority is to polish the single-agent live call path now that end-to-end telephony is proven.
- Once the base call flow is stable, the second model can be introduced as a background intake / form-fill / planning consumer over streams.
