"""
VoiceOps FSM — LLM Consumer
==============================

Consumer group: voice:llm

Handles llm.extract and llm.classify events from the State Controller.
Publishes llm.extracted (field values) and llm.intent (intent lane).

Phase 3 status
--------------
The State Controller currently handles LLM calls inline and publishes
llm.extract + llm.extracted events for observability only. This consumer
is NOT wired into handle_ws() in Phase 3.

Phase 4: Start this task from handle_ws() AND update the State Controller
to emit llm.extract and await llm.extracted (remove inline path from
_on_asr_transcript). The State Controller will then be LLM-call-free.

Field extraction
----------------
llm.extract payload has: task, transcript_text, target_fields, fsm_state,
context_snapshot (collected_fields at time of request).

Intent classification
---------------------
llm.classify payload has: transcript_text, available_lanes, fsm_state,
context_snapshot.
"""

from __future__ import annotations

import asyncio

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.agent_runtime.runtime import AgentRuntime
from app.services.streams.event_schemas import (
    FSMEventBase,
    LLMExtractedEvent,
    LLMExtractedPayload,
    LLMIntentEvent,
    LLMIntentPayload,
    make_event,
)
from app.services.streams.publisher import StreamPublisher

logger = get_logger(__name__)

STREAM_POLL_BLOCK_MS = 500


