from app.services.telephony.inbound_routing import (
    build_inbound_webhook_payload,
    normalize_phone_number,
    phone_number_matches,
)


def test_normalize_phone_number_handles_common_us_formats() -> None:
    assert normalize_phone_number('(812) 969-1371') == '+18129691371'
    assert normalize_phone_number('+1 812 969 1371') == '+18129691371'
    assert normalize_phone_number('8129691371') == '+18129691371'


def test_phone_number_matches_normalized_twilio_inputs() -> None:
    assert phone_number_matches('+18129691371', '(812) 969-1371') is True
    assert phone_number_matches('(812) 969-1371', '+18129691371') is True
    assert phone_number_matches('+18129691371', '+18124109125') is False


def test_build_inbound_webhook_payload_tracks_forwarded_call_warnings() -> None:
    payload = build_inbound_webhook_payload(
        {
            'From': '+18124109125',
            'To': '+18129691371',
            'CallSid': 'CA123',
            'ForwardedFrom': '+18125550123',
            'CallerName': 'Wireless Caller',
        }
    )

    assert payload.from_number == '+18124109125'
    assert payload.to_number == '+18129691371'
    assert payload.call_sid == 'CA123'
    assert payload.metadata['ForwardedFrom'] == '+18125550123'
    assert 'forwarded_call_detected' in payload.warnings


def test_build_inbound_webhook_payload_reports_missing_metadata() -> None:
    payload = build_inbound_webhook_payload({})

    assert 'missing_from_number' in payload.warnings
    assert 'missing_to_number' in payload.warnings
    assert 'missing_call_sid' in payload.warnings
