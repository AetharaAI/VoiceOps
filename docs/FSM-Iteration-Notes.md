# FSM Iteration Notes

## Purpose
Quick handoff notes for ongoing tuning of the 7-state inbound conversation flow.

## Where To Look
- FSM controller: `services/backend/app/services/state_controller/controller.py`
- FSM tests: `services/backend/tests/test_state_controller.py`
- Working call logs: `logs/working-logs-*.md`
- Known strong baseline log: `logs/working-logs-0.9_1st_Near-100%.md`

## Current Known Behavior
- Main intake path (greeting -> name/intent capture) is stable enough for demo use.
- Remaining friction point has been S6 readback confirmation (yes/no gate), especially callers talking naturally while/after prompt.

## Recent Needle Moves
1. Empty transcript anti-talkover guard (global FSM)
- Added early-empty grace handling to avoid immediate recovery speech on quick empty ASR finals.
- Current tuning:
  - `EARLY_EMPTY_GRACE_SECONDS = 8.0`
  - `MAX_EARLY_EMPTY_SILENT_RETRIES = 5`
- Goal: prevent "I didn't hear anything" from stepping on caller responses.

2. S6 confirmation natural language handling
- Added semantic confirmation classification with deny-first precedence.
- Accepts natural affirm phrases (for example: "yeah everything looks good", "sounds good", "all good", "good to go").
- Handles natural deny/edit phrases (for example: "need to change", "not correct", "different").
- Deny-first prevents accidental pass-through on mixed text such as: "yeah but I need to change one thing".

## Important Product Rules
- No hard-coded single-word gates where natural phrasing is expected.
- Keep the flow deterministic at state boundaries but conversational inside turns.
- Treat repeated no-progress loops as a tuning signal, not a caller failure.

## Suggested Logging Discipline
- Keep sequential files: `working-logs-1.4.md`, `working-logs-1.5.md`, etc.
- For each run, note:
  - number called (main/demo)
  - model + TTS lane + voice
  - where talk-over occurred (state)
  - exact phrase caller said
  - whether gate passed, retried, or misclassified

## Open Items
- Validate latest S6 confirmation behavior on both numbers with fresh logs.
- If S6 still feels tight, next tuning lever is additional post-readback listening slack before recovery prompting.
