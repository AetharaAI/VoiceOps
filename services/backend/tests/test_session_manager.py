import sys
import types
from uuid import uuid4

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
from app.models.models import Agent, Call, CallDirection, CallStatus


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


def test_mark_event_is_passthrough(monkeypatch) -> None:
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
            'event': 'mark',
            'mark': {
                'name': 'tts-chunk-finished',
            },
        },
    )

    assert handled is True
    assert session.telemetry.anomalies == []
    assert len(recorded_events) == 1
    assert recorded_events[0]['event_type'] == 'call.telephony.stream.mark'
    assert recorded_events[0]['payload'] == {
        'media_stream_event': 'mark',
        'mark_name': 'tts-chunk-finished',
    }


def test_retry_reason_prefers_partial_unclear_when_partial_exists() -> None:
    manager = VoiceSessionManager()
    session = VoiceSession(call_id='call-123', tenant_id='tenant-123')
    session.last_asr_partial = 'hel'

    reason = manager._retry_reason_from_transcript(session=session, transcript_text='')

    assert reason == 'partial_unclear_speech'


def test_retry_reason_prefers_interruption_flag() -> None:
    manager = VoiceSessionManager()
    session = VoiceSession(call_id='call-123', tenant_id='tenant-123')
    session.interrupted_turn = True
    session.last_asr_partial = 'hello'

    reason = manager._retry_reason_from_transcript(session=session, transcript_text='hello?')

    assert reason == 'caller_interruption'


def test_build_operator_artifacts_uses_inbound_builder_config() -> None:
    manager = VoiceSessionManager()
    session = VoiceSession(call_id='call-123', tenant_id='tenant-123')
    session.collected_fields = {'intent': 'book a demo', 'name': 'Bob'}
    session.llm_mode = 'live'
    session.detected_intent = 'booking'
    session.last_asr_final = 'Can I make an appointment?'

    agent = Agent(
        id=uuid4(),
        tenant_id=uuid4(),
        name='SyndicateAI',
        persona='Front desk',
        script='Help callers',
        required_fields={
            'intent': {'prompt': 'What are you calling about?'},
            'name': {'prompt': 'Can I have your full name?'},
            'callback_number': {'prompt': 'Best callback number?'},
        },
        tools_config={'schedule_appointment': True},
        policy_config={'runtime': {'llm_model': 'qwen3.5-35b'}},
        workflow_dsl={
            'workflow_type': 'inbound',
            'inbound_builder': {
                'crm_mapping': {'contact': ['name', 'callback_number']},
                'action_config': {'schedule_appointment': True, 'send_sms': True},
            },
        },
    )
    call = Call(
        id=uuid4(),
        tenant_id=uuid4(),
        direction=CallDirection.inbound,
        status=CallStatus.completed,
        from_number='+18125550100',
        to_number='+18125550101',
        context_payload={'telephony': {'selected_agent': {'id': 'agent-123', 'name': 'SyndicateAI'}}},
    )

    artifacts = manager._build_operator_artifacts(call=call, agent=agent, session=session)

    assert artifacts['extraction']['fields_captured'] == {'intent': 'book a demo', 'name': 'Bob'}
    assert artifacts['extraction']['missing_fields'] == ['callback_number']
    assert artifacts['extraction']['crm_mapping'] == {'contact': ['name', 'callback_number']}
    assert artifacts['action']['action_config'] == {'schedule_appointment': True, 'send_sms': True}
    assert artifacts['action']['follow_up_needed'] is True
