"""
Tests for the FSM stream event schema contract.

Validates:
- Every event type round-trips through serialization (model_dump_json → model_validate_json)
- Discriminated union dispatches to the correct typed class
- make_event() factory produces valid events
- Required fields are enforced; optional fields default correctly
- ALL_EVENT_TYPES, STATE_CONTROLLER_COMMANDS, STATE_CONTROLLER_TRIGGERS are complete
- No two event types share the same literal string
"""

import json
import uuid
from typing import get_args

import pytest

from app.services.streams.event_schemas import (
    ALL_EVENT_TYPES,
    STATE_CONTROLLER_COMMANDS,
    STATE_CONTROLLER_TRIGGERS,
    AnyFSMEvent,
    ASRStartListenEvent,
    ASRStartListenPayload,
    ASRTranscriptEvent,
    ASRTranscriptPayload,
    AuditLogEvent,
    AuditLogPayload,
    CallEndedEvent,
    CallEndedPayload,
    CallIncomingEvent,
    CallIncomingPayload,
    EscalateFrustrationEvent,
    EscalateFrustrationPayload,
    FSMEventBase,
    GreetingCompleteEvent,
    GreetingCompletePayload,
    LLMClassifyEvent,
    LLMClassifyPayload,
    LLMExtractedEvent,
    LLMExtractedPayload,
    LLMExtractEvent,
    LLMExtractPayload,
    LLMIntentEvent,
    LLMIntentPayload,
    StateTransitionEvent,
    StateTransitionPayload,
    TimeoutSilenceEvent,
    TimeoutSilencePayload,
    TTSCompleteEvent,
    TTSCompletePayload,
    TTSSpeakEvent,
    TTSSpeakPayload,
    make_event,
)

SESSION_ID = str(uuid.uuid4())
CALL_ID = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def roundtrip(event: FSMEventBase) -> FSMEventBase:
    """Serialize then deserialize via the discriminated union."""
    raw = event.model_dump_json()
    return _validate_any(raw)


def _validate_any(raw: str) -> FSMEventBase:
    """Deserialize raw JSON through the AnyFSMEvent discriminated union."""
    from pydantic import TypeAdapter
    adapter = TypeAdapter(AnyFSMEvent)
    return adapter.validate_json(raw)


def _make(event_cls, payload):
    return make_event(event_cls, session_id=SESSION_ID, call_id=CALL_ID, payload=payload)


# ---------------------------------------------------------------------------
# Base envelope
# ---------------------------------------------------------------------------

def test_base_envelope_defaults_populated():
    event = CallIncomingEvent(
        session_id=SESSION_ID,
        call_id=CALL_ID,
        payload=CallIncomingPayload(
            from_number='+18125550100',
            to_number='+18129691371',
            call_sid='CA123',
            agent_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            resolution_source='phone_number_mapping',
            agent_config_snapshot={},
        ),
    )
    assert event.event_id  # auto-generated uuid
    assert event.timestamp  # auto-generated ISO timestamp
    assert event.event_type == 'call.incoming'
    assert event.session_id == SESSION_ID
    assert event.call_id == CALL_ID


def test_base_envelope_custom_event_id():
    fixed_id = str(uuid.uuid4())
    event = CallIncomingEvent(
        event_id=fixed_id,
        session_id=SESSION_ID,
        call_id=CALL_ID,
        payload=CallIncomingPayload(
            from_number='+1', to_number='+1', call_sid='CA1',
            agent_id='a', tenant_id='t',
            resolution_source='global_fallback',
            agent_config_snapshot={},
        ),
    )
    assert event.event_id == fixed_id


# ---------------------------------------------------------------------------
# Round-trip tests — one per event type
# ---------------------------------------------------------------------------

