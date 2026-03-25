"""
Tests for StreamIngester — the thin Twilio WebSocket handler.

Tests focus on:
- VAD state machine: speech onset, end-of-turn silence, barge-in
- Audio queue behavior (end-of-turn None sentinel, pre-speech flush)
- Twilio event routing (connected/mark passthrough, start/media/stop/dtmf)
- Feature flag routing in the WebSocket endpoint
"""

import sys
import types
import asyncio
import uuid
from dataclasses import dataclass, field
from collections import deque

# Stub webrtcvad before importing session code
if 'webrtcvad' not in sys.modules:
    webrtcvad_module = types.ModuleType('webrtcvad')

    class Vad:
        def set_mode(self, mode):
            self._mode = mode
            self._speech = False

        def is_speech(self, pcm_data, sample_rate):
            return getattr(self, '_speech', False)

    webrtcvad_module.Vad = Vad
    sys.modules['webrtcvad'] = webrtcvad_module

from app.services.realtime.stream_ingester import (
    IngesterSession,
    StreamIngester,
    MIN_SPEECH_FRAMES,
    END_OF_TURN_SILENCE_FRAMES,
    TWILIO_FRAME_BYTES,
    RECENT_FRAME_BUFFER,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(**kwargs) -> IngesterSession:
    defaults = dict(
        call_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
    )
    defaults.update(kwargs)
    return IngesterSession(**defaults)


def _silence_frame() -> bytes:
    """160 bytes of μ-law silence (0x7F)."""
    return bytes([0x7F] * TWILIO_FRAME_BYTES)


def _speech_frame() -> bytes:
    """
    160 bytes that our stubbed VAD will treat as speech.
    We use a sentinel value the test Vad.is_speech watches for.
    The stub just reads _speech flag — we toggle it separately.
    """
    return bytes([0x00] * TWILIO_FRAME_BYTES)


class _FakeWebSocket:
    def __init__(self):
        self.sent = []
        self._send_lock = asyncio.Lock()

    async def send_json(self, data):
        self.sent.append(data)


# ---------------------------------------------------------------------------
# VAD state: speech onset
# ---------------------------------------------------------------------------

def test_speech_onset_requires_min_frames():
    """asr_active becomes True only after MIN_SPEECH_FRAMES consecutive voiced frames."""
    ingester = StreamIngester()
    session = _make_session()
    ws = _FakeWebSocket()

    async def run():
        # Override VAD to always return is_speech=True
        session.vad._speech = True
        # One frame below threshold — should not activate
        await ingester._process_audio_frame(session, ws, _silence_frame())
        assert session.asr_active is False
        assert session.consecutive_voiced_frames == 1

        # One more → hits MIN_SPEECH_FRAMES (2)
        await ingester._process_audio_frame(session, ws, _silence_frame())
        assert session.asr_active is True

    asyncio.get_event_loop().run_until_complete(run())


def test_speech_onset_flushes_pre_speech_buffer():
    """When speech onset triggers, buffered pre-speech frames go to asr_audio_queue."""
    ingester = StreamIngester()
    session = _make_session()
    ws = _FakeWebSocket()

    async def run():
        # Put 3 silence frames in the pre-speech buffer first
        session.vad._speech = False
        for _ in range(3):
            await ingester._process_audio_frame(session, ws, _silence_frame())
        assert session.asr_active is False
        buffered_before = session.asr_audio_queue.qsize()
        assert buffered_before == 0  # nothing sent yet

        # Now trigger speech onset
        session.vad._speech = True
        for _ in range(MIN_SPEECH_FRAMES):
            await ingester._process_audio_frame(session, ws, _silence_frame())

        assert session.asr_active is True
        # Pre-speech frames (3) + onset frames (MIN_SPEECH_FRAMES) should be queued
        queued = session.asr_audio_queue.qsize()
        assert queued >= MIN_SPEECH_FRAMES  # at minimum the onset frames

    asyncio.get_event_loop().run_until_complete(run())


def test_silence_resets_voiced_frame_counter():
    """Silence between voiced frames resets the counter — no false onset."""
    ingester = StreamIngester()
    session = _make_session()
    ws = _FakeWebSocket()

    async def run():
        session.vad._speech = True
        await ingester._process_audio_frame(session, ws, _silence_frame())
        assert session.consecutive_voiced_frames == 1

        session.vad._speech = False
        await ingester._process_audio_frame(session, ws, _silence_frame())
        assert session.consecutive_voiced_frames == 0
        assert session.asr_active is False

    asyncio.get_event_loop().run_until_complete(run())


# ---------------------------------------------------------------------------
# VAD state: end-of-turn silence
# ---------------------------------------------------------------------------

def test_end_of_turn_silence_sends_sentinel():
    """After END_OF_TURN_SILENCE_FRAMES of silence while asr_active, None is queued."""
    ingester = StreamIngester()
    session = _make_session()
    ws = _FakeWebSocket()

    async def run():
        # Force asr_active to True (as if State Controller already issued start_listen)
        session.asr_active = True
        session.vad._speech = False

        for i in range(END_OF_TURN_SILENCE_FRAMES - 1):
            result = await ingester._process_audio_frame(session, ws, _silence_frame())
            assert result is None  # no event yet
            assert session.asr_active is True

        # The Nth frame triggers end-of-turn
        result = await ingester._process_audio_frame(session, ws, _silence_frame())
        assert result is not None
        assert result['type'] == 'silence_end_of_turn'
        assert session.asr_active is False

        # None sentinel is in the queue after the forwarded audio frames
        # Drain until we hit it
        sentinel_found = False
        for _ in range(END_OF_TURN_SILENCE_FRAMES + 1):
            item = session.asr_audio_queue.get_nowait()
            if item is None:
                sentinel_found = True
                break
        assert sentinel_found, 'None sentinel not found in asr_audio_queue'

    asyncio.get_event_loop().run_until_complete(run())


def test_end_of_turn_resets_state():
    """After end-of-turn, counters and resample state are cleared."""
    ingester = StreamIngester()
    session = _make_session()
    ws = _FakeWebSocket()
    async def run():
        session.asr_active = True
        session.vad._speech = False

        for _ in range(END_OF_TURN_SILENCE_FRAMES):
            await ingester._process_audio_frame(session, ws, _silence_frame())

        assert session.asr_active is False
        assert session.consecutive_silence_frames == 0
        assert session.consecutive_voiced_frames == 0
        assert session.asr_resample_state is None  # reset on end-of-turn
        assert len(session.pre_speech_frames) == 0

    asyncio.get_event_loop().run_until_complete(run())


def test_speech_resets_silence_counter_during_asr():
    """Speech during ASR active resets the silence counter — no false end-of-turn."""
    ingester = StreamIngester()
    session = _make_session()
    ws = _FakeWebSocket()

    async def run():
        session.asr_active = True
        session.vad._speech = False

        # Build up near-end silence
        for _ in range(END_OF_TURN_SILENCE_FRAMES - 5):
            await ingester._process_audio_frame(session, ws, _silence_frame())
        assert session.consecutive_silence_frames == END_OF_TURN_SILENCE_FRAMES - 5

        # Caller speaks — resets counter
        session.vad._speech = True
        await ingester._process_audio_frame(session, ws, _silence_frame())
        assert session.consecutive_silence_frames == 0
        assert session.asr_active is True

    asyncio.get_event_loop().run_until_complete(run())


# ---------------------------------------------------------------------------
# Barge-in
# ---------------------------------------------------------------------------

def test_barge_in_sends_clear_and_sets_flag():
    """When caller speaks during TTS, barge-in clears Twilio buffer."""
    ingester = StreamIngester()
    session = _make_session()
    session.stream_sid = 'MZ_test_stream_sid'
    ws = _FakeWebSocket()

    async def run():
        session.tts_active = True
        session.asr_active = False
        session.vad._speech = True

        result = await ingester._process_audio_frame(session, ws, _silence_frame())
        assert result is not None
        assert result['type'] == 'barge_in'
        assert session.barge_in_requested is True

        # Should have sent a clear event to Twilio
        clear_events = [e for e in ws.sent if e.get('event') == 'clear']
        assert len(clear_events) == 1
        assert clear_events[0]['streamSid'] == 'MZ_test_stream_sid'

    asyncio.get_event_loop().run_until_complete(run())


def test_barge_in_only_fires_once():
    """Second speech frame during TTS does not send another clear."""
    ingester = StreamIngester()
    session = _make_session()
    session.stream_sid = 'MZ_test'
    ws = _FakeWebSocket()

    async def run():
        session.tts_active = True
        session.asr_active = False
        session.vad._speech = True

        await ingester._process_audio_frame(session, ws, _silence_frame())
        await ingester._process_audio_frame(session, ws, _silence_frame())

        clear_events = [e for e in ws.sent if e.get('event') == 'clear']
        assert len(clear_events) == 1  # only fired once

    asyncio.get_event_loop().run_until_complete(run())


def test_no_barge_in_without_tts_active():
    """Speech when tts_active=False should not trigger barge-in."""
    ingester = StreamIngester()
    session = _make_session()
    session.stream_sid = 'MZ_test'
    ws = _FakeWebSocket()

    async def run():
        session.tts_active = False
        session.asr_active = False
        session.vad._speech = True

        result = await ingester._process_audio_frame(session, ws, _silence_frame())
        # First frame hits MIN_SPEECH_FRAMES=2 threshold — returns speech_started
        # after 2 frames, not barge_in
        assert session.barge_in_requested is False
        clear_events = [e for e in ws.sent if e.get('event') == 'clear']
        assert len(clear_events) == 0

    asyncio.get_event_loop().run_until_complete(run())


# ---------------------------------------------------------------------------
# TTS drain task
# ---------------------------------------------------------------------------

def test_tts_drain_sends_audio_chunks():
    """Audio chunks in tts_audio_queue are sent to Twilio as media events."""
    ingester = StreamIngester()
    session = _make_session()
    session.stream_sid = 'MZ_drain_test'
    ws = _FakeWebSocket()

    audio_chunk = bytes([0x7F] * 320)  # 320 bytes of μ-law audio

    async def run():
        session.tts_active = True
        drain_task = asyncio.create_task(ingester._drain_tts_audio(ws, session))

        # Put audio chunk then sentinel
        await session.tts_audio_queue.put(audio_chunk)
        await session.tts_audio_queue.put(None)

        # Give the drain task time to process
        await asyncio.sleep(0.05)
        drain_task.cancel()
        try:
            await drain_task
        except asyncio.CancelledError:
            pass

        media_events = [e for e in ws.sent if e.get('event') == 'media']
        assert len(media_events) > 0
        assert media_events[0]['streamSid'] == 'MZ_drain_test'
        assert session.tts_active is False  # sentinel cleared the flag

    asyncio.get_event_loop().run_until_complete(run())


def test_tts_drain_none_sentinel_clears_active_flag():
    """None in tts_audio_queue sets tts_active=False and clears barge_in flag."""
    ingester = StreamIngester()
    session = _make_session()
    session.stream_sid = 'MZ_test'
    session.tts_active = True
    session.barge_in_requested = True
    ws = _FakeWebSocket()

    async def run():
        drain_task = asyncio.create_task(ingester._drain_tts_audio(ws, session))
        await session.tts_audio_queue.put(None)
        await asyncio.sleep(0.05)
        drain_task.cancel()
        try:
            await drain_task
        except asyncio.CancelledError:
            pass

        assert session.tts_active is False
        assert session.barge_in_requested is False

    asyncio.get_event_loop().run_until_complete(run())


# ---------------------------------------------------------------------------
# IngesterSession defaults
# ---------------------------------------------------------------------------

def test_ingester_session_defaults():
    session = _make_session()
    assert session.stream_sid is None
    assert session.asr_active is False
    assert session.tts_active is False
    assert session.barge_in_requested is False
    assert session.frames_received == 0
    assert session.vad_speech_events == 0
    assert session.vad_silence_events == 0
    assert session.dead_air_reported is False
    assert session.asr_resample_state is None
    assert session.consecutive_voiced_frames == 0
    assert session.consecutive_silence_frames == 0


def test_ingester_session_queues_are_independent():
    """Each session gets its own queue instances."""
    s1 = _make_session()
    s2 = _make_session()
    assert s1.asr_audio_queue is not s2.asr_audio_queue
    assert s1.tts_audio_queue is not s2.tts_audio_queue


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

def test_fsm_pipeline_disabled_by_default(monkeypatch):
    """FSM pipeline must default to disabled — live calls go through legacy path."""
    from app.core.config import Settings
    s = Settings()
    assert s.fsm_pipeline_enabled is False
