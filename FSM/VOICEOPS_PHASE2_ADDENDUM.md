# VoiceOps Phase 2 Addendum — Pre-Phase-3 Requirements

## Approved with additions. Address these before starting Phase 3 implementation.

---

## Addition 1: Config & Secrets Hygiene (BLOCKING — do before Phase 3)

### Rule: Zero hardcoded values or secrets anywhere in the application.

Audit `config.py` and every file that imports from it. Every value that is currently hardcoded (Redis URLs, API endpoints, model names, ports, timeouts, secrets, tokens) must be driven by `.env` via a settings class.

### Settings reader requirements:

1. Use Pydantic `BaseSettings` with `env_file = '.env'` (you probably already have this — extend it)
2. **Do NOT fail on unknown/extra fields in `.env`.** Set `model_config = SettingsConfigDict(extra='ignore')`. People leave old variables, commented-out experiments, and notes in `.env` files. The settings reader must silently ignore anything it doesn't recognize.
3. **Do NOT fail on missing optional fields.** Every setting must have a sensible default. Only truly required values (like `DATABASE_URL`) should raise on missing. Everything else: default and log a warning at startup, not crash.
4. Group settings logically:
   - `DatabaseSettings` — Postgres connection
   - `RedisSettings` — Redis/Valkey URLs, stream prefixes, consumer group names
   - `TwilioSettings` — account SID, auth token, phone numbers
   - `VoiceSettings` — ASR/TTS endpoints, default models, default voices
   - `LLMSettings` — endpoint, default model, timeout
   - `TelemetrySettings` — log paths, Prometheus port, stream names
5. **Commented-out lines in `.env` (lines starting with `#`) must not cause errors.** This is standard `.env` parser behavior but verify it works.
6. Log all resolved settings at startup (redact secrets — show first 4 chars + `****`). This is your "what's actually running" audit trail.
7. Remove every `os.getenv()` call scattered through the codebase. All env access goes through the settings singleton.

### Deliverable:
- Refactored `config.py` with grouped Pydantic settings
- Updated `.env.example` with every variable, grouped and commented
- Grep confirmation: zero `os.getenv()` or `os.environ` calls outside of `config.py`

---

## Addition 2: FSM Configurator Stub (NON-BLOCKING — stub only, implement later)

The `workflow_dsl.fsm_config` schema in the transition plan is the foundation for a future visual FSM configurator. For now, stub the following:

1. In the Inbound Workflow Builder frontend, add a **collapsed section** labeled "Call flow configuration (advanced)" below the existing fields.
2. Inside: render the `fsm_config` JSON as a read-only code block for now. This proves the config round-trips through the API correctly.
3. Add a comment block in the frontend code: `// FUTURE: Visual FSM configurator — lane editor, field editor, timeout sliders, greeting per-state. See voiceops_inbound_state_machine.svg for reference.`
4. The backend `workflow_dsl` schema must accept and persist the `fsm_config` object as-is. The State Controller reads it at call start.

This is a stub. No visual editor yet. Just prove the config path works end-to-end so we can build the UI later without a backend migration.

---

## Addition 3: Stream event schema contract (BLOCKING — define before Phase 3)

Before writing any consumer code, define the exact JSON schema for every event type on the `voice:calls:{session_id}` stream. Each event must have:

```json
{
  "event_id": "uuid",
  "event_type": "tts.speak | asr.transcript | state.transition | ...",
  "timestamp": "ISO-8601",
  "session_id": "uuid",
  "call_id": "uuid", 
  "payload": { ... event-specific fields ... }
}
```

Create a file `services/backend/app/services/streams/event_schemas.py` with Pydantic models for every event type. All producers and consumers import from this single source of truth. No ad-hoc dict construction anywhere.

Event types to define:
- `call.incoming` — payload: from_number, to_number, agent_id, agent_config snapshot
- `greeting.complete` — payload: greeting_text, duration_ms
- `asr.start_listen` — payload: state, prompted_field (if any)
- `asr.transcript` — payload: text, confidence, duration_ms, is_final
- `llm.extract` — payload: task (name_extract | field_extract), transcript_text, target_fields
- `llm.extracted` — payload: extracted_fields dict, confidence
- `llm.classify` — payload: transcript_text, available_lanes
- `llm.intent` — payload: lane (A|B|C), confidence, fallback_triggered
- `tts.speak` — payload: text, voice, model, state
- `tts.complete` — payload: duration_ms, interrupted (bool)
- `state.transition` — payload: from_state, to_state, trigger_event_id, collected_fields snapshot
- `timeout.silence` — payload: state, elapsed_seconds, action (nudge | escalate)
- `escalate.frustration` — payload: state, trigger_transcript, reason
- `call.ended` — payload: final_state, duration_seconds, outcome, collected_fields
- `audit.log` — payload: full call summary blob

---

## Phase 3 is approved once these three additions are addressed.