def test_call_incoming_roundtrip():
    event = _make(CallIncomingEvent, CallIncomingPayload(
        from_number='+18125550100',
        to_number='+18129691371',
        call_sid='CAabc',
        agent_id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        resolution_source='phone_number_mapping',
        agent_config_snapshot={'llm_model': 'omnicoder', 'tts_voice': 'af_bella'},
        correlation_id='corr-001',
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'call.incoming'
    assert isinstance(rt, CallIncomingEvent)
    assert rt.payload.from_number == '+18125550100'
    assert rt.payload.correlation_id == 'corr-001'


def test_greeting_complete_roundtrip():
    event = _make(GreetingCompleteEvent, GreetingCompletePayload(
        greeting_text='Hello, this is Maya. How can I help?',
        duration_ms=2500,
        interrupted=False,
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'greeting.complete'
    assert isinstance(rt, GreetingCompleteEvent)
    assert rt.payload.greeting_text.startswith('Hello')
    assert rt.payload.interrupted is False


def test_greeting_complete_interrupted_roundtrip():
    event = _make(GreetingCompleteEvent, GreetingCompletePayload(
        greeting_text='Hello—',
        interrupted=True,
    ))
    rt = roundtrip(event)
    assert rt.payload.interrupted is True
    assert rt.payload.duration_ms is None  # optional


def test_asr_start_listen_roundtrip():
    event = _make(ASRStartListenEvent, ASRStartListenPayload(
        fsm_state='S2',
        prompted_field='caller_name',
        timeout_seconds=8.0,
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'asr.start_listen'
    assert isinstance(rt, ASRStartListenEvent)
    assert rt.payload.prompted_field == 'caller_name'


def test_asr_start_listen_no_field():
    event = _make(ASRStartListenEvent, ASRStartListenPayload(fsm_state='S1'))
    rt = roundtrip(event)
    assert rt.payload.prompted_field is None
    assert rt.payload.timeout_seconds == 8.0  # default


def test_asr_transcript_roundtrip():
    event = _make(ASRTranscriptEvent, ASRTranscriptPayload(
        text='My name is Alex Johnson',
        confidence=0.97,
        duration_ms=1800,
        started_ms=1000,
        ended_ms=2800,
        is_final=True,
        asr_session_id='asr-sess-001',
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'asr.transcript'
    assert isinstance(rt, ASRTranscriptEvent)
    assert rt.payload.text == 'My name is Alex Johnson'
    assert rt.payload.confidence == pytest.approx(0.97)


def test_llm_extract_roundtrip():
    event = _make(LLMExtractEvent, LLMExtractPayload(
        task='name_extract',
        transcript_text='Hi I am Sarah',
        target_fields=['caller_name'],
        fsm_state='S2',
        context_snapshot={'collected': {}},
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'llm.extract'
    assert isinstance(rt, LLMExtractEvent)
    assert rt.payload.task == 'name_extract'


def test_llm_extracted_roundtrip():
    event = _make(LLMExtractedEvent, LLMExtractedPayload(
        extracted_fields={'caller_name': 'Sarah'},
        confidence=0.95,
        task='name_extract',
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'llm.extracted'
    assert rt.payload.extracted_fields == {'caller_name': 'Sarah'}


def test_llm_extracted_fallback():
    event = _make(LLMExtractedEvent, LLMExtractedPayload(
        extracted_fields={},
        fallback_triggered=True,
        fallback_reason='llm_timeout',
    ))
    rt = roundtrip(event)
    assert rt.payload.fallback_triggered is True
    assert rt.payload.fallback_reason == 'llm_timeout'


def test_llm_classify_roundtrip():
    event = _make(LLMClassifyEvent, LLMClassifyPayload(
        transcript_text='I need to schedule a maintenance window',
        available_lanes=['A', 'B', 'C'],
        fsm_state='S3',
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'llm.classify'
    assert rt.payload.available_lanes == ['A', 'B', 'C']


def test_llm_intent_roundtrip():
    event = _make(LLMIntentEvent, LLMIntentPayload(
        lane='B',
        confidence=0.88,
        fallback_triggered=False,
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'llm.intent'
    assert rt.payload.lane == 'B'


def test_llm_intent_unknown_lane():
    event = _make(LLMIntentEvent, LLMIntentPayload(
        lane='unknown',
        fallback_triggered=True,
        fallback_reason='low_confidence',
    ))
    rt = roundtrip(event)
    assert rt.payload.lane == 'unknown'
    assert rt.payload.fallback_triggered is True


def test_tts_speak_roundtrip():
    tts_id = str(uuid.uuid4())
    event = _make(TTSSpeakEvent, TTSSpeakPayload(
        text='What is your name?',
        voice='af_bella',
        model='kokoro_realtime',
        fsm_state='S2',
        tts_request_id=tts_id,
        response_source='fsm_state_controller',
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'tts.speak'
    assert isinstance(rt, TTSSpeakEvent)
    assert rt.payload.tts_request_id == tts_id
    assert rt.payload.text == 'What is your name?'


def test_tts_complete_roundtrip():
    tts_id = str(uuid.uuid4())
    event = _make(TTSCompleteEvent, TTSCompletePayload(
        tts_request_id=tts_id,
        duration_ms=1200,
        interrupted=False,
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'tts.complete'
    assert rt.payload.tts_request_id == tts_id
    assert rt.payload.interrupted is False


def test_tts_complete_interrupted():
    event = _make(TTSCompleteEvent, TTSCompletePayload(
        tts_request_id=str(uuid.uuid4()),
        interrupted=True,
        error=None,
    ))
    rt = roundtrip(event)
    assert rt.payload.interrupted is True


def test_tts_complete_with_error():
    event = _make(TTSCompleteEvent, TTSCompletePayload(
        tts_request_id=str(uuid.uuid4()),
        error='TTS service unavailable',
    ))
    rt = roundtrip(event)
    assert rt.payload.error == 'TTS service unavailable'


def test_state_transition_roundtrip():
    trigger_id = str(uuid.uuid4())
    event = _make(StateTransitionEvent, StateTransitionPayload(
        from_state='S1',
        to_state='S2',
        trigger_event_id=trigger_id,
        trigger_event_type='greeting.complete',
        collected_fields_snapshot={'caller_name': 'Alex'},
        reason='greeting_complete_hard_listen',
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'state.transition'
    assert rt.payload.from_state == 'S1'
    assert rt.payload.to_state == 'S2'
    assert rt.payload.trigger_event_id == trigger_id
    assert rt.payload.collected_fields_snapshot == {'caller_name': 'Alex'}


def test_timeout_silence_nudge_roundtrip():
    event = _make(TimeoutSilenceEvent, TimeoutSilencePayload(
        fsm_state='S2',
        elapsed_seconds=8.1,
        prompted_field='caller_name',
        action='nudge',
        retry_count=1,
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'timeout.silence'
    assert rt.payload.action == 'nudge'
    assert rt.payload.retry_count == 1


def test_timeout_silence_escalate_roundtrip():
    event = _make(TimeoutSilenceEvent, TimeoutSilencePayload(
        fsm_state='S3',
        elapsed_seconds=24.0,
        action='escalate',
        retry_count=3,
    ))
    rt = roundtrip(event)
    assert rt.payload.action == 'escalate'
    assert rt.payload.prompted_field is None  # optional


def test_escalate_frustration_roundtrip():
    event = _make(EscalateFrustrationEvent, EscalateFrustrationPayload(
        fsm_state='S3',
        trigger_transcript='I want to speak to a manager right now',
        reason='sensitive_keyword',
        escalation_type='warm_transfer',
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'escalate.frustration'
    assert rt.payload.reason == 'sensitive_keyword'
    assert rt.payload.escalation_type == 'warm_transfer'


def test_call_ended_roundtrip():
    event = _make(CallEndedEvent, CallEndedPayload(
        final_state='S7',
        duration_seconds=145.3,
        outcome='success',
        collected_fields={'caller_name': 'Alex', 'callback_number': '8125550100'},
        missing_fields=[],
        notable_errors=[],
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'call.ended'
    assert rt.payload.outcome == 'success'
    assert rt.payload.duration_seconds == pytest.approx(145.3)
    assert rt.payload.collected_fields['caller_name'] == 'Alex'


def test_audit_log_roundtrip():
    event = _make(AuditLogEvent, AuditLogPayload(
        call_id=CALL_ID,
        session_id=SESSION_ID,
        tenant_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        direction='inbound',
        from_number='+18125550100',
        to_number='+18129691371',
        started_at='2026-03-25T14:00:00+00:00',
        ended_at='2026-03-25T14:02:25+00:00',
        duration_seconds=145.0,
        final_state='S7',
        outcome='success',
        collected_fields={'caller_name': 'Alex', 'issue': 'AC unit not cooling'},
        missing_fields=[],
        notable_errors=[],
        caller_turns=5,
        agent_turns=6,
        llm_mode='live',
        detected_intent='support',
    ))
    rt = roundtrip(event)
    assert rt.event_type == 'audit.log'
    assert isinstance(rt, AuditLogEvent)
    assert rt.payload.caller_turns == 5
    assert rt.payload.detected_intent == 'support'


# ---------------------------------------------------------------------------
# Discriminated union — wrong type should not match
# ---------------------------------------------------------------------------

def test_discriminated_union_rejects_unknown_type():
    from pydantic import TypeAdapter, ValidationError
    adapter = TypeAdapter(AnyFSMEvent)
    bad_json = json.dumps({
        'event_id': str(uuid.uuid4()),
        'event_type': 'not.a.real.type',
        'timestamp': '2026-03-25T00:00:00+00:00',
        'session_id': SESSION_ID,
        'call_id': CALL_ID,
        'payload': {},
    })
    with pytest.raises(ValidationError):
        adapter.validate_json(bad_json)


def test_discriminated_union_routes_all_types():
    """Every event type literal dispatches to its correct class."""
    type_to_cls = {
        'call.incoming': CallIncomingEvent,
        'greeting.complete': GreetingCompleteEvent,
        'asr.start_listen': ASRStartListenEvent,
        'asr.transcript': ASRTranscriptEvent,
        'llm.extract': LLMExtractEvent,
        'llm.extracted': LLMExtractedEvent,
        'llm.classify': LLMClassifyEvent,
        'llm.intent': LLMIntentEvent,
        'tts.speak': TTSSpeakEvent,
        'tts.complete': TTSCompleteEvent,
        'state.transition': StateTransitionEvent,
        'timeout.silence': TimeoutSilenceEvent,
        'escalate.frustration': EscalateFrustrationEvent,
        'call.ended': CallEndedEvent,
        'audit.log': AuditLogEvent,
    }
    # Build minimal valid payloads for each type
    minimal_payloads: dict[str, dict] = {
        'call.incoming': {'from_number': '+1', 'to_number': '+1', 'call_sid': 'CA1',
                          'agent_id': 'a', 'tenant_id': 't',
                          'resolution_source': 's', 'agent_config_snapshot': {}},
        'greeting.complete': {'greeting_text': 'hi'},
        'asr.start_listen': {'fsm_state': 'S1'},
        'asr.transcript': {'text': 'hello'},
        'llm.extract': {'task': 'name_extract', 'transcript_text': 'hi',
                        'target_fields': [], 'fsm_state': 'S2'},
        'llm.extracted': {'extracted_fields': {}},
        'llm.classify': {'transcript_text': 'hi', 'available_lanes': ['A'], 'fsm_state': 'S3'},
        'llm.intent': {'lane': 'A'},
        'tts.speak': {'text': 'hi', 'voice': 'af_bella', 'model': 'kokoro_realtime', 'fsm_state': 'S2'},
        'tts.complete': {'tts_request_id': str(uuid.uuid4())},
        'state.transition': {'from_state': 'S1', 'to_state': 'S2',
                             'trigger_event_id': str(uuid.uuid4()), 'trigger_event_type': 'greeting.complete'},
        'timeout.silence': {'fsm_state': 'S2', 'elapsed_seconds': 8.0, 'action': 'nudge'},
        'escalate.frustration': {'fsm_state': 'S3', 'trigger_transcript': 'angry',
                                 'reason': 'sensitive_keyword'},
        'call.ended': {'final_state': 'S7', 'outcome': 'success'},
        'audit.log': {'call_id': CALL_ID, 'session_id': SESSION_ID, 'tenant_id': 't',
                      'agent_id': 'a', 'direction': 'inbound', 'from_number': '+1',
                      'to_number': '+1', 'started_at': '2026-01-01T00:00:00+00:00',
                      'ended_at': '2026-01-01T00:01:00+00:00', 'final_state': 'S7',
                      'outcome': 'success'},
    }

    from pydantic import TypeAdapter
    adapter = TypeAdapter(AnyFSMEvent)

    for event_type, expected_cls in type_to_cls.items():
        raw = json.dumps({
            'event_id': str(uuid.uuid4()),
            'event_type': event_type,
            'timestamp': '2026-03-25T00:00:00+00:00',
            'session_id': SESSION_ID,
            'call_id': CALL_ID,
            'payload': minimal_payloads[event_type],
        })
        result = adapter.validate_json(raw)
        assert isinstance(result, expected_cls), (
            f'event_type={event_type!r} dispatched to {type(result).__name__}, '
            f'expected {expected_cls.__name__}'
        )


# ---------------------------------------------------------------------------
# make_event factory
# ---------------------------------------------------------------------------

def test_make_event_produces_valid_envelope():
    event = make_event(
        TTSSpeakEvent,
        session_id=SESSION_ID,
        call_id=CALL_ID,
        payload=TTSSpeakPayload(
            text='Hello caller',
            voice='af_bella',
            model='kokoro_realtime',
            fsm_state='S1',
        ),
    )
    assert event.session_id == SESSION_ID
    assert event.call_id == CALL_ID
    assert event.event_type == 'tts.speak'
    assert event.event_id  # auto-generated


def test_make_event_serializes_cleanly():
    event = make_event(
        CallEndedEvent,
        session_id=SESSION_ID,
        call_id=CALL_ID,
        payload=CallEndedPayload(final_state='S7', outcome='success'),
    )
    raw = event.model_dump_json()
    parsed = json.loads(raw)
    assert parsed['event_type'] == 'call.ended'
    assert parsed['payload']['outcome'] == 'success'


# ---------------------------------------------------------------------------
# Frozenset completeness
# ---------------------------------------------------------------------------

def test_all_event_types_covers_every_literal():
    """ALL_EVENT_TYPES must match the set of event_type literals in AnyFSMEvent."""
    # Extract literals from the discriminated union members
    union_members = get_args(AnyFSMEvent.__args__[0] if hasattr(AnyFSMEvent, '__args__') else AnyFSMEvent)
    # Collect via minimal instantiation — use the type_to_cls map above
    expected = {
        'call.incoming', 'greeting.complete', 'asr.start_listen', 'asr.transcript',
        'llm.extract', 'llm.extracted', 'llm.classify', 'llm.intent',
        'tts.speak', 'tts.complete', 'state.transition', 'timeout.silence',
        'escalate.frustration', 'call.ended', 'audit.log',
    }
    assert ALL_EVENT_TYPES == expected, (
        f'ALL_EVENT_TYPES is missing: {expected - ALL_EVENT_TYPES} '
        f'or has extras: {ALL_EVENT_TYPES - expected}'
    )


def test_state_controller_commands_are_subset_of_all():
    assert STATE_CONTROLLER_COMMANDS.issubset(ALL_EVENT_TYPES)


def test_state_controller_triggers_are_subset_of_all():
    assert STATE_CONTROLLER_TRIGGERS.issubset(ALL_EVENT_TYPES)


def test_commands_and_triggers_do_not_overlap():
    """Commands are things the controller emits; triggers are things it reacts to.
    They should not overlap (controller should not react to its own commands)."""
    overlap = STATE_CONTROLLER_COMMANDS & STATE_CONTROLLER_TRIGGERS
    assert not overlap, f'Unexpected overlap: {overlap}'


def test_all_event_types_count():
    assert len(ALL_EVENT_TYPES) == 15


# ---------------------------------------------------------------------------
# Payload field validation
# ---------------------------------------------------------------------------

def test_timeout_silence_action_must_be_nudge_or_escalate():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        TimeoutSilencePayload(fsm_state='S2', elapsed_seconds=5.0, action='invalid')


def test_escalate_frustration_escalation_type_default():
    payload = EscalateFrustrationPayload(
        fsm_state='S3',
        trigger_transcript='cancel now',
        reason='sensitive_keyword',
    )
    assert payload.escalation_type == 'warm_transfer'


def test_llm_extract_task_must_be_valid_literal():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        LLMExtractPayload(
            task='invalid_task',
            transcript_text='hi',
            target_fields=[],
            fsm_state='S2',
        )


def test_asr_transcript_defaults():
    payload = ASRTranscriptPayload(text='hello world')
    assert payload.is_final is True
    assert payload.confidence is None
    assert payload.asr_session_id == ''


def test_collected_fields_snapshot_defaults_empty():
    payload = StateTransitionPayload(
        from_state='S0',
        to_state='S1',
        trigger_event_id=str(uuid.uuid4()),
        trigger_event_type='call.incoming',
    )
    assert payload.collected_fields_snapshot == {}
    assert payload.reason == ''
