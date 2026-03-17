import sys
import types

if 'webrtcvad' not in sys.modules:
    webrtcvad_module = types.ModuleType('webrtcvad')

    class Vad:  # pragma: no cover - test bootstrap shim
        def set_mode(self, mode):  # noqa: ANN001 - third-party interface
            self.mode = mode

        def is_speech(self, pcm_data, sample_rate):  # noqa: ANN001 - third-party interface
            return False

    webrtcvad_module.Vad = Vad
    sys.modules['webrtcvad'] = webrtcvad_module

from app.services.realtime.session_manager import VoiceSession, VoiceSessionManager
from app.services.telephony.telemetry import CallTelemetry


def test_connected_event_is_passthrough(monkeypatch) -> None:
    recorded_events: list[dict] = []
    monkeypatch.setattr(
        'app.services.telephony.telemetry.call_event_sink.record_event',
        lambda event: recorded_events.append(event),
    )

    manager = VoiceSessionManager()
    session = VoiceSession(call_id='call-123', tenant_id='tenant-123')
    session.telemetry = CallTelemetry(
        call_id='call-123',
        tenant_id='tenant-123',
        route='inbound',
        call_sid='CA123',
        from_number='+18125550100',
        to_number='+18125550101',
        correlation_id='corr-123',
    )
    session.telemetry.bind_agent(agent_id='agent-123', agent_name='Monica')

    handled = manager._handle_passthrough_telephony_event(
        session=session,
        event={
            'event': 'connected',
            'connected': {
                'protocol': 'Call',
                'version': '1.0.0',
            },
        },
    )

    assert handled is True
    assert session.telemetry.anomalies == []
    assert len(recorded_events) == 1
    assert recorded_events[0]['event_type'] == 'call.telephony.stream.connected'
    assert recorded_events[0]['payload'] == {
        'media_stream_event': 'connected',
        'protocol': 'Call',
        'version': '1.0.0',
    }


def test_non_passthrough_event_returns_false() -> None:
    manager = VoiceSessionManager()
    session = VoiceSession(call_id='call-123', tenant_id='tenant-123')

    handled = manager._handle_passthrough_telephony_event(
        session=session,
        event={'event': 'start'},
    )

    assert handled is False
