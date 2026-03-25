"""
VoiceOps FSM — Audit Consumer
================================

Consumer group: voice:audit

Reads ALL events from the per-call Redis stream and writes them to:
  1. A per-call JSONL file under {call_log_root}/{call_id}/fsm_events.jsonl
  2. (Phase 4) Postgres TranscriptSegment rows for transcript events

The Audit Consumer is purely observational — it publishes nothing.
It runs as an asyncio task alongside the StreamIngester and can be
started/stopped without affecting call logic.

JSONL file format (one JSON object per line):
    {
        "event_id": "...",
        "event_type": "asr.transcript",
        "timestamp": "2026-03-25T12:00:00Z",
        "session_id": "...",
        "call_id": "...",
        "payload": { ... }
    }
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.streams.event_schemas import FSMEventBase
from app.services.streams.publisher import StreamPublisher

logger = get_logger(__name__)

STREAM_POLL_BLOCK_MS = 500


class AuditConsumer:
    """
    Writes all FSM events for one call to a JSONL log file.
    Does not publish any events back to the stream.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    async def run(
        self,
        *,
        session_id: str,
        call_id: str,
        tenant_id: str,
        redis: Redis,
        publisher: StreamPublisher,  # held for interface consistency, not used
    ) -> None:
        """Consumer loop for one call."""
        stream_key = self._settings.per_call_stream_key(session_id)
        group_name = self._settings.redis_cg_audit
        consumer_name = f'audit_{session_id[:8]}'

        try:
            await redis.xgroup_create(stream_key, group_name, id='0', mkstream=True)
        except Exception:
            pass

        log_file = self._open_log(call_id)

        logger.info('audit_consumer.started', extra={
            'correlation_id': '', 'tenant_id': tenant_id,
            'call_id': call_id, 'session_id': session_id,
            'log_path': log_file.name if log_file else '(none)',
        })

        try:
            while True:
                entries = await redis.xreadgroup(
                    group_name, consumer_name,
                    {stream_key: '>'},
                    count=20,
                    block=STREAM_POLL_BLOCK_MS,
                )
                if not entries:
                    continue

                for _stream, messages in entries:
                    for entry_id, raw_fields in messages:
                        et = self._write_event(raw_fields, log_file)
                        try:
                            await redis.xack(stream_key, group_name, entry_id)
                        except Exception:
                            pass
                        if et == 'call.ended':
                            return

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error('audit_consumer.fatal', extra={
                'correlation_id': '', 'tenant_id': tenant_id,
                'call_id': call_id, 'error': str(exc),
            })
        finally:
            if log_file is not None:
                try:
                    log_file.flush()
                    log_file.close()
                except Exception:
                    pass
            logger.info('audit_consumer.ended', extra={
                'correlation_id': '', 'tenant_id': tenant_id,
                'call_id': call_id,
            })

    # ------------------------------------------------------------------
    # Log file helpers
    # ------------------------------------------------------------------

    def _open_log(self, call_id: str) -> TextIO | None:
        """Open (or create) the per-call FSM event log file."""
        try:
            log_root = Path(self._settings.call_log_root)
            call_dir = log_root / call_id
            call_dir.mkdir(parents=True, exist_ok=True)
            log_path = call_dir / 'fsm_events.jsonl'
            return log_path.open('a', encoding='utf-8')
        except Exception as exc:
            logger.warning('audit_consumer.log_open_failed', extra={
                'correlation_id': '', 'tenant_id': '', 'call_id': call_id,
                'error': str(exc),
            })
            return None

    def _write_event(self, raw_fields: dict, log_file: TextIO | None) -> str:
        """Parse one stream entry and write it to the JSONL log."""
        raw = raw_fields.get('data') or raw_fields.get(b'data', b'')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8', errors='replace')
        if not raw:
            return ''

        try:
            base = FSMEventBase.model_validate_json(raw)
        except Exception:
            return ''

        if log_file is not None:
            try:
                log_file.write(base.model_dump_json() + '\n')
                # Flush after transcript/transition events for real-time visibility
                if base.event_type in ('asr.transcript', 'state.transition', 'call.ended'):
                    log_file.flush()
            except Exception:
                pass

        return base.event_type


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

audit_consumer = AuditConsumer()
