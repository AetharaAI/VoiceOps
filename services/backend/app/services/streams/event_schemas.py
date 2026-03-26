"""
VoiceOps FSM — Redis Stream Event Schema Contract
=================================================

Single source of truth for all event types on the per-call stream:
    voice:calls:{session_id}

Every producer and consumer imports from here. No ad-hoc dict construction.

Wire format
-----------
Events are serialized with .model_dump_json() and stored as a single Redis
Stream field `data`. The stream entry therefore looks like:

    XADD voice:calls:{session_id} * data <json>

Consumers do:
    raw = entry['data']
    event = FSMEvent.model_validate_json(raw)
    typed = FSMEvent.to_typed(event)

Event hierarchy
---------------
All events share the FSMEvent base envelope. The `event_type` discriminates
which Payload subclass to use. Call FSMEvent.to_typed(base) to get a
strongly-typed event with the correct payload model.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Base envelope — every event on the stream uses this shape
# ---------------------------------------------------------------------------

class FSMEventBase(BaseModel):
    event_id: str = Field(default_factory=_new_id)
    event_type: str
    timestamp: str = Field(default_factory=_now_iso)
    session_id: str
    call_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Payload models — one per event_type
# ---------------------------------------------------------------------------

class CallIncomingPayload(BaseModel):
    """S0 entry: Twilio webhook received, agent resolved."""
    from_number: str
    to_number: str
    call_sid: str
    agent_id: str
    tenant_id: str
    resolution_source: str                  # phone_number_mapping | tenant_fallback | global_fallback
    agent_config_snapshot: dict[str, Any]   # snapshot of agent.policy_config.runtime at call start
    correlation_id: str = ''


class GreetingCompletePayload(BaseModel):
    """TTS finished playing the opening greeting (S1 → hard listen)."""
    greeting_text: str
    duration_ms: int | None = None
    interrupted: bool = False               # True if barge-in occurred


class ASRStartListenPayload(BaseModel):
    """State Controller command: open ASR stream and begin listening."""
    fsm_state: str                          # current FSM state label (S1, S2, ...)
    prompted_field: str | None = None       # field we are trying to capture, if any
    timeout_seconds: float = 8.0            # silence timeout for this listen window


class ASRTranscriptPayload(BaseModel):
    """ASR transcript event (partial or final) for the current caller turn."""
    text: str
    confidence: float | None = None
    duration_ms: int | None = None
    started_ms: int | None = None
    ended_ms: int | None = None
    is_final: bool = True
    asr_session_id: str = ''


class LLMExtractPayload(BaseModel):
    """State Controller command: extract structured fields from transcript."""
    task: Literal['name_extract', 'field_extract', 'generic_extract']
    transcript_text: str
    target_fields: list[str]                # field names we are trying to extract
    fsm_state: str
    context_snapshot: dict[str, Any] = Field(default_factory=dict)


class LLMExtractedPayload(BaseModel):
    """LLM consumer returned extracted field values."""
    extracted_fields: dict[str, str]        # field_name → value
    confidence: float | None = None
    task: str = ''
    fallback_triggered: bool = False
    fallback_reason: str | None = None


class LLMClassifyPayload(BaseModel):
    """State Controller command: classify caller intent into a lane."""
    transcript_text: str
    available_lanes: list[str]              # ['A', 'B', 'C']
    fsm_state: str
    context_snapshot: dict[str, Any] = Field(default_factory=dict)


class LLMIntentPayload(BaseModel):
    """LLM consumer returned lane classification."""
    lane: str                               # 'A' | 'B' | 'C' | 'unknown'
    confidence: float | None = None
    fallback_triggered: bool = False
    fallback_reason: str | None = None
    raw_response: str = ''


class TTSSpeakPayload(BaseModel):
    """State Controller command: synthesize and play text via TTS."""
    text: str
    voice: str
    model: str
    fsm_state: str
    tts_request_id: str = Field(default_factory=_new_id)
    response_source: str = 'fsm_state_controller'  # scripted_greeting | llm_response | recovery_prompt | ...


class TTSCompletePayload(BaseModel):
    """TTS consumer finished streaming audio for a tts.speak command."""
    tts_request_id: str
    duration_ms: int | None = None
    interrupted: bool = False               # True if barge-in cancelled this TTS
    error: str | None = None               # set if TTS failed


class StateTransitionPayload(BaseModel):
    """FSM moved from one state to another."""
    from_state: str
    to_state: str
    trigger_event_id: str                   # event_id that triggered the transition
    trigger_event_type: str
    collected_fields_snapshot: dict[str, str] = Field(default_factory=dict)
    reason: str = ''


class TimeoutSilencePayload(BaseModel):
    """No caller speech detected within the listen window."""
    fsm_state: str
    elapsed_seconds: float
    prompted_field: str | None = None
    action: Literal['nudge', 'escalate']    # nudge = play recovery prompt; escalate = transfer
    retry_count: int = 0


class EscalateFrustrationPayload(BaseModel):
    """LLM or heuristic detected caller frustration."""
    fsm_state: str
    trigger_transcript: str
    reason: str                             # sensitive_keyword | repeated_failure | explicit_request
    escalation_type: Literal['warm_transfer', 'voicemail', 'callback'] = 'warm_transfer'


class CallEndedPayload(BaseModel):
    """Call terminated — final state recorded."""
    final_state: str
    duration_seconds: float | None = None
    outcome: str                            # success | partial_intake | failed_intake | escalated | error
    collected_fields: dict[str, str] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    notable_errors: list[str] = Field(default_factory=list)
    escalation_reason: str | None = None


class AuditLogPayload(BaseModel):
    """Full call audit blob — written at call end by audit consumer."""
    call_id: str
    session_id: str
    tenant_id: str
    agent_id: str
    direction: str
    from_number: str
    to_number: str
    started_at: str
    ended_at: str
    duration_seconds: float | None = None
    final_state: str
    outcome: str
    collected_fields: dict[str, str] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    notable_errors: list[str] = Field(default_factory=list)
    caller_turns: int = 0
    agent_turns: int = 0
    llm_mode: str = ''
    detected_intent: str = ''
    escalation_reason: str | None = None
    telemetry_snapshot: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Typed event wrappers — one per event_type, for consumer pattern-matching
# ---------------------------------------------------------------------------

class CallIncomingEvent(FSMEventBase):
    event_type: Literal['call.incoming'] = 'call.incoming'
    payload: CallIncomingPayload


class GreetingCompleteEvent(FSMEventBase):
    event_type: Literal['greeting.complete'] = 'greeting.complete'
    payload: GreetingCompletePayload


class ASRStartListenEvent(FSMEventBase):
    event_type: Literal['asr.start_listen'] = 'asr.start_listen'
    payload: ASRStartListenPayload


class ASRTranscriptEvent(FSMEventBase):
    event_type: Literal['asr.transcript'] = 'asr.transcript'
    payload: ASRTranscriptPayload


class LLMExtractEvent(FSMEventBase):
    event_type: Literal['llm.extract'] = 'llm.extract'
    payload: LLMExtractPayload


class LLMExtractedEvent(FSMEventBase):
    event_type: Literal['llm.extracted'] = 'llm.extracted'
    payload: LLMExtractedPayload


class LLMClassifyEvent(FSMEventBase):
    event_type: Literal['llm.classify'] = 'llm.classify'
    payload: LLMClassifyPayload


class LLMIntentEvent(FSMEventBase):
    event_type: Literal['llm.intent'] = 'llm.intent'
    payload: LLMIntentPayload


class TTSSpeakEvent(FSMEventBase):
    event_type: Literal['tts.speak'] = 'tts.speak'
    payload: TTSSpeakPayload


class TTSCompleteEvent(FSMEventBase):
    event_type: Literal['tts.complete'] = 'tts.complete'
    payload: TTSCompletePayload


class StateTransitionEvent(FSMEventBase):
    event_type: Literal['state.transition'] = 'state.transition'
    payload: StateTransitionPayload


class TimeoutSilenceEvent(FSMEventBase):
    event_type: Literal['timeout.silence'] = 'timeout.silence'
    payload: TimeoutSilencePayload


class EscalateFrustrationEvent(FSMEventBase):
    event_type: Literal['escalate.frustration'] = 'escalate.frustration'
    payload: EscalateFrustrationPayload


class CallEndedEvent(FSMEventBase):
    event_type: Literal['call.ended'] = 'call.ended'
    payload: CallEndedPayload


class AuditLogEvent(FSMEventBase):
    event_type: Literal['audit.log'] = 'audit.log'
    payload: AuditLogPayload


# ---------------------------------------------------------------------------
# Union type for deserialization dispatch
# ---------------------------------------------------------------------------

AnyFSMEvent = Annotated[
    Union[
        CallIncomingEvent,
        GreetingCompleteEvent,
        ASRStartListenEvent,
        ASRTranscriptEvent,
        LLMExtractEvent,
        LLMExtractedEvent,
        LLMClassifyEvent,
        LLMIntentEvent,
        TTSSpeakEvent,
        TTSCompleteEvent,
        StateTransitionEvent,
        TimeoutSilenceEvent,
        EscalateFrustrationEvent,
        CallEndedEvent,
        AuditLogEvent,
    ],
    Field(discriminator='event_type'),
]


# ---------------------------------------------------------------------------
# Factory helpers — build typed events with correct defaults
# ---------------------------------------------------------------------------

def make_event(
    event_cls: type,
    *,
    session_id: str,
    call_id: str,
    payload: BaseModel,
) -> FSMEventBase:
    """Construct a typed FSM event ready for XADD."""
    return event_cls(
        session_id=session_id,
        call_id=call_id,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# All event type literals — useful for consumer subscription filtering
# ---------------------------------------------------------------------------

ALL_EVENT_TYPES: frozenset[str] = frozenset({
    'call.incoming',
    'greeting.complete',
    'asr.start_listen',
    'asr.transcript',
    'llm.extract',
    'llm.extracted',
    'llm.classify',
    'llm.intent',
    'tts.speak',
    'tts.complete',
    'state.transition',
    'timeout.silence',
    'escalate.frustration',
    'call.ended',
    'audit.log',
})

# Events that ONLY the State Controller may emit
STATE_CONTROLLER_COMMANDS: frozenset[str] = frozenset({
    'tts.speak',
    'asr.start_listen',
    'state.transition',
})

# Events that trigger State Controller processing
STATE_CONTROLLER_TRIGGERS: frozenset[str] = frozenset({
    'call.incoming',
    'greeting.complete',
    'asr.transcript',
    'llm.extracted',
    'llm.intent',
    'tts.complete',
    'timeout.silence',
    'escalate.frustration',
    'call.ended',
})