class LLMConsumer:
    """
    Event-driven LLM consumer. Handles field extraction and intent
    classification from caller transcripts.

    NOT started in Phase 3 — State Controller handles LLM inline.
    Start in Phase 4 after removing inline LLM from State Controller.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._runtime = AgentRuntime()

    async def run(
        self,
        *,
        session_id: str,
        call_id: str,
        tenant_id: str,
        redis: Redis,
        publisher: StreamPublisher,
    ) -> None:
        """Consumer loop for one call."""
        stream_key = self._settings.per_call_stream_key(session_id)
        group_name = self._settings.redis_cg_llm
        consumer_name = f'llm_{session_id[:8]}'

        try:
            await redis.xgroup_create(stream_key, group_name, id='0', mkstream=True)
        except Exception:
            pass

        logger.info('llm_consumer.started', extra={
            'correlation_id': '', 'tenant_id': tenant_id,
            'call_id': call_id, 'session_id': session_id,
        })

        try:
            while True:
                entries = await redis.xreadgroup(
                    group_name, consumer_name,
                    {stream_key: '>'},
                    count=5,
                    block=STREAM_POLL_BLOCK_MS,
                )
                if not entries:
                    continue

                for _stream, messages in entries:
                    for entry_id, raw_fields in messages:
                        et = await self._dispatch(
                            publisher, raw_fields,
                            session_id=session_id, call_id=call_id,
                            tenant_id=tenant_id,
                        )
                        try:
                            await redis.xack(stream_key, group_name, entry_id)
                        except Exception:
                            pass
                        if et == 'call.ended':
                            return

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error('llm_consumer.fatal', extra={
                'correlation_id': '', 'tenant_id': tenant_id,
                'call_id': call_id, 'error': str(exc),
            })
        finally:
            logger.info('llm_consumer.ended', extra={
                'correlation_id': '', 'tenant_id': tenant_id,
                'call_id': call_id,
            })

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        publisher: StreamPublisher,
        raw_fields: dict,
        *,
        session_id: str,
        call_id: str,
        tenant_id: str,
    ) -> str:
        raw = raw_fields.get('data') or raw_fields.get(b'data', b'')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8', errors='replace')
        if not raw:
            return ''

        try:
            base = FSMEventBase.model_validate_json(raw)
        except Exception:
            return ''

        et = base.event_type

        if et == 'llm.extract':
            await self._handle_extract(publisher, base,
                                       call_id=call_id, tenant_id=tenant_id)
        elif et == 'llm.classify':
            await self._handle_classify(publisher, base,
                                        call_id=call_id, tenant_id=tenant_id)

        return et

    # ------------------------------------------------------------------
    # Field extraction
    # ------------------------------------------------------------------

    async def _handle_extract(
        self,
        publisher: StreamPublisher,
        base: FSMEventBase,
        *,
        call_id: str,
        tenant_id: str,
    ) -> None:
        """
        Extract structured field values from transcript.
        Uses AgentRuntime heuristic extraction (no external LLM required).
        Publishes llm.extracted.
        """
        payload = base.payload
        transcript = (
            payload.get('transcript_text', '')
            if isinstance(payload, dict)
            else getattr(payload, 'transcript_text', '')
        )
        target_fields = (
            payload.get('target_fields', [])
            if isinstance(payload, dict)
            else getattr(payload, 'target_fields', [])
        )
        collected = (
            payload.get('context_snapshot', {})
            if isinstance(payload, dict)
            else getattr(payload, 'context_snapshot', {})
        )
        task = (
            payload.get('task', 'field_extract')
            if isinstance(payload, dict)
            else getattr(payload, 'task', 'field_extract')
        )

        # Heuristic extraction using AgentRuntime patterns
        # (no external LLM call — fast, works offline)
        extracted: dict[str, str] = {}
        if transcript:
            extracted = self._runtime.capture_required_fields(
                agent=self._make_minimal_agent(target_fields),
                user_text=transcript,
                collected_fields=dict(collected),
                prompted_field=target_fields[0] if target_fields else None,
            )

        await publisher.publish(make_event(
            LLMExtractedEvent,
            session_id=base.session_id,
            call_id=base.call_id,
            payload=LLMExtractedPayload(
                extracted_fields=extracted,
                task=task,
                confidence=None,
                fallback_triggered=False,
            ),
        ))

        logger.debug('llm_consumer.extracted', extra={
            'correlation_id': '', 'tenant_id': tenant_id,
            'call_id': call_id, 'task': task,
            'fields_extracted': list(extracted.keys()),
        })

    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

    async def _handle_classify(
        self,
        publisher: StreamPublisher,
        base: FSMEventBase,
        *,
        call_id: str,
        tenant_id: str,
    ) -> None:
        """
        Classify caller intent into a lane.
        Uses AgentRuntime.detect_intent() heuristic.
        Publishes llm.intent.
        """
        payload = base.payload
        transcript = (
            payload.get('transcript_text', '')
            if isinstance(payload, dict)
            else getattr(payload, 'transcript_text', '')
        )
        collected = (
            payload.get('context_snapshot', {})
            if isinstance(payload, dict)
            else getattr(payload, 'context_snapshot', {})
        )

        detected = self._runtime.detect_intent(
            user_text=transcript, collected_fields=dict(collected)
        )
        # Map intent to lane (simple heuristic — Phase 4 can use LLM)
        lane_map = {
            'booking': 'A',
            'quote': 'B',
            'support': 'C',
            'sales': 'A',
        }
        lane = lane_map.get(detected, 'A')

        await publisher.publish(make_event(
            LLMIntentEvent,
            session_id=base.session_id,
            call_id=base.call_id,
            payload=LLMIntentPayload(
                lane=lane,
                raw_response=detected,
            ),
        ))

        logger.debug('llm_consumer.intent', extra={
            'correlation_id': '', 'tenant_id': tenant_id,
            'call_id': call_id, 'detected': detected, 'lane': lane,
        })

    # ------------------------------------------------------------------
    # Helper: minimal Agent-like object for capture_required_fields()
    # ------------------------------------------------------------------

    def _make_minimal_agent(self, target_fields: list[str]):
        """
        Build a minimal stand-in for the Agent model so
        capture_required_fields() can be called without a DB lookup.
        Only sets the fields used by capture_required_fields().
        """
        from types import SimpleNamespace
        return SimpleNamespace(
            required_fields={f: {'label': f, 'prompt': f} for f in target_fields},
            policy_config={},
            persona='',
            script='',
            name='',
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

llm_consumer = LLMConsumer()
