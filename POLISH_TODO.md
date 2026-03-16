# Polish TODO

Live-call polish only. No architecture expansion.

## Current Focus

1. Run repeat live calls and verify the first-turn intake is smoother after the field-aware retry changes.
2. Confirm the agent now captures `name`, `phone`, and `issue/service_request` with fewer repeated prompts.
3. Inspect call summaries in `/calls` and verify:
   - `final_disposition`
   - `fields_captured`
   - `missing_fields`
   - `notable_errors`
4. Check whether the shortened end-of-turn silence threshold feels natural on real phone audio.
5. Verify status callbacks do not overwrite `escalated` / transfer-oriented terminal states.

## If Problems Remain

1. Tune short-answer capture for names:
   - especially one-word first names
   - especially immediate post-greeting responses
2. Tune phone capture if ASR returns number words inconsistently.
3. Soften fallback language if retries still sound robotic.
4. Decide whether the opening prompt should remain backend-generated or move into explicit agent configuration.

## Explicitly Deferred

1. Redis Streams dual-model orchestration
2. New routing systems
3. New UI design work unrelated to call debugging
4. ASR/TTS boundary changes
