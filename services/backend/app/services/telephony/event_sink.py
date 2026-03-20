from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from redis import asyncio as redis_asyncio

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.telephony.inbound_routing import normalize_phone_number

logger = get_logger(__name__)


def _resolve_runtime_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in current.parents:
        if (candidate / 'requirements.txt').exists() and (candidate / 'app').is_dir():
            return candidate
    return Path.cwd()


REPO_ROOT = _resolve_runtime_root()
TOP_LEVEL_EVENT_FIELDS = {
    'timestamp',
    'event_type',
    'level',
    'call_id',
    'call_sid',
    'tenant_id',
    'direction',
    'route',
    'agent_id',
    'agent_name',
    'trace_id',
    'correlation_id',
    'from_number',
    'to_number',
    'latency_ms',
    'llm_provider',
    'llm_model',
    'llm_mode',
    'tts_provider',
    'tts_voice',
    'asr_provider',
    'log_path',
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _filename_timestamp(timestamp: str) -> str:
    return (
        timestamp.replace(':', '')
        .replace('-', '')
        .replace('+00:00', 'Z')
        .replace('.', '')
    )


def _safe_phone_fragment(number: str | None) -> str:
    normalized = normalize_phone_number(number)
    if not normalized:
        return 'unknown'
    return normalized.replace('+', '')


@dataclass(slots=True)
class CallLogWriter:
    keys: set[str]
    path: Path
    handle: TextIO


class CallEventSink:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._writers: dict[str, CallLogWriter] = {}
        self._paths: dict[str, Path] = {}
        self._lock = threading.Lock()
        self._redis: redis_asyncio.Redis | None = None

    def _root_dir(self) -> Path:
        root = Path(self.settings.call_log_root)
        if root.is_absolute():
            return root
        return REPO_ROOT / root

    def build_event(
        self,
        *,
        event_type: str,
        level: str = 'info',
        timestamp: str | None = None,
        direction: str = '',
        route: str = '',
        call_id: str = '',
        call_sid: str = '',
        tenant_id: str = '',
        agent_id: str = '',
        agent_name: str = '',
        correlation_id: str = '',
        trace_id: str = '',
        from_number: str = '',
        to_number: str = '',
        latency_ms: float | None = None,
        llm_provider: str = '',
        llm_model: str = '',
        llm_mode: str = '',
        tts_provider: str = '',
        tts_voice: str = '',
        asr_provider: str = '',
        **payload: Any,
    ) -> dict[str, Any]:
        event_timestamp = timestamp or utc_now_iso()
        resolved_direction = direction or route or 'unknown'
        event: dict[str, Any] = {
            'timestamp': event_timestamp,
            'event_type': event_type,
            'level': level,
            'call_id': call_id,
            'call_sid': call_sid,
            'tenant_id': tenant_id,
            'direction': resolved_direction,
            'route': route or resolved_direction,
            'agent_id': agent_id,
            'agent_name': agent_name,
            'trace_id': trace_id or correlation_id,
            'correlation_id': correlation_id,
            'from_number': from_number,
            'to_number': to_number,
            'latency_ms': latency_ms,
            'llm_provider': llm_provider,
            'llm_model': llm_model,
            'llm_mode': llm_mode,
            'tts_provider': tts_provider,
            'tts_voice': tts_voice,
            'asr_provider': asr_provider,
            'payload': {key: value for key, value in payload.items() if value is not None},
        }
        return event

    def _writer_key(self, event: dict[str, Any]) -> str:
        call_id = event.get('call_id') or ''
        call_sid = event.get('call_sid') or ''
        return call_id or call_sid

    def _writer_keys(self, event: dict[str, Any]) -> list[str]:
        return [key for key in {event.get('call_id') or '', event.get('call_sid') or ''} if key]

    def _log_path(self, event: dict[str, Any]) -> Path:
        timestamp = event.get('timestamp') or utc_now_iso()
        day = timestamp[:10]
        direction = event.get('direction') or 'unknown'
        peer_phone = event.get('from_number') if direction == 'inbound' else event.get('to_number')
        phone_fragment = _safe_phone_fragment(peer_phone)
        call_fragment = event.get('call_sid') or event.get('call_id') or 'unknown'
        filename = f'{direction}-{phone_fragment}-{call_fragment}-{_filename_timestamp(timestamp)}.jsonl'
        return self._root_dir() / day / filename

    def _ensure_writer(self, event: dict[str, Any]) -> CallLogWriter | None:
        keys = self._writer_keys(event)
        if not keys:
            return None

        with self._lock:
            for key in keys:
                writer = self._writers.get(key)
                if writer is not None and not writer.handle.closed:
                    for alias in keys:
                        self._writers[alias] = writer
                        self._paths[alias] = writer.path
                        writer.keys.add(alias)
                    return writer

            path = next((self._paths[key] for key in keys if key in self._paths), None) or self._log_path(event)
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = path.open('a', encoding='utf-8')
            writer = CallLogWriter(keys=set(keys), path=path, handle=handle)
            for key in keys:
                self._writers[key] = writer
                self._paths[key] = path
            return writer

    def record_event(self, event: dict[str, Any]) -> dict[str, Any]:
        writer = self._ensure_writer(event)
        if writer is not None:
            event['log_path'] = str(writer.path)
            try:
                writer.handle.write(json.dumps(event, ensure_ascii=True, default=str) + '\n')
                writer.handle.flush()
            except Exception as exc:
                logger.warning(
                    'call.log.persist_failed',
                    extra={
                        'correlation_id': event.get('correlation_id', ''),
                        'tenant_id': event.get('tenant_id', ''),
                        'call_id': event.get('call_id', ''),
                        'call_sid': event.get('call_sid', ''),
                        'event_type': event.get('event_type', ''),
                        'error_type': type(exc).__name__,
                        'error': str(exc),
                    },
                )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return event

        loop.create_task(self._publish_to_streams(event))
        return event

    async def _get_redis(self) -> redis_asyncio.Redis | None:
        if not self.settings.redis_streams_enabled:
            return None
        if self._redis is None:
            self._redis = redis_asyncio.from_url(self.settings.redis_url, decode_responses=True)
        return self._redis

    async def _publish_to_streams(self, event: dict[str, Any]) -> None:
        try:
            client = await self._get_redis()
            if client is None:
                return

            base_fields = {
                'timestamp': event.get('timestamp', ''),
                'event_type': event.get('event_type', ''),
                'call_id': event.get('call_id', ''),
                'call_sid': event.get('call_sid', ''),
                'tenant_id': event.get('tenant_id', ''),
                'direction': event.get('direction', ''),
                'route': event.get('route', ''),
                'agent_id': event.get('agent_id', ''),
                'agent_name': event.get('agent_name', ''),
                'trace_id': event.get('trace_id', ''),
                'correlation_id': event.get('correlation_id', ''),
                'latency_ms': '' if event.get('latency_ms') is None else str(event.get('latency_ms')),
                'llm_provider': event.get('llm_provider', ''),
                'llm_model': event.get('llm_model', ''),
                'llm_mode': event.get('llm_mode', ''),
                'tts_provider': event.get('tts_provider', ''),
                'tts_voice': event.get('tts_voice', ''),
                'asr_provider': event.get('asr_provider', ''),
                'payload_json': json.dumps(event.get('payload', {}), ensure_ascii=True, default=str),
            }
            await client.xadd(self.settings.redis_call_event_stream, base_fields)

            if event.get('event_type', '').startswith('transcript.'):
                payload = event.get('payload', {})
                transcript_fields = {
                    **base_fields,
                    'speaker': str(payload.get('speaker', '')),
                    'text': str(payload.get('text', '')),
                    'is_final': str(payload.get('is_final', '')),
                    'started_ms': '' if payload.get('started_ms') is None else str(payload.get('started_ms')),
                    'ended_ms': '' if payload.get('ended_ms') is None else str(payload.get('ended_ms')),
                }
                await client.xadd(self.settings.redis_call_transcript_stream, transcript_fields)

            if event.get('event_type') == 'call.extraction.ready':
                extraction_fields = {
                    **base_fields,
                    'artifact_type': 'extraction',
                    'artifact_json': json.dumps(event.get('payload', {}), ensure_ascii=True, default=str),
                }
                await client.xadd(self.settings.redis_call_extraction_stream, extraction_fields)

            if event.get('event_type') == 'call.action.ready':
                action_fields = {
                    **base_fields,
                    'artifact_type': 'action',
                    'artifact_json': json.dumps(event.get('payload', {}), ensure_ascii=True, default=str),
                }
                await client.xadd(self.settings.redis_call_action_stream, action_fields)
        except Exception as exc:
            logger.warning(
                'call.stream.publish_failed',
                extra={
                    'correlation_id': event.get('correlation_id', ''),
                    'tenant_id': event.get('tenant_id', ''),
                    'call_id': event.get('call_id', ''),
                    'call_sid': event.get('call_sid', ''),
                    'event_type': event.get('event_type', ''),
                    'error_type': type(exc).__name__,
                    'error': str(exc),
                },
            )

    def close_call(self, call_id: str, call_sid: str = '') -> None:
        closed_writer_ids: set[int] = set()
        for key in filter(None, {call_id, call_sid}):
            with self._lock:
                writer = self._writers.pop(key, None)
            if writer is None or id(writer) in closed_writer_ids:
                continue
            closed_writer_ids.add(id(writer))
            if not writer.handle.closed:
                try:
                    writer.handle.flush()
                    writer.handle.close()
                except Exception:
                    pass

    def latest_logs(self, *, limit: int = 1, tenant_id: str = '') -> list[dict[str, Any]]:
        root = self._root_dir()
        if not root.exists():
            return []
        files = sorted(root.glob('*/*.jsonl'), key=lambda path: path.stat().st_mtime, reverse=True)
        results: list[dict[str, Any]] = []
        for path in files:
            log = self.load_log(path=path)
            if not log:
                continue
            if tenant_id and log.get('tenant_id') != tenant_id:
                continue
            results.append(log)
            if len(results) >= limit:
                break
        return results

    def find_by_call_sid(self, *, call_sid: str, tenant_id: str = '') -> dict[str, Any] | None:
        root = self._root_dir()
        if not root.exists():
            return None
        for path in sorted(root.glob('*/*.jsonl'), key=lambda item: item.stat().st_mtime, reverse=True):
            log = self.load_log(path=path)
            if not log:
                continue
            if log.get('call_sid') != call_sid:
                continue
            if tenant_id and log.get('tenant_id') != tenant_id:
                continue
            return log
        return None

    def load_log(self, *, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None

        events: list[dict[str, Any]] = []
        first_event: dict[str, Any] | None = None
        final_summary: dict[str, Any] | None = None
        resolved_context = {
            'call_id': '',
            'call_sid': '',
            'tenant_id': '',
            'direction': '',
            'agent_name': '',
            'started_at': '',
        }
        with path.open('r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        'call.log.load_failed',
                        extra={
                            'correlation_id': '',
                            'tenant_id': '',
                            'call_id': '',
                            'call_sid': '',
                            'path': str(path),
                            'error_type': type(exc).__name__,
                            'error': str(exc),
                        },
                    )
                    continue
                if first_event is None:
                    first_event = event
                if event.get('event_type') == 'call.summary.final':
                    final_summary = event
                resolved_context['call_id'] = resolved_context['call_id'] or event.get('call_id', '')
                resolved_context['call_sid'] = resolved_context['call_sid'] or event.get('call_sid', '')
                resolved_context['tenant_id'] = resolved_context['tenant_id'] or event.get('tenant_id', '')
                resolved_context['direction'] = resolved_context['direction'] or event.get('direction', '')
                resolved_context['agent_name'] = resolved_context['agent_name'] or event.get('agent_name', '')
                resolved_context['started_at'] = resolved_context['started_at'] or event.get('timestamp', '')
                events.append(event)

        if first_event is None:
            return None

        return {
            'path': str(path),
            'call_id': resolved_context['call_id'],
            'call_sid': resolved_context['call_sid'],
            'tenant_id': resolved_context['tenant_id'],
            'direction': resolved_context['direction'],
            'agent_name': resolved_context['agent_name'],
            'started_at': resolved_context['started_at'],
            'event_count': len(events),
            'summary': final_summary.get('payload', {}) if final_summary else {},
            'events': events,
        }


call_event_sink = CallEventSink()
