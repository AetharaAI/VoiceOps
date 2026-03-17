from pathlib import Path

from app.core.config import get_settings
from app.services.telephony import event_sink as event_sink_module
from app.services.telephony.event_sink import CallEventSink


def test_call_event_sink_keeps_call_sid_and_call_id_in_one_file(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(event_sink_module, 'REPO_ROOT', tmp_path)
    monkeypatch.setattr(settings, 'call_log_root', 'logs/calls-test')
    monkeypatch.setattr(settings, 'redis_streams_enabled', False)

    sink = CallEventSink()
    first_event = sink.build_event(
        event_type='telephony.inbound.webhook.received',
        call_sid='CA123',
        direction='inbound',
        route='inbound',
        from_number='+18123632424',
        to_number='+18129691371',
    )
    sink.record_event(first_event)

    second_event = sink.build_event(
        event_type='call.session.started',
        call_id='call-123',
        call_sid='CA123',
        tenant_id='tenant-123',
        direction='inbound',
        route='inbound',
        agent_name='Monica',
        from_number='+18123632424',
        to_number='+18129691371',
    )
    sink.record_event(second_event)
    sink.close_call('call-123', 'CA123')

    files = list((tmp_path / 'logs/calls-test').glob('*/*.jsonl'))
    assert len(files) == 1

    log = sink.find_by_call_sid(call_sid='CA123', tenant_id='tenant-123')
    assert log is not None
    assert log['call_id'] == 'call-123'
    assert log['call_sid'] == 'CA123'
    assert log['tenant_id'] == 'tenant-123'
    assert log['agent_name'] == 'Monica'
    assert log['event_count'] == 2


def test_latest_logs_filters_by_exact_tenant(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(event_sink_module, 'REPO_ROOT', tmp_path)
    monkeypatch.setattr(settings, 'call_log_root', 'logs/calls-test')
    monkeypatch.setattr(settings, 'redis_streams_enabled', False)

    sink = CallEventSink()
    sink.record_event(
        sink.build_event(
            event_type='call.session.started',
            call_id='call-a',
            call_sid='CAA',
            tenant_id='tenant-a',
            direction='inbound',
            route='inbound',
            agent_name='Monica',
        )
    )
    sink.record_event(
        sink.build_event(
            event_type='call.session.started',
            call_id='call-b',
            call_sid='CAB',
            tenant_id='tenant-b',
            direction='outbound',
            route='outbound',
            agent_name='Sales Agent',
        )
    )
    sink.close_call('call-a', 'CAA')
    sink.close_call('call-b', 'CAB')

    tenant_a_logs = sink.latest_logs(limit=10, tenant_id='tenant-a')
    assert len(tenant_a_logs) == 1
    assert tenant_a_logs[0]['call_sid'] == 'CAA'
