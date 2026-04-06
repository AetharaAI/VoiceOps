from fastapi import HTTPException

from app.api.routes.portal import _coerce_mode


def test_coerce_mode_accepts_supported_values():
    assert _coerce_mode('enabled') == 'enabled'
    assert _coerce_mode('bypass') == 'bypass'
    assert _coerce_mode('after_hours_only') == 'after_hours_only'
    assert _coerce_mode(' AFTER_HOURS_ONLY ') == 'after_hours_only'


def test_coerce_mode_rejects_unsupported_values():
    try:
        _coerce_mode('maintenance')
        assert False, 'Expected HTTPException'
    except HTTPException as exc:
        assert exc.status_code == 400
