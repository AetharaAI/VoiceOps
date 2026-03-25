"""
Smoke tests for LLM Consumer and Audit Consumer.

Tests focus on the _dispatch / _write_event paths, not on Redis connectivity.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from io import StringIO
from pathlib import Path

from app.services.audit.consumer import AuditConsumer
from app.services.llm.consumer import LLMConsumer
from app.services.streams.event_schemas import (
    ASRTranscriptEvent,
    ASRTranscriptPayload,
    CallIncomingEvent,
    CallIncomingPayload,
    LLMClassifyEvent,
    LLMClassifyPayload,
    LLMExtractEvent,
    LLMExtractPayload,
    make_event,
)
from app.services.streams.publisher import StreamPublisher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_ids():
    return str(uuid.uuid4()), str(uuid.uuid4())  # session_id, call_id


class _FakePublisher:
    def __init__(self):
        self.published = []

    async def publish(self, event):
        self.published.append(event)
        return '1-0'

    def events_of_type(self, et):
        return [e for e in self.published if e.event_type == et]


def _raw_fields(event) -> dict:
    """Wrap a typed event as the raw Redis fields dict."""
    return {'data': event.model_dump_json()}


# ---------------------------------------------------------------------------
# LLM Consumer: extract
# ---------------------------------------------------------------------------

def test_llm_consumer_extract_publishes_llm_extracted():
    """llm.extract → LLMConsumer → publishes llm.extracted."""
    consumer = LLMConsumer()
    session_id, call_id = _make_session_ids()
    publisher = _FakePublisher()

    extract_event = make_event(
        LLMExtractEvent,
        session_id=session_id,
        call_id=call_id,
        payload=LLMExtractPayload(
            task='field_extract',
            transcript_text='My name is Alice and my number is 555-1234',
            target_fields=['caller_name', 'callback_number'],
            fsm_state='S2',
            context_snapshot={},
        ),
    )

    async def run():
        await consumer._dispatch(
            publisher, _raw_fields(extract_event),
            session_id=session_id, call_id=call_id, tenant_id='test',
        )

    asyncio.get_event_loop().run_until_complete(run())

    extracted_events = publisher.events_of_type('llm.extracted')
    assert len(extracted_events) == 1
    payload = extracted_events[0].payload
    assert isinstance(payload.extracted_fields, dict)


def test_llm_consumer_classify_publishes_llm_intent():
    """llm.classify → LLMConsumer → publishes llm.intent."""
    consumer = LLMConsumer()
    session_id, call_id = _make_session_ids()
    publisher = _FakePublisher()

    classify_event = make_event(
        LLMClassifyEvent,
        session_id=session_id,
        call_id=call_id,
        payload=LLMClassifyPayload(
            transcript_text='I need to book an appointment',
            available_lanes=['A', 'B', 'C'],
            fsm_state='S3',
            context_snapshot={},
        ),
    )

    async def run():
        await consumer._dispatch(
            publisher, _raw_fields(classify_event),
            session_id=session_id, call_id=call_id, tenant_id='test',
        )

    asyncio.get_event_loop().run_until_complete(run())

    intent_events = publisher.events_of_type('llm.intent')
    assert len(intent_events) == 1
    payload = intent_events[0].payload
    assert payload.lane in ('A', 'B', 'C')


def test_llm_consumer_unknown_event_ignored():
    """Non-llm events are dispatched but don't produce output."""
    consumer = LLMConsumer()
    session_id, call_id = _make_session_ids()
    publisher = _FakePublisher()

    asr_event = make_event(
        ASRTranscriptEvent,
        session_id=session_id,
        call_id=call_id,
        payload=ASRTranscriptPayload(text='hello'),
    )

    async def run():
        et = await consumer._dispatch(
            publisher, _raw_fields(asr_event),
            session_id=session_id, call_id=call_id, tenant_id='test',
        )
        return et

    et = asyncio.get_event_loop().run_until_complete(run())

    assert et == 'asr.transcript'
    assert len(publisher.published) == 0  # no output from non-llm events


def test_llm_consumer_call_ended_returns_sentinel():
    """call.ended event makes _dispatch return 'call.ended'."""
    from app.services.streams.event_schemas import CallEndedEvent, CallEndedPayload
    consumer = LLMConsumer()
    session_id, call_id = _make_session_ids()
    publisher = _FakePublisher()

    ended_event = make_event(
        CallEndedEvent,
        session_id=session_id,
        call_id=call_id,
        payload=CallEndedPayload(
            final_state='S7',
            outcome='success',
        ),
    )

    async def run():
        return await consumer._dispatch(
            publisher, _raw_fields(ended_event),
            session_id=session_id, call_id=call_id, tenant_id='test',
        )

    et = asyncio.get_event_loop().run_until_complete(run())
    assert et == 'call.ended'


# ---------------------------------------------------------------------------
# Audit Consumer: JSONL writing
# ---------------------------------------------------------------------------

def test_audit_consumer_writes_events_to_jsonl():
    """Events are written to the JSONL log file."""
    consumer = AuditConsumer()
    session_id, call_id = _make_session_ids()
    publisher = _FakePublisher()

    incoming_event = make_event(
        CallIncomingEvent,
        session_id=session_id,
        call_id=call_id,
        payload=CallIncomingPayload(
            from_number='+15551234567',
            to_number='+15559876543',
            call_sid='CA_test',
            agent_id='ag-1',
            tenant_id='t-1',
            resolution_source='phone_number_mapping',
            agent_config_snapshot={},
        ),
    )

    log_buffer = StringIO()

    consumer._write_event(_raw_fields(incoming_event), log_buffer)

    log_buffer.seek(0)
    line = log_buffer.readline()
    assert line.strip()
    parsed = json.loads(line)
    assert parsed['event_type'] == 'call.incoming'
    assert parsed['call_id'] == call_id


def test_audit_consumer_write_returns_event_type():
    """_write_event returns the event_type string."""
    consumer = AuditConsumer()
    log_buffer = StringIO()

    session_id, call_id = _make_session_ids()
    asr_event = make_event(
        ASRTranscriptEvent,
        session_id=session_id,
        call_id=call_id,
        payload=ASRTranscriptPayload(text='Hello'),
    )

    et = consumer._write_event(_raw_fields(asr_event), log_buffer)
    assert et == 'asr.transcript'


def test_audit_consumer_handles_none_log_file():
    """_write_event is safe when log_file is None."""
    consumer = AuditConsumer()
    session_id, call_id = _make_session_ids()
    asr_event = make_event(
        ASRTranscriptEvent,
        session_id=session_id,
        call_id=call_id,
        payload=ASRTranscriptPayload(text='test'),
    )

    # Should not raise
    et = consumer._write_event(_raw_fields(asr_event), None)
    assert et == 'asr.transcript'


def test_audit_consumer_handles_bad_json():
    """_write_event returns '' for malformed entries."""
    consumer = AuditConsumer()
    log_buffer = StringIO()

    et = consumer._write_event({'data': 'not valid json {'}, log_buffer)
    assert et == ''


def test_audit_consumer_open_log_creates_file():
    """_open_log creates the per-call directory and file."""
    consumer = AuditConsumer()

    with tempfile.TemporaryDirectory() as tmpdir:
        consumer._settings = type('S', (), {'call_log_root': tmpdir})()
        call_id = str(uuid.uuid4())
        f = consumer._open_log(call_id)
        assert f is not None
        f.close()
        assert Path(tmpdir, call_id, 'fsm_events.jsonl').exists()
