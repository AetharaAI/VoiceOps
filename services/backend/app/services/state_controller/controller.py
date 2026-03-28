"""
VoiceOps FSM — State Controller
================================

The ONLY service that may emit: tts.speak, asr.start_listen, state.transition.

Runs as an asyncio task alongside the StreamIngester (started from handle_ws).
Reads events from the per-call Redis Stream via XREADGROUP (group: voice:ctrl).
Maintains in-memory FSM state. Enforces the hard-listen guarantee.

Hard-listen guarantee (enforced here — not a comment, a runtime guard):
    RULE 1: _emit_tts() is a no-op if asr_listening is True.
    RULE 2: _emit_asr_start_listen() is a no-op if pending_tts_id is set.
    RULE 3: tts.speak is only emitted from _emit_tts() — never constructed inline.

FSM states
----------
S0  Call Incoming     — call.incoming received, setup
S1  Greeting          — greeting TTS playing
S2  Name Capture      — listening for caller name
S3  Intent Capture    — listening for caller intent / issue
S4a Detail Capture    — lane A field collection loop
S5  Contact Capture   — confirm/capture callback number
S6  Readback+Confirm  — read back all details, Y/N loop
S7  Close+Log         — goodbye TTS, then call.ended
Esc Escalation        — warm transfer TTS, then call.ended

Phase 3 notes
-------------
AgentRuntime is called inline here (no separate LLM Consumer yet).
llm.extract / llm.extracted events are still emitted to the stream for
observability and audit. The LLM Consumer TODO will offload this in Phase 4.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Agent
from app.services.agent_runtime.runtime import AgentRuntime
from app.services.streams.event_schemas import (
    ASRStartListenEvent,
    ASRStartListenPayload,
    CallEndedEvent,
    CallEndedPayload,
    FSMEventBase,
    LLMExtractedEvent,
    LLMExtractedPayload,
    LLMExtractEvent,
    LLMExtractPayload,
    STATE_CONTROLLER_COMMANDS,
    StateTransitionEvent,
    StateTransitionPayload,
    TTSSpeakEvent,
    TTSSpeakPayload,
    make_event,
)
from app.services.streams.publisher import StreamPublisher

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FIELD_RETRIES = 3       # per-field: after this many failures, skip
MAX_SILENCE_RETRIES = 2     # global: after this many silent turns, escalate
STREAM_POLL_BLOCK_MS = 500  # XREADGROUP block timeout
EARLY_EMPTY_GRACE_SECONDS = 8.0
MAX_EARLY_EMPTY_SILENT_RETRIES = 5

TERMINAL_STATES = frozenset({'S7', 'Esc'})
S6_CONFIRMATION_TIMEOUT_FLOOR = 14.0

# Events the State Controller should skip when consuming its own stream
_SKIP_EVENT_TYPES = STATE_CONTROLLER_COMMANDS | {'llm.extract', 'llm.classify'}


# ---------------------------------------------------------------------------
# In-memory FSM state for one active call
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CallFSMState:
    """All mutable FSM state for one call — lives in RAM for the duration."""

    session_id: str
    call_id: str
    tenant_id: str
    agent: Agent

    # FSM
    current_state: str = 'S0'
    collected_fields: dict[str, str] = field(default_factory=dict)

    # Hard-listen guarantee tracking
    pending_tts_id: str | None = None   # tts_request_id we're waiting on
    asr_listening: bool = False          # True after asr.start_listen, cleared on asr.transcript

    # Retry counters (per field / per action)
    retry_counts: dict[str, int] = field(default_factory=dict)
    silence_retry_count: int = 0
    last_prompted_field: str | None = None

    # Termination
    terminated: bool = False

    # Telemetry
    started_at: str = field(default_factory=_utc_now)
    agent_turns: int = 0
    caller_turns: int = 0
    detected_intent: str = 'unknown'

    # Silence timeout — monotonic timestamp when we should fire timeout.silence
    silence_deadline: float | None = None
    silence_timeout_seconds: float = 10.0
    last_recovery_prompt: str = ''
    last_listen_started_at: float | None = None
    empty_transcript_count: int = 0


# ---------------------------------------------------------------------------
# State Controller
# ---------------------------------------------------------------------------

class StateController:
    """
    FSM driver for a single call.  Run one instance per call via run().
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._runtime = AgentRuntime()

    # ------------------------------------------------------------------
    # Public entry point — call as asyncio.create_task(ctrl.run(...))
    # ------------------------------------------------------------------

    async def run(
        self,
        *,
        session_id: str,
        call_id: str,
        agent: Agent,
        tenant_id: str,
        redis: Redis,
        publisher: StreamPublisher,
    ) -> None:
        """
        Start the consumer loop for one call.
        Returns when the call terminates (S7/Esc) or the task is cancelled.
        """
        state = CallFSMState(
            session_id=session_id,
            call_id=call_id,
            tenant_id=tenant_id,
            agent=agent,
        )

        stream_key = self._settings.per_call_stream_key(session_id)
        group_name = self._settings.redis_cg_state_controller
        consumer_name = f'ctrl_{session_id[:8]}'

        # Consumer group reads from the beginning so it sees call.incoming
        # even if published before this task started.
        try:
            await redis.xgroup_create(stream_key, group_name, id='0', mkstream=True)
        except Exception:
            pass  # BUSYGROUP — already exists

        logger.info('state_ctrl.started', extra={
            'correlation_id': '', 'tenant_id': tenant_id,
            'call_id': call_id, 'session_id': session_id,
            'stream_key': stream_key,
        })

        try:
            await self._consume(state, redis, stream_key, group_name, consumer_name, publisher)
        except asyncio.CancelledError:
            logger.info('state_ctrl.cancelled', extra={
                'correlation_id': '', 'tenant_id': tenant_id,
                'call_id': call_id, 'state': state.current_state,
            })
            raise
        except Exception as exc:
            logger.error('state_ctrl.fatal', extra={
                'correlation_id': '', 'tenant_id': tenant_id,
                'call_id': call_id, 'error': str(exc), 'exc_type': type(exc).__name__,
            })
        finally:
            logger.info('state_ctrl.ended', extra={
                'correlation_id': '', 'tenant_id': tenant_id,
                'call_id': call_id, 'final_state': state.current_state,
                'agent_turns': state.agent_turns, 'caller_turns': state.caller_turns,
                'collected_fields': list(state.collected_fields.keys()),
            })

    # ------------------------------------------------------------------
    # Consumer loop
    # ------------------------------------------------------------------

    async def _consume(
        self,
        state: CallFSMState,
        redis: Redis,
        stream_key: str,
        group_name: str,
        consumer_name: str,
        publisher: StreamPublisher,
    ) -> None:
        while not state.terminated:
            # Check silence timeout between polls
            if (
                state.silence_deadline is not None
                and time.monotonic() > state.silence_deadline
            ):
                state.silence_deadline = None
                await self._on_silence_timeout(state, publisher)

            entries = await redis.xreadgroup(
                group_name, consumer_name,
                {stream_key: '>'},
                count=10,
                block=STREAM_POLL_BLOCK_MS,
            )
            if not entries:
                continue

            for _stream, messages in entries:
                for entry_id, raw_fields in messages:
                    await self._dispatch(state, raw_fields, publisher)
                    try:
                        await redis.xack(stream_key, group_name, entry_id)
                    except Exception:
                        pass  # non-fatal; entry redelivered at worst

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        state: CallFSMState,
        raw_fields: dict,
        publisher: StreamPublisher,
    ) -> None:
        raw = raw_fields.get('data') or raw_fields.get(b'data', b'')
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8', errors='replace')
        if not raw:
            return

        try:
            base = FSMEventBase.model_validate_json(raw)
        except Exception as exc:
            logger.warning('state_ctrl.parse_error', extra={
                'correlation_id': '', 'tenant_id': state.tenant_id,
                'call_id': state.call_id, 'error': str(exc),
            })
            return

        et = base.event_type

        # Skip our own commands and the LLM consumer's commands
        if et in _SKIP_EVENT_TYPES:
            return

        logger.debug('state_ctrl.event', extra={
            'correlation_id': '', 'tenant_id': state.tenant_id,
            'call_id': state.call_id,
            'event_type': et, 'fsm_state': state.current_state,
        })

        handlers: dict[str, Any] = {
            'call.incoming': self._on_call_incoming,
            'tts.complete': self._on_tts_complete,
            'asr.transcript': self._on_asr_transcript,
            'timeout.silence': self._on_timeout_silence_event,
            'escalate.frustration': self._on_escalate,
            'call.ended': self._on_call_ended,
        }
        handler = handlers.get(et)
        if handler:
            await handler(state, base, publisher)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _on_call_incoming(
        self, state: CallFSMState, base: FSMEventBase, publisher: StreamPublisher
    ) -> None:
        """S0: call arrived — emit greeting TTS, transition to S1."""
        if state.current_state != 'S0':
            return  # guard against duplicate call.incoming

        opening = self._runtime.build_opening_prompt(
            agent=state.agent, collected_fields={}
        )
        await self._transition_to(state, 'S1', trigger=base, publisher=publisher)
        await self._emit_tts(
            state, publisher,
            text=opening.response_text,
            response_source='scripted_greeting',
        )

    async def _on_tts_complete(
        self, state: CallFSMState, base: FSMEventBase, publisher: StreamPublisher
    ) -> None:
        """TTS finished — begin listening (unless in a terminal state)."""
        payload = base.payload
        tts_id = (
            payload.get('tts_request_id', '')
            if isinstance(payload, dict)
            else getattr(payload, 'tts_request_id', '')
        )

        # Guard: ignore completions for TTS requests we didn't emit
        if state.pending_tts_id and tts_id and tts_id != state.pending_tts_id:
            logger.debug('state_ctrl.tts_complete.stale', extra={
                'correlation_id': '', 'tenant_id': state.tenant_id,
                'call_id': state.call_id,
                'expected': state.pending_tts_id, 'got': tts_id,
            })
            return

        state.pending_tts_id = None

        if state.current_state in TERMINAL_STATES:
            # Goodbye/transfer TTS finished — end the call cleanly
            state.terminated = True
        else:
            # Start listening for the next caller turn
            await self._emit_asr_start_listen(state, publisher)

    async def _on_asr_transcript(
        self, state: CallFSMState, base: FSMEventBase, publisher: StreamPublisher
    ) -> None:
        """Caller spoke — advance the FSM."""
        if state.current_state in TERMINAL_STATES:
            state.asr_listening = False
            state.silence_deadline = None
            return

        payload = base.payload
        text = (
            payload.get('text', '')
            if isinstance(payload, dict)
            else getattr(payload, 'text', '')
        )
        is_final = (
            payload.get('is_final', True)
            if isinstance(payload, dict)
            else getattr(payload, 'is_final', True)
        )

        # ASR partial: caller is actively speaking. Keep listen mode active and
        # extend the silence deadline so we don't talk over long utterances.
        if not bool(is_final):
            if state.asr_listening:
                state.silence_deadline = time.monotonic() + self._resolve_listen_timeout(state)
            return

        state.asr_listening = False
        state.silence_deadline = None

        if not text or not text.strip():
            await self._handle_empty_transcript(state, publisher)
            return

        state.silence_retry_count = 0
        state.last_recovery_prompt = ''
        state.empty_transcript_count = 0
        state.caller_turns += 1

        # ── Greeting-state transition: first thing caller says after greeting
        # We need to move out of S1 before processing the transcript.
        if state.current_state == 'S1':
            await self._transition_to(state, 'S2', trigger=base, publisher=publisher,
                                      reason='first_caller_turn')

        # ── Run AgentRuntime inline (Phase 3 — no separate LLM consumer yet)
        agent_turn = await self._runtime.generate_response(
            agent=state.agent,
            user_text=text,
            context={},
            collected_fields=state.collected_fields,
            prompted_field=state.last_prompted_field,
            telemetry_context={
                'call_id': state.call_id,
                'tenant_id': state.tenant_id,
                'resolved_agent_id': str(state.agent.id),
                'resolved_agent_name': state.agent.name,
            },
        )

        # Publish llm.extract + llm.extracted to the stream for observability / audit
        missing_before = self._runtime.missing_required_fields(
            agent=state.agent, collected_fields=state.collected_fields
        )
        state.collected_fields.update(agent_turn.captured_fields)
        state.detected_intent = agent_turn.detected_intent

        await self._publish_llm_events(
            state, publisher,
            transcript_text=text,
            extracted_fields=agent_turn.captured_fields,
        )

        if agent_turn.should_escalate:
            await self._transition_to_escalation(
                state, publisher,
                reason=agent_turn.escalation_reason or 'escalation_keyword',
                transcript=text,
            )
            return

        # ── Decide FSM transition based on collected fields
        missing_after = self._runtime.missing_required_fields(
            agent=state.agent, collected_fields=state.collected_fields
        )

        if not missing_after and state.current_state not in ('S6', 'S7', 'Esc'):
            # All required fields captured — move to readback
            await self._transition_to(state, 'S6', trigger=base, publisher=publisher,
                                      reason='all_fields_captured')
            await self._enter_s6_tts(state, publisher)

        elif state.current_state in ('S2', 'S3', 'S4a'):
            # Still collecting fields — respond naturally, keep listening
            if missing_after:
                state.last_prompted_field = missing_after[0]
                retry_key = missing_after[0]
                if missing_before and missing_after[0] == missing_before[0]:
                    # Same field — no progress
                    state.retry_counts[retry_key] = state.retry_counts.get(retry_key, 0) + 1
                    if state.retry_counts[retry_key] >= MAX_FIELD_RETRIES:
                        # Skip this field
                        state.collected_fields[retry_key] = ''
                        state.retry_counts[retry_key] = 0
                else:
                    state.retry_counts[retry_key] = 0

            await self._emit_tts(
                state, publisher,
                text=agent_turn.response_text,
                response_source=agent_turn.response_source,
            )

        elif state.current_state == 'S6':
            await self._handle_confirmation(state, publisher, base=base, text=text)

    async def _on_timeout_silence_event(
        self, state: CallFSMState, base: FSMEventBase, publisher: StreamPublisher
    ) -> None:
        """timeout.silence event from ASR Consumer."""
        state.asr_listening = False
        await self._on_silence_timeout(state, publisher)

    async def _on_escalate(
        self, state: CallFSMState, base: FSMEventBase, publisher: StreamPublisher
    ) -> None:
        """LLM or heuristic detected frustration — transfer the call."""
        payload = base.payload
        reason = (
            payload.get('reason', 'frustration')
            if isinstance(payload, dict)
            else getattr(payload, 'reason', 'frustration')
        )
        await self._transition_to_escalation(
            state, publisher, reason=reason, transcript=''
        )

    async def _on_call_ended(
        self, state: CallFSMState, _base: FSMEventBase, _publisher: StreamPublisher
    ) -> None:
        state.terminated = True

    # ------------------------------------------------------------------
    # Sub-handlers
    # ------------------------------------------------------------------

    async def _handle_confirmation(
        self,
        state: CallFSMState,
        publisher: StreamPublisher,
        base: FSMEventBase,
        text: str,
    ) -> None:
        """Parse caller yes/no in S6 (readback confirmation)."""
        lowered = text.lower()
        affirm = {'yes', 'yeah', 'yep', 'correct', 'right', 'sure', 'confirm', "that's right"}
        deny = {'no', 'nope', 'wrong', 'incorrect', 'not right', 'change', 'different'}

        if any(w in lowered for w in affirm):
            closing = (
                (state.agent.policy_config or {}).get('runtime', {}).get('closing_message')
                or 'Great, we have everything we need. Thank you, and have a wonderful day!'
            )
            await self._transition_to(state, 'S7', trigger=base, publisher=publisher,
                                      reason='confirmed')
            await self._emit_tts(state, publisher, text=closing,
                                 response_source='scripted_goodbye')

        elif any(w in lowered for w in deny):
            retries = state.retry_counts.get('confirmation', 0) + 1
            state.retry_counts['confirmation'] = retries
            if retries >= MAX_FIELD_RETRIES:
                await self._transition_to_escalation(
                    state, publisher, reason='max_confirm_retries', transcript=text
                )
            else:
                # Ask what to correct — run LLM for a natural response
                agent_turn = await self._runtime.generate_response(
                    agent=state.agent, user_text=text, context={},
                    collected_fields=state.collected_fields, prompted_field=None,
                )
                await self._emit_tts(state, publisher, text=agent_turn.response_text,
                                     response_source='confirmation_correction')

        else:
            # Unclear yes/no — nudge without repeating full readback.
            await self._emit_tts(
                state,
                publisher,
                text=self._confirmation_retry_prompt(),
                response_source='confirmation_retry',
            )

    async def _handle_empty_transcript(
        self, state: CallFSMState, publisher: StreamPublisher
    ) -> None:
        """Empty or noise-only transcript."""
        if state.current_state in TERMINAL_STATES:
            return

        state.empty_transcript_count += 1
        listen_elapsed = (
            time.monotonic() - state.last_listen_started_at
            if state.last_listen_started_at is not None
            else None
        )

        # In confirmation state, avoid repeating the same yes/no prompt back-to-back.
        if (
            state.current_state == 'S6'
            and state.last_recovery_prompt == self._confirmation_retry_prompt()
        ):
            await self._emit_asr_start_listen(state, publisher)
            return

        # Quick empty finals often come from edge VAD/noise. Keep listening for
        # a short grace window to avoid talking over the caller.
        if (
            (listen_elapsed is None or listen_elapsed < EARLY_EMPTY_GRACE_SECONDS)
            and state.empty_transcript_count <= MAX_EARLY_EMPTY_SILENT_RETRIES
        ):
            await self._emit_asr_start_listen(state, publisher)
            return

        if state.last_prompted_field:
            recovery = self._runtime.build_field_retry_prompt(
                agent=state.agent,
                field_name=state.last_prompted_field,
                retry_count=max(state.empty_transcript_count, state.silence_retry_count),
                retry_reason='partial_unclear_speech',
                previous_prompt=state.last_recovery_prompt,
            )
        elif state.current_state == 'S6':
            recovery = self._confirmation_retry_prompt()
        else:
            recovery = self._runtime.build_general_recovery_prompt(
                retry_reason='no_speech',
                retry_count=max(state.empty_transcript_count, state.silence_retry_count),
                previous_prompt=state.last_recovery_prompt,
            )
        state.last_recovery_prompt = recovery
        await self._emit_tts(state, publisher, text=recovery,
                             response_source='recovery_prompt')

    async def _on_silence_timeout(
        self, state: CallFSMState, publisher: StreamPublisher
    ) -> None:
        """No speech within the listen window — nudge or escalate."""
        if not state.asr_listening:
            return  # ASR already got something; stale timeout

        state.silence_retry_count += 1
        state.asr_listening = False

        if state.silence_retry_count >= MAX_SILENCE_RETRIES:
            await self._transition_to_escalation(
                state, publisher, reason='max_silence_timeout', transcript=''
            )
        else:
            # Prefer field-aware retry prompts when we're collecting a known field.
            if state.last_prompted_field:
                recovery = self._runtime.build_field_retry_prompt(
                    agent=state.agent,
                    field_name=state.last_prompted_field,
                    retry_count=state.silence_retry_count,
                    retry_reason='no_speech',
                    previous_prompt=state.last_recovery_prompt,
                )
            elif state.current_state == 'S6':
                recovery = self._confirmation_retry_prompt()
            else:
                recovery = self._runtime.build_general_recovery_prompt(
                    retry_reason='no_speech',
                    retry_count=state.silence_retry_count,
                    previous_prompt=state.last_recovery_prompt,
                )
            state.last_recovery_prompt = recovery
            await self._emit_tts(state, publisher, text=recovery,
                                 response_source='silence_recovery')

    async def _transition_to_escalation(
        self,
        state: CallFSMState,
        publisher: StreamPublisher,
        reason: str,
        transcript: str,
    ) -> None:
        await self._transition_to(state, 'Esc', trigger=None, publisher=publisher,
                                  reason=reason)
        transfer = (
            (state.agent.policy_config or {}).get('runtime', {}).get('escalation_message')
            or 'I am transferring you to a specialist now. Please hold.'
        )
        await self._emit_tts(state, publisher, text=transfer,
                             response_source='escalation_transfer')

    # ------------------------------------------------------------------
    # State entry helpers
    # ------------------------------------------------------------------

    async def _enter_s6_tts(
        self, state: CallFSMState, publisher: StreamPublisher
    ) -> None:
        """Build and emit the readback confirmation prompt."""
        state.last_prompted_field = None
        parts: list[str] = []
        required_fields = state.agent.required_fields if isinstance(state.agent.required_fields, dict) else {}
        if required_fields:
            for field_name in required_fields.keys():
                value = state.collected_fields.get(field_name)
                if value:
                    parts.append(
                        f'{field_name.replace("_", " ").title()}: '
                        f'{self._format_field_for_readback(field_name, value)}'
                    )
        else:
            parts = [
                f'{k.replace("_", " ").title()}: {self._format_field_for_readback(k, v)}'
                for k, v in state.collected_fields.items()
                if v
            ]
        if parts:
            readback = 'Let me confirm what I have. ' + ', '.join(parts) + '. Is that all correct?'
        else:
            readback = 'I have your information on file. Is everything correct?'
        await self._emit_tts(state, publisher, text=readback,
                             response_source='readback_prompt')

    # ------------------------------------------------------------------
    # Emitters — the only places tts.speak / asr.start_listen are built
    # ------------------------------------------------------------------

    async def _emit_tts(
        self,
        state: CallFSMState,
        publisher: StreamPublisher,
        text: str,
        response_source: str = 'fsm_state_controller',
    ) -> None:
        """
        Emit tts.speak.  HARD-LISTEN GUARANTEE: blocks if ASR is active.
        This is the ONLY place tts.speak events are constructed and published.
        """
        if state.asr_listening:
            logger.warning('state_ctrl.tts.blocked_during_asr', extra={
                'correlation_id': '', 'tenant_id': state.tenant_id,
                'call_id': state.call_id, 'fsm_state': state.current_state,
                'text_preview': text[:60],
            })
            return  # hard-listen guarantee enforced

        voice = self._runtime.tts_voice_for_agent(agent=state.agent)
        model = self._runtime.tts_model_for_agent(agent=state.agent)

        tts_payload = TTSSpeakPayload(
            text=text,
            voice=voice,
            model=model,
            fsm_state=state.current_state,
            response_source=response_source,
        )
        state.pending_tts_id = tts_payload.tts_request_id
        state.agent_turns += 1

        event = make_event(
            TTSSpeakEvent,
            session_id=state.session_id,
            call_id=state.call_id,
            payload=tts_payload,
        )
        await publisher.publish(event)

        logger.info('state_ctrl.tts.emit', extra={
            'correlation_id': '', 'tenant_id': state.tenant_id,
            'call_id': state.call_id, 'fsm_state': state.current_state,
            'tts_request_id': tts_payload.tts_request_id,
            'tts_voice': voice, 'tts_model': model,
            'text_preview': text[:80], 'response_source': response_source,
        })

    async def _emit_asr_start_listen(
        self,
        state: CallFSMState,
        publisher: StreamPublisher,
        timeout_seconds: float | None = None,
    ) -> None:
        """
        Emit asr.start_listen. HARD-LISTEN GUARANTEE: blocks if TTS is pending.
        """
        if state.pending_tts_id is not None:
            logger.warning('state_ctrl.asr.blocked_during_tts', extra={
                'correlation_id': '', 'tenant_id': state.tenant_id,
                'call_id': state.call_id, 'pending_tts_id': state.pending_tts_id,
            })
            return  # hard-listen guarantee enforced

        timeout = timeout_seconds or self._resolve_listen_timeout(state)
        asr_payload = ASRStartListenPayload(
            fsm_state=state.current_state,
            prompted_field=state.last_prompted_field,
            timeout_seconds=timeout,
        )
        event = make_event(
            ASRStartListenEvent,
            session_id=state.session_id,
            call_id=state.call_id,
            payload=asr_payload,
        )
        await publisher.publish(event)

        state.asr_listening = True
        state.silence_deadline = time.monotonic() + timeout
        state.last_listen_started_at = time.monotonic()

        logger.info('state_ctrl.asr.start_listen', extra={
            'correlation_id': '', 'tenant_id': state.tenant_id,
            'call_id': state.call_id, 'fsm_state': state.current_state,
            'timeout_s': timeout, 'prompted_field': state.last_prompted_field or '',
        })

    def _resolve_listen_timeout(self, state: CallFSMState) -> float:
        timeout = state.silence_timeout_seconds
        field_name = (state.last_prompted_field or '').lower()
        if state.current_state == 'S1':
            timeout = max(timeout, 12.0)
        if state.current_state == 'S6':
            timeout = max(timeout, S6_CONFIRMATION_TIMEOUT_FLOOR)
        if field_name in {'phone', 'phone_number', 'callback_number', 'callback_phone', 'best_callback_number'}:
            timeout = max(timeout, 16.0)
        if field_name in {'name', 'full_name', 'customer_name'}:
            timeout = max(timeout, 12.0)
        return timeout

    def _confirmation_retry_prompt(self) -> str:
        return 'Please say yes if everything is correct, or no if you want to change something.'

    def _format_field_for_readback(self, field_name: str, value: str) -> str:
        if not value:
            return value
        lowered = field_name.lower()
        if lowered in {'phone', 'phone_number', 'callback_number', 'callback_phone', 'best_callback_number'}:
            digits = ''.join(ch for ch in value if ch.isdigit())
            if len(digits) == 10:
                return ' '.join(digits)
            if len(digits) == 11 and digits.startswith('1'):
                return '+1 ' + ' '.join(digits[1:])
        return value

    # ------------------------------------------------------------------
    # Observability: emit llm.extract + llm.extracted for audit trail
    # ------------------------------------------------------------------

    async def _publish_llm_events(
        self,
        state: CallFSMState,
        publisher: StreamPublisher,
        transcript_text: str,
        extracted_fields: dict[str, str],
    ) -> None:
        """
        Publish llm.extract command + llm.extracted result to the stream.
        In Phase 3 the State Controller handles LLM inline; these events exist
        for observability / audit only. The LLM Consumer (Phase 4) will handle
        llm.extract events and remove this inline path.
        """
        missing = self._runtime.missing_required_fields(
            agent=state.agent, collected_fields=state.collected_fields
        )
        extract_payload = LLMExtractPayload(
            task='field_extract',
            transcript_text=transcript_text,
            target_fields=missing,
            fsm_state=state.current_state,
            context_snapshot=dict(state.collected_fields),
        )
        await publisher.publish(make_event(
            LLMExtractEvent,
            session_id=state.session_id,
            call_id=state.call_id,
            payload=extract_payload,
        ))

        extracted_payload = LLMExtractedPayload(
            extracted_fields=extracted_fields,
            task='field_extract',
        )
        await publisher.publish(make_event(
            LLMExtractedEvent,
            session_id=state.session_id,
            call_id=state.call_id,
            payload=extracted_payload,
        ))

    # ------------------------------------------------------------------
    # FSM transition
    # ------------------------------------------------------------------

    async def _transition_to(
        self,
        state: CallFSMState,
        to_state: str,
        *,
        trigger: FSMEventBase | None,
        publisher: StreamPublisher,
        reason: str = '',
    ) -> None:
        """Update current_state and publish state.transition event."""
        from_state = state.current_state
        state.current_state = to_state

        trans_payload = StateTransitionPayload(
            from_state=from_state,
            to_state=to_state,
            trigger_event_id=trigger.event_id if trigger else '',
            trigger_event_type=trigger.event_type if trigger else 'internal',
            collected_fields_snapshot=dict(state.collected_fields),
            reason=reason,
        )
        await publisher.publish(make_event(
            StateTransitionEvent,
            session_id=state.session_id,
            call_id=state.call_id,
            payload=trans_payload,
        ))

        logger.info('state_ctrl.transition', extra={
            'correlation_id': '', 'tenant_id': state.tenant_id,
            'call_id': state.call_id,
            'from_state': from_state, 'to_state': to_state, 'reason': reason,
        })


# ---------------------------------------------------------------------------
# Module-level singleton — one StateController instance serves all calls
# (each call gets its own CallFSMState; the controller itself is stateless)
# ---------------------------------------------------------------------------

state_controller = StateController()
