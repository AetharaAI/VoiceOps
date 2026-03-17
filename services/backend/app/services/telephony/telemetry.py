from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.services.telephony.event_sink import call_event_sink

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
    correlation_id: str = ''
    resolved_agent_id: str = ''
    resolved_agent_name: str = ''
    started_at: str = field(default_factory=utc_now_iso)
    started_monotonic: float = field(default_factory=time.perf_counter)
    timestamps: dict[str, str] = field(default_factory=dict)
    monotonic_points: dict[str, float] = field(default_factory=dict)
    latency_samples: dict[str, list[float]] = field(
        default_factory=lambda: {'asr': [], 'llm': [], 'tts': []}
    )
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
            'correlation_id': self.correlation_id,
            'tenant_id': self.tenant_id,
            'call_id': self.call_id,
            'call_sid': self.call_sid,
            'route': self.route,
            'direction': self.route,
            'from_number': self.from_number,
            'to_number': self.to_number,
            'resolved_agent_id': self.resolved_agent_id,
            'resolved_agent_name': self.resolved_agent_name,
            **extra,
        }

    def _payload_extras(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in payload.items()
            if key
            not in {
                'correlation_id',
                'tenant_id',
                'call_id',
                'call_sid',
                'route',
                'direction',
                'from_number',
                'to_number',
                'resolved_agent_id',
                'resolved_agent_name',
                'latency_ms',
                'llm_provider',
                'llm_model',
                'tts_provider',
                'tts_voice',
                'asr_provider',
            }
        }

    def _observe_latency(self, event: str, latency_ms: Any) -> None:
        if latency_ms is None:
            return
        try:
            latency_value = float(latency_ms)
        except (TypeError, ValueError):
            return

        if event.startswith('call.asr.'):
            self.latency_samples['asr'].append(latency_value)
        elif event.startswith('call.llm.'):
            self.latency_samples['llm'].append(latency_value)
        elif event.startswith('call.tts.'):
            self.latency_samples['tts'].append(latency_value)

    def _emit(self, level: str, event: str, **extra: Any) -> None:
        payload = self.payload(**extra)
        getattr(logger, level)(event, extra=payload)
        self._observe_latency(event, payload.get('latency_ms'))
        call_event_sink.record_event(
            call_event_sink.build_event(
                event_type=event,
                level=level,
                call_id=self.call_id,
                call_sid=self.call_sid,
                tenant_id=self.tenant_id,
                direction=self.route,
                route=self.route,
                agent_id=self.resolved_agent_id,
                agent_name=self.resolved_agent_name,
                correlation_id=self.correlation_id,
                from_number=self.from_number,
                to_number=self.to_number,
                latency_ms=payload.get('latency_ms'),
                llm_provider=payload.get('llm_provider', ''),
                llm_model=payload.get('llm_model', ''),
                tts_provider=payload.get('tts_provider', ''),
                tts_voice=payload.get('tts_voice', ''),
                asr_provider=payload.get('asr_provider', ''),
                **self._payload_extras(payload),
            )
        )

    def log(self, event: str, **extra: Any) -> None:
        self._emit('info', event, **extra)

    def warning(self, event: str, **extra: Any) -> None:
        self._emit('warning', event, **extra)

    def error(self, event: str, **extra: Any) -> None:
        self._emit('error', event, **extra)

    def latency_summary(self, kind: str) -> dict[str, Any]:
        values = self.latency_samples.get(kind, [])
        if not values:
            return {'count': 0, 'min_ms': None, 'max_ms': None, 'avg_ms': None}
        return {
            'count': len(values),
            'min_ms': round(min(values), 2),
            'max_ms': round(max(values), 2),
            'avg_ms': round(sum(values) / len(values), 2),
        }

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
            'latency_summary': {
                'asr': self.latency_summary('asr'),
                'llm': self.latency_summary('llm'),
                'tts': self.latency_summary('tts'),
            },
            'fallbacks': list(self.fallbacks),
            'anomalies': list(self.anomalies),
            'handoff_attempts': self.handoff_attempts,
        }
