from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


@dataclass(slots=True)
class CallTelemetry:
    call_id: str
    tenant_id: str
    route: str
    call_sid: str = ''
    from_number: str = ''
    to_number: str = ''
    resolved_agent_id: str = ''
    resolved_agent_name: str = ''
    started_at: str = field(default_factory=utc_now_iso)
    started_monotonic: float = field(default_factory=time.perf_counter)
    timestamps: dict[str, str] = field(default_factory=dict)
    monotonic_points: dict[str, float] = field(default_factory=dict)
    fallbacks: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    handoff_attempts: int = 0

    def bind_agent(self, *, agent_id: str | None, agent_name: str | None) -> None:
        self.resolved_agent_id = agent_id or ''
        self.resolved_agent_name = agent_name or ''

    def mark(self, step: str, **extra: Any) -> None:
        if step in self.timestamps:
            return
        self.timestamps[step] = utc_now_iso()
        self.monotonic_points[step] = time.perf_counter()
        self.log('call.step', step=step, **extra)

    def latency_ms(self, start_step: str, end_step: str) -> float | None:
        start = self.monotonic_points.get(start_step)
        end = self.monotonic_points.get(end_step)
        if start is None or end is None:
            return None
        return round(max(0.0, (end - start) * 1000), 2)

    def latency_ms_since_start(self, step: str) -> float | None:
        end = self.monotonic_points.get(step)
        if end is None:
            return None
        return round(max(0.0, (end - self.started_monotonic) * 1000), 2)

    def add_fallback(self, reason: str, **extra: Any) -> None:
        if reason in self.fallbacks:
            return
        self.fallbacks.append(reason)
        self.log('call.fallback', fallback_reason=reason, **extra)

    def add_anomaly(self, code: str, **extra: Any) -> None:
        if code in self.anomalies:
            return
        self.anomalies.append(code)
        self.log('call.anomaly', anomaly_code=code, **extra)

    def note_handoff_attempt(self, reason: str | None = None, **extra: Any) -> None:
        self.handoff_attempts += 1
        self.log('call.handoff.attempt', handoff_reason=reason or '', **extra)

    def payload(self, **extra: Any) -> dict[str, Any]:
        return {
            'correlation_id': '',
            'tenant_id': self.tenant_id,
            'call_id': self.call_id,
            'call_sid': self.call_sid,
            'route': self.route,
            'from_number': self.from_number,
            'to_number': self.to_number,
            'resolved_agent_id': self.resolved_agent_id,
            'resolved_agent_name': self.resolved_agent_name,
            **extra,
        }

    def log(self, event: str, **extra: Any) -> None:
        logger.info(event, extra=self.payload(**extra))

    def warning(self, event: str, **extra: Any) -> None:
        logger.warning(event, extra=self.payload(**extra))

    def error(self, event: str, **extra: Any) -> None:
        logger.error(event, extra=self.payload(**extra))

    def snapshot(self) -> dict[str, Any]:
        return {
            'route': self.route,
            'call_sid': self.call_sid,
            'from_number': self.from_number,
            'to_number': self.to_number,
            'resolved_agent_id': self.resolved_agent_id,
            'resolved_agent_name': self.resolved_agent_name,
            'timestamps': dict(self.timestamps),
            'latency_ms': {
                'time_to_first_greeting_audio': self.latency_ms_since_start('tts_first_audio_chunk'),
                'time_to_asr_start': self.latency_ms_since_start('asr_started'),
                'time_to_first_asr_partial': self.latency_ms_since_start('asr_first_partial'),
                'time_to_first_asr_final': self.latency_ms_since_start('asr_first_final'),
                'llm_request': self.latency_ms('llm_request_started', 'llm_request_completed'),
                'tts_request': self.latency_ms('tts_request_started', 'tts_request_completed'),
                'time_to_hangup': self.latency_ms_since_start('call_ended'),
            },
            'fallbacks': list(self.fallbacks),
            'anomalies': list(self.anomalies),
            'handoff_attempts': self.handoff_attempts,
        }
