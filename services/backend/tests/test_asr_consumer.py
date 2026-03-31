import asyncio
import types

import pytest

from app.services.asr.consumer import ASRConsumer


class _FakeFinal:
    def __init__(self, text: str, started_ms=None, ended_ms=None) -> None:
        self.text = text
        self.started_ms = started_ms
        self.ended_ms = ended_ms


class _FakeASRStream:
    def __init__(self, final: _FakeFinal) -> None:
        self._final = final
        self.frames = []
        self.session_id = 'fake-asr-session'

    async def send_audio_frame(self, frame: bytes) -> None:
        self.frames.append(frame)

    async def end_stream(self) -> None:
        return None

    async def wait_for_final(self, timeout_seconds: float = 5.0) -> _FakeFinal:
        return self._final

    async def close(self) -> None:
        return None


class _FakeASRClient:
    def __init__(self, final: _FakeFinal) -> None:
        self._final = final

    async def start_stream(self, call_id: str, on_event=None) -> _FakeASRStream:
        return _FakeASRStream(self._final)


class _FakePublisher:
    def __init__(self) -> None:
        self.events = []

    async def publish(self, event) -> None:
        self.events.append(event)


def _fake_session():
    return types.SimpleNamespace(asr_audio_queue=asyncio.Queue())


@pytest.mark.asyncio
async def test_asr_consumer_drops_empty_noise_final_without_signal():
    consumer = ASRConsumer(client=_FakeASRClient(_FakeFinal(text='')))
    publisher = _FakePublisher()
    session = _fake_session()
    base = types.SimpleNamespace(session_id='s1', call_id='c1')

    await session.asr_audio_queue.put(b'\x00' * 320)
    await session.asr_audio_queue.put(None)

    await consumer._handle_listen_window(
        session=session,
        publisher=publisher,
        base=base,
        timeout_seconds=10.0,
    )

    # No partials, no timing bounds, empty final => drop to avoid prompt churn.
    assert len(publisher.events) == 0


@pytest.mark.asyncio
async def test_asr_consumer_publishes_non_empty_final():
    consumer = ASRConsumer(client=_FakeASRClient(_FakeFinal(text='hello world', started_ms=0, ended_ms=1200)))
    publisher = _FakePublisher()
    session = _fake_session()
    base = types.SimpleNamespace(session_id='s1', call_id='c1')

    await session.asr_audio_queue.put(b'\x00' * 320)
    await session.asr_audio_queue.put(None)

    await consumer._handle_listen_window(
        session=session,
        publisher=publisher,
        base=base,
        timeout_seconds=10.0,
    )

    assert len(publisher.events) == 1
