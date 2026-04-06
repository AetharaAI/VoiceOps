"""
Tests for StateController — FSM logic and hard-listen guarantee.

Tests focus on:
- Hard-listen guarantee: tts.speak blocked during ASR, asr.start_listen blocked during TTS
- FSM transitions: S0→S1→S2 flow via call.incoming, tts.complete, asr.transcript
- Terminal state handling: S7/Esc → terminated on tts.complete
- Silence timeout detection
- Escalation on keyword detection

These tests call private helpers directly to test FSM logic without Redis.
The _dispatch path is tested via a stub publisher that captures published events.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.state_controller.controller import (
    CallFSMState,
    StateController,
)
from app.services.streams.event_schemas import (
    ASRTranscriptEvent,
    ASRTranscriptPayload,
    CallIncomingEvent,
    CallIncomingPayload,
    FSMEventBase,
    TTSCompleteEvent,
    TTSCompletePayload,
    make_event,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(**kwargs) -> MagicMock:
    """Stub Agent with sane defaults."""
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.name = 'Test Agent'
    agent.persona = 'You are a helpful agent.'
    agent.script = 'Collect caller info.'
    agent.required_fields = {'caller_name': {'label': 'Name', 'prompt': 'Could I have your name?'}}
    agent.policy_config = {'runtime': {
        'tts_voice': 'af_bella',
        'tts_model': 'kokoro_realtime',
        'opening_greeting': 'Hello, thank you for calling.',
        'closing_message': 'Thank you and have a great day!',
        'escalation_message': 'Transferring you to a specialist.',
    }}
    agent.context_payload = {}
    for k, v in kwargs.items():
        setattr(agent, k, v)
    return agent


def _make_fsm_state(**kwargs) -> CallFSMState:
    defaults = dict(
        session_id=str(uuid.uuid4()),
        call_id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        agent=_make_agent(),
    )
    defaults.update(kwargs)
    return CallFSMState(**defaults)


class _FakePublisher:
    """Captures all published events for assertion."""

    def __init__(self):
        self.published: list[FSMEventBase] = []

    async def publish(self, event: FSMEventBase) -> str | None:
        self.published.append(event)
        return '1-0'

    def events_of_type(self, event_type: str) -> list[FSMEventBase]:
        return [e for e in self.published if e.event_type == event_type]

    def last_of_type(self, event_type: str) -> FSMEventBase | None:
        events = self.events_of_type(event_type)
        return events[-1] if events else None


def _make_incoming_event(state: CallFSMState) -> FSMEventBase:
    return make_event(
        CallIncomingEvent,
        session_id=state.session_id,
        call_id=state.call_id,
        payload=CallIncomingPayload(
            from_number='+15551234567',
            to_number='+15559876543',
            call_sid='CA_test',
            agent_id=str(state.agent.id),
            tenant_id=state.tenant_id,
            resolution_source='phone_number_mapping',
            agent_config_snapshot={},
        ),
    )


def _make_tts_complete_event(state: CallFSMState, tts_request_id: str | None = None) -> FSMEventBase:
    return make_event(
        TTSCompleteEvent,
        session_id=state.session_id,
        call_id=state.call_id,
        payload=TTSCompletePayload(
            tts_request_id=tts_request_id or str(uuid.uuid4()),
        ),
    )


def _make_transcript_event(state: CallFSMState, text: str, *, is_final: bool = True) -> FSMEventBase:
    return make_event(
        ASRTranscriptEvent,
        session_id=state.session_id,
        call_id=state.call_id,
        payload=ASRTranscriptPayload(text=text, is_final=is_final),
    )


# ---------------------------------------------------------------------------
# Hard-listen guarantee
# ---------------------------------------------------------------------------

def test_emit_tts_blocked_when_asr_listening():
    """_emit_tts() must not publish if asr_listening=True."""
    ctrl = StateController()
    state = _make_fsm_state()
    publisher = _FakePublisher()
    state.asr_listening = True

    asyncio.get_event_loop().run_until_complete(
        ctrl._emit_tts(state, publisher, text='Hello', response_source='test')
    )

    assert len(publisher.published) == 0
    assert state.pending_tts_id is None
    assert state.agent_turns == 0


def test_emit_tts_publishes_when_asr_not_listening():
    """_emit_tts() publishes tts.speak when asr_listening=False."""
    ctrl = StateController()
    state = _make_fsm_state()
    publisher = _FakePublisher()
    state.asr_listening = False

    asyncio.get_event_loop().run_until_complete(
        ctrl._emit_tts(state, publisher, text='Hello caller.', response_source='test')
    )

    tts_events = publisher.events_of_type('tts.speak')
    assert len(tts_events) == 1
    assert tts_events[0].payload.text == 'Hello caller.'
    assert state.pending_tts_id is not None
    assert state.agent_turns == 1


def test_emit_asr_blocked_when_tts_pending():
    """_emit_asr_start_listen() must not publish if pending_tts_id is set."""
    ctrl = StateController()
    state = _make_fsm_state()
    publisher = _FakePublisher()
    state.pending_tts_id = 'some-tts-id'

    asyncio.get_event_loop().run_until_complete(
        ctrl._emit_asr_start_listen(state, publisher)
    )

    assert len(publisher.published) == 0
    assert state.asr_listening is False


def test_emit_asr_publishes_when_no_pending_tts():
    """_emit_asr_start_listen() publishes when pending_tts_id is None."""
    ctrl = StateController()
    state = _make_fsm_state()
    publisher = _FakePublisher()
    state.pending_tts_id = None

    asyncio.get_event_loop().run_until_complete(
        ctrl._emit_asr_start_listen(state, publisher)
    )

    asr_events = publisher.events_of_type('asr.start_listen')
    assert len(asr_events) == 1
    assert state.asr_listening is True
    assert state.silence_deadline is not None


def test_emit_asr_preserves_existing_listen_window_open_at():
    ctrl = StateController()
    state = _make_fsm_state()
    publisher = _FakePublisher()
    existing = time.monotonic() - 10.0
    state.listen_window_open_at = existing

    asyncio.get_event_loop().run_until_complete(
        ctrl._emit_asr_start_listen(state, publisher)
    )

    assert state.listen_window_open_at == existing


# ---------------------------------------------------------------------------
# call.incoming → S0→S1 flow
# ---------------------------------------------------------------------------

def test_call_incoming_emits_greeting_tts():
    """call.incoming triggers greeting tts.speak and S0→S1 transition."""
    ctrl = StateController()
    state = _make_fsm_state()
    publisher = _FakePublisher()

    async def run():
        incoming = _make_incoming_event(state)
        await ctrl._on_call_incoming(state, incoming, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.current_state == 'S1'
    tts = publisher.last_of_type('tts.speak')
    assert tts is not None
    assert len(tts.payload.text) > 0
    trans = publisher.last_of_type('state.transition')
    assert trans is not None
    assert trans.payload.to_state == 'S1'
    assert len(publisher.events_of_type('asr.start_listen')) == 0


def test_call_incoming_ignored_if_not_s0():
    """Duplicate call.incoming is silently ignored when not in S0."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S2'
    publisher = _FakePublisher()

    async def run():
        incoming = _make_incoming_event(state)
        await ctrl._on_call_incoming(state, incoming, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.current_state == 'S2'  # unchanged
    assert len(publisher.published) == 0


# ---------------------------------------------------------------------------
# tts.complete → emit asr.start_listen
# ---------------------------------------------------------------------------

def test_tts_complete_starts_listen_in_s1():
    """tts.complete in S1 clears pending_tts_id and emits asr.start_listen."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S1'
    publisher = _FakePublisher()

    # Simulate we emitted a TTS
    state.pending_tts_id = 'req-123'

    async def run():
        event = _make_tts_complete_event(state, tts_request_id='req-123')
        await ctrl._on_tts_complete(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.pending_tts_id is None
    assert state.asr_listening is True
    asr_events = publisher.events_of_type('asr.start_listen')
    assert len(asr_events) == 1


def test_tts_complete_stale_id_ignored():
    """tts.complete for a different tts_request_id is ignored."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S1'
    state.pending_tts_id = 'expected-id'
    publisher = _FakePublisher()

    async def run():
        event = _make_tts_complete_event(state, tts_request_id='stale-id')
        await ctrl._on_tts_complete(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    # Should not start listening
    assert state.pending_tts_id == 'expected-id'  # unchanged
    assert state.asr_listening is False
    assert len(publisher.published) == 0


def test_tts_complete_in_s7_sets_terminated():
    """tts.complete in S7 (goodbye TTS) terminates the call."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S7'
    state.pending_tts_id = 'goodbye-req'
    publisher = _FakePublisher()

    async def run():
        event = _make_tts_complete_event(state, tts_request_id='goodbye-req')
        await ctrl._on_tts_complete(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.terminated is True
    # Should NOT start listening after goodbye
    assert state.asr_listening is False
    assert len(publisher.events_of_type('asr.start_listen')) == 0


def test_tts_complete_in_esc_sets_terminated():
    """tts.complete in Esc (transfer TTS) terminates the call."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'Esc'
    state.pending_tts_id = 'esc-req'
    publisher = _FakePublisher()

    async def run():
        event = _make_tts_complete_event(state, tts_request_id='esc-req')
        await ctrl._on_tts_complete(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.terminated is True


# ---------------------------------------------------------------------------
# asr.transcript handling
# ---------------------------------------------------------------------------

def test_asr_transcript_clears_listening_flag():
    """asr.transcript always clears asr_listening, regardless of content."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S2'
    state.asr_listening = True
    state.silence_deadline = 999999.0
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='My name is Alex')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.asr_listening is False
    assert state.silence_deadline is None
    assert state.caller_turns == 1


def test_asr_partial_transcript_extends_deadline_without_agent_turn():
    """Non-final asr.transcript keeps listen active and only extends deadline."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S2'
    state.last_prompted_field = 'callback_number'
    state.asr_listening = True
    state.silence_deadline = 1.0
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='eight one two', is_final=False)
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.asr_listening is True
    assert state.silence_deadline is not None
    assert state.silence_deadline > 1.0
    assert state.caller_turns == 0
    assert len(publisher.events_of_type('tts.speak')) == 0


def test_asr_transcript_ignored_in_terminal_state():
    """Late transcripts must be ignored once the FSM is in S7/Esc."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S7'
    state.asr_listening = True
    state.silence_deadline = 9999.0
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='yes')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.asr_listening is False
    assert state.silence_deadline is None
    assert len(publisher.events_of_type('tts.speak')) == 0


def test_asr_transcript_increments_caller_turns():
    """caller_turns is incremented for each non-empty transcript."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S2'
    state.asr_listening = True
    publisher = _FakePublisher()

    async def run():
        for text in ['Hello', 'My name is Bob', 'I need help']:
            state.asr_listening = True
            state.silence_deadline = None
            event = _make_transcript_event(state, text=text)
            await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.caller_turns == 3


def test_asr_transcript_emits_tts_response():
    """asr.transcript produces a tts.speak (agent response)."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S2'
    state.asr_listening = True
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='My name is Carol')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    tts_events = publisher.events_of_type('tts.speak')
    assert len(tts_events) >= 1


def test_asr_transcript_escalates_on_keyword():
    """Escalation keyword in transcript triggers Esc transition."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S2'
    state.asr_listening = True
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='I want to sue you')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.current_state == 'Esc'
    trans = publisher.last_of_type('state.transition')
    assert trans is not None
    assert trans.payload.to_state == 'Esc'


def test_asr_empty_transcript_discards_and_reopens_listen():
    """Empty transcript should be discarded and re-open listen without TTS."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S2'
    state.asr_listening = True
    state.last_listen_started_at = time.monotonic() - 9.0
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.current_state != 'Esc'
    assert len(publisher.events_of_type('tts.speak')) == 0
    assert len(publisher.events_of_type('asr.start_listen')) == 1


def test_asr_empty_transcript_quick_result_restarts_listen_silently():
    """First quick empty transcript should re-open listen without speaking."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S2'
    state.asr_listening = True
    state.last_listen_started_at = time.monotonic()
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert len(publisher.events_of_type('tts.speak')) == 0
    assert len(publisher.events_of_type('asr.start_listen')) == 1


def test_asr_empty_transcript_does_not_reset_empty_counter_or_increment_turns():
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S2'
    state.asr_listening = True
    state.empty_transcript_count = 1
    state.caller_turns = 0
    state.last_listen_started_at = time.monotonic()
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.empty_transcript_count == 2
    assert state.caller_turns == 0
    assert len(publisher.events_of_type('tts.speak')) == 0
    assert len(publisher.events_of_type('asr.start_listen')) == 1


def test_s6_ignores_duplicate_confirmation_retry_prompt_on_empty_transcript():
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S6'
    state.asr_listening = True
    state.last_listen_started_at = time.monotonic() - 3.0
    state.last_recovery_prompt = ctrl._confirmation_retry_prompt()
    state.empty_transcript_count = 1
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert len(publisher.events_of_type('tts.speak')) == 0
    assert len(publisher.events_of_type('asr.start_listen')) == 1


# ---------------------------------------------------------------------------
# Silence timeout
# ---------------------------------------------------------------------------

def test_silence_timeout_fires_recovery_on_first_miss():
    """First silence timeout emits recovery TTS, not escalation."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S2'
    state.asr_listening = True
    state.silence_retry_count = 0
    publisher = _FakePublisher()

    asyncio.get_event_loop().run_until_complete(
        ctrl._on_silence_timeout(state, publisher)
    )

    assert state.current_state != 'Esc'
    assert state.asr_listening is False
    tts_events = publisher.events_of_type('tts.speak')
    assert len(tts_events) == 1


def test_s1_silence_timeout_reopens_listen_during_greeting_window():
    """During the initial greeting window, silence timeout should not speak."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S1'
    state.asr_listening = True
    state.listen_window_open_at = time.monotonic() - 3.0
    publisher = _FakePublisher()

    asyncio.get_event_loop().run_until_complete(
        ctrl._on_silence_timeout(state, publisher)
    )

    assert len(publisher.events_of_type('tts.speak')) == 0
    assert len(publisher.events_of_type('asr.start_listen')) == 1


def test_s1_silence_timeout_emits_recovery_after_greeting_window():
    from app.services.state_controller.controller import GREETING_RECOVERY_DELAY_SECONDS

    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S1'
    state.asr_listening = True
    state.listen_window_open_at = time.monotonic() - (GREETING_RECOVERY_DELAY_SECONDS + 1.0)
    publisher = _FakePublisher()

    asyncio.get_event_loop().run_until_complete(
        ctrl._on_silence_timeout(state, publisher)
    )

    assert len(publisher.events_of_type('tts.speak')) == 1


def test_silence_timeout_in_s6_uses_confirmation_retry_prompt():
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S6'
    state.asr_listening = True
    state.silence_retry_count = 0
    publisher = _FakePublisher()

    asyncio.get_event_loop().run_until_complete(
        ctrl._on_silence_timeout(state, publisher)
    )

    tts = publisher.last_of_type('tts.speak')
    assert tts is not None
    assert tts.payload.response_source == 'silence_recovery'
    assert 'yes' in tts.payload.text.lower()
    assert 'no' in tts.payload.text.lower()


def test_silence_timeout_escalates_after_max_retries():
    """After MAX_SILENCE_RETRIES silence timeouts, escalate."""
    from app.services.state_controller.controller import MAX_SILENCE_RETRIES
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S2'
    state.asr_listening = True
    state.silence_retry_count = MAX_SILENCE_RETRIES - 1  # one more = escalate
    publisher = _FakePublisher()

    asyncio.get_event_loop().run_until_complete(
        ctrl._on_silence_timeout(state, publisher)
    )

    assert state.current_state == 'Esc'


def test_silence_timeout_ignored_when_not_listening():
    """Silence timeout is a no-op if asr_listening is False (stale)."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.asr_listening = False
    state.silence_retry_count = 0
    publisher = _FakePublisher()

    asyncio.get_event_loop().run_until_complete(
        ctrl._on_silence_timeout(state, publisher)
    )

    assert len(publisher.published) == 0
    assert state.silence_retry_count == 0  # unchanged


def test_enter_s6_readback_formats_callback_number_as_digits():
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S6'
    state.agent.required_fields = {
        'name': {'prompt': 'Name?'},
        'callback_number': {'prompt': 'Best callback number?'},
    }
    state.last_prompted_field = 'callback_number'
    state.collected_fields = {
        'name': 'Mary',
        'callback_number': '8123632424',
    }
    publisher = _FakePublisher()

    async def run():
        await ctrl._enter_s6_tts(state, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    tts = publisher.last_of_type('tts.speak')
    assert tts is not None
    assert '8 1 2 3 6 3 2 4 2 4' in tts.payload.text
    assert state.last_prompted_field is None


def test_enter_s6_readback_only_uses_required_fields():
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S6'
    state.agent.required_fields = {
        'name': {'prompt': 'Name?'},
        'callback_number': {'prompt': 'Best callback number?'},
    }
    state.collected_fields = {
        'name': 'Corey',
        'callback_number': '8123632424',
        'best_follow_up_method': 'Text me after 5 pm',
        'organization': 'Not required',
    }
    publisher = _FakePublisher()

    async def run():
        await ctrl._enter_s6_tts(state, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    tts = publisher.last_of_type('tts.speak')
    assert tts is not None
    assert 'Name: Corey' in tts.payload.text
    assert 'Callback Number: 8 1 2 3 6 3 2 4 2 4' in tts.payload.text
    assert 'Best Follow Up Method' not in tts.payload.text
    assert 'Organization' not in tts.payload.text


def test_resolve_listen_timeout_in_s6_has_confirmation_floor():
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S6'
    state.silence_timeout_seconds = 10.0
    state.last_prompted_field = None

    timeout = ctrl._resolve_listen_timeout(state)

    assert timeout >= 14.0


# ---------------------------------------------------------------------------
# State transition helper
# ---------------------------------------------------------------------------

def test_transition_to_publishes_event_and_updates_state():
    """_transition_to() publishes state.transition and updates current_state."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S1'
    publisher = _FakePublisher()

    async def run():
        incoming = _make_incoming_event(state)
        await ctrl._transition_to(state, 'S2', trigger=incoming, publisher=publisher,
                                  reason='test')

    asyncio.get_event_loop().run_until_complete(run())

    assert state.current_state == 'S2'
    trans_events = publisher.events_of_type('state.transition')
    assert len(trans_events) == 1
    payload = trans_events[0].payload
    assert payload.from_state == 'S1'
    assert payload.to_state == 'S2'
    assert payload.reason == 'test'


# ---------------------------------------------------------------------------
# Readback + confirmation
# ---------------------------------------------------------------------------

def test_confirmation_yes_transitions_to_s7():
    """Saying 'yes' in S6 triggers S7 and goodbye TTS."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S6'
    state.asr_listening = True
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='Yes that is correct')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.current_state == 'S7'
    tts = publisher.last_of_type('tts.speak')
    assert tts is not None
    assert tts.payload.response_source == 'scripted_goodbye'


def test_confirmation_natural_affirm_phrase_transitions_to_s7():
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S6'
    state.asr_listening = True
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='Yeah everything looks good to me')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.current_state == 'S7'
    tts = publisher.last_of_type('tts.speak')
    assert tts is not None
    assert tts.payload.response_source == 'scripted_goodbye'


def test_confirmation_no_triggers_retry():
    """Saying 'no' in S6 emits correction TTS without changing state."""
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S6'
    state.asr_listening = True
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='No that is wrong')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    # Still in S6 (not escalated on first denial)
    assert state.current_state == 'S6'
    assert publisher.last_of_type('tts.speak') is not None


def test_confirmation_mixed_response_prefers_deny():
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S6'
    state.asr_listening = True
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='Yeah but I need to change one thing')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.current_state == 'S6'
    tts = publisher.last_of_type('tts.speak')
    assert tts is not None
    assert tts.payload.response_source == 'confirmation_correction'


def test_confirmation_unclear_uses_yes_no_retry_prompt():
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S6'
    state.asr_listening = True
    publisher = _FakePublisher()

    async def run():
        event = _make_transcript_event(state, text='maybe I guess')
        await ctrl._on_asr_transcript(state, event, publisher)

    asyncio.get_event_loop().run_until_complete(run())

    assert state.current_state == 'S6'
    tts = publisher.last_of_type('tts.speak')
    assert tts is not None
    assert tts.payload.response_source == 'confirmation_retry'
    assert 'yes' in tts.payload.text.lower()
    assert 'no' in tts.payload.text.lower()


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------

def test_escalation_emits_transfer_tts():
    """escalate.frustration event triggers Esc TTS."""
    from app.services.streams.event_schemas import (
        EscalateFrustrationEvent,
        EscalateFrustrationPayload,
    )
    ctrl = StateController()
    state = _make_fsm_state()
    state.current_state = 'S3'
    publisher = _FakePublisher()

    esc_event = make_event(
        EscalateFrustrationEvent,
        session_id=state.session_id,
        call_id=state.call_id,
        payload=EscalateFrustrationPayload(
            fsm_state='S3',
            trigger_transcript='I want to speak to a manager',
            reason='explicit_request',
        ),
    )

    asyncio.get_event_loop().run_until_complete(
        ctrl._on_escalate(state, esc_event, publisher)
    )

    assert state.current_state == 'Esc'
    tts = publisher.last_of_type('tts.speak')
    assert tts is not None
    assert tts.payload.response_source == 'escalation_transfer'


# ---------------------------------------------------------------------------
# CallFSMState defaults
# ---------------------------------------------------------------------------

def test_call_fsm_state_defaults():
    state = _make_fsm_state()
    assert state.current_state == 'S0'
    assert state.asr_listening is False
    assert state.pending_tts_id is None
    assert state.terminated is False
    assert state.agent_turns == 0
    assert state.caller_turns == 0
    assert state.collected_fields == {}
    assert state.silence_deadline is None
