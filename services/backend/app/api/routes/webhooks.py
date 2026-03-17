from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, WebSocket
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import CALLS_STARTED
from app.db.session import get_db
from app.models.models import Call, CallDirection, CallStatus
from app.services.realtime.session_manager import session_manager
from app.services.telephony.event_sink import call_event_sink
from app.services.telephony.inbound_routing import build_inbound_webhook_payload, resolve_inbound_agent
from app.services.telephony.telemetry import utc_now_iso

router = APIRouter(tags=['telephony-webhooks'])
logger = get_logger(__name__)


@router.post('/webhooks/telephony/inbound')
async def inbound_call(
    request: Request,
    db: AsyncSession = Depends(get_db),
    call_id: str | None = Query(default=None),
    from_number: str = Form(default=''),
    to_number: str = Form(default=''),
    call_sid: str = Form(default=''),
) -> Response:
    form = await request.form()
    payload = build_inbound_webhook_payload(
        dict(form),
        from_number=from_number,
        to_number=to_number,
        call_sid=call_sid,
    )
    correlation_id = getattr(request.state, 'correlation_id', '')
    logger.info(
        'telephony.inbound.webhook.received',
        extra={
            'correlation_id': correlation_id,
            'tenant_id': '',
            'call_id': call_id or '',
            'call_sid': payload.call_sid,
            'from_number': payload.from_number,
            'to_number': payload.to_number,
            'metadata': payload.metadata,
            'warnings': payload.warnings,
        },
    )
    call_event_sink.record_event(
        call_event_sink.build_event(
            event_type='telephony.inbound.webhook.received',
            level='info',
            call_id=call_id or '',
            call_sid=payload.call_sid,
            direction='inbound',
            route='inbound',
            correlation_id=correlation_id,
            from_number=payload.from_number,
            to_number=payload.to_number,
            warnings=payload.warnings,
            metadata=payload.metadata,
        )
    )

    existing_call = None
    if call_id:
        existing_call = (await db.execute(select(Call).where(Call.id == call_id))).scalar_one_or_none()

    if existing_call:
        chosen_call = existing_call
        chosen_call.external_call_id = payload.call_sid or chosen_call.external_call_id
        chosen_call.from_number = payload.from_number or chosen_call.from_number
        chosen_call.to_number = payload.to_number or chosen_call.to_number
        existing_context = dict(chosen_call.context_payload or {})
        existing_context['telephony'] = {
            **(existing_context.get('telephony') or {}),
            'route': 'outbound',
            'callback': {
                'call_id': str(chosen_call.id),
                'call_sid': payload.call_sid,
                'from_number': payload.from_number,
                'to_number': payload.to_number,
                'correlation_id': correlation_id,
                'webhook_received_at': utc_now_iso(),
                'warnings': payload.warnings,
                'metadata': payload.metadata,
            },
        }
        chosen_call.context_payload = existing_context
        logger.info(
            'telephony.inbound.webhook.reused_outbound_call',
            extra={
                'correlation_id': correlation_id,
                'tenant_id': str(chosen_call.tenant_id),
                'call_id': str(chosen_call.id),
                'call_sid': payload.call_sid,
                'route': 'outbound',
                'agent_id': str(chosen_call.agent_id) if chosen_call.agent_id else '',
                'warnings': payload.warnings,
            },
        )
        call_event_sink.record_event(
            call_event_sink.build_event(
                event_type='telephony.inbound.webhook.reused_outbound_call',
                level='info',
                call_id=str(chosen_call.id),
                call_sid=payload.call_sid,
                tenant_id=str(chosen_call.tenant_id),
                direction='outbound',
                route='outbound',
                agent_id=str(chosen_call.agent_id) if chosen_call.agent_id else '',
                correlation_id=correlation_id,
                from_number=payload.from_number,
                to_number=payload.to_number,
                warnings=payload.warnings,
            )
        )
    else:
        try:
            resolution = await resolve_inbound_agent(db, payload=payload)
        except LookupError as exc:
            logger.error(
                'telephony.inbound.webhook.agent_resolution_failed',
                extra={
                    'correlation_id': correlation_id,
                    'tenant_id': '',
                    'call_id': '',
                    'call_sid': payload.call_sid,
                    'from_number': payload.from_number,
                    'to_number': payload.to_number,
                    'warnings': payload.warnings,
                    'error': str(exc),
                },
            )
            call_event_sink.record_event(
                call_event_sink.build_event(
                    event_type='telephony.inbound.webhook.agent_resolution_failed',
                    level='error',
                    call_sid=payload.call_sid,
                    direction='inbound',
                    route='inbound',
                    correlation_id=correlation_id,
                    from_number=payload.from_number,
                    to_number=payload.to_number,
                    warnings=payload.warnings,
                    error=str(exc),
                )
            )
            raise HTTPException(status_code=500, detail='No agent configured for inbound calls') from exc

        logger.info(
            'telephony.inbound.webhook.agent_resolved',
            extra={
                'correlation_id': correlation_id,
                'tenant_id': resolution.tenant_id,
                'call_id': '',
                'call_sid': payload.call_sid,
                'from_number': payload.from_number,
                'to_number': payload.to_number,
                'agent_id': str(resolution.agent.id),
                'agent_name': resolution.agent.name,
                'resolution_source': resolution.resolution_source,
                'matched_phone_number': resolution.matched_phone_number or '',
                'phone_number_id': resolution.phone_number_id or '',
                'fallback_reason': resolution.fallback_reason or '',
                'warnings': resolution.warnings,
            },
        )
        call_event_sink.record_event(
            call_event_sink.build_event(
                event_type='telephony.inbound.webhook.agent_resolved',
                level='info',
                call_sid=payload.call_sid,
                tenant_id=resolution.tenant_id,
                direction='inbound',
                route='inbound',
                agent_id=str(resolution.agent.id),
                agent_name=resolution.agent.name,
                correlation_id=correlation_id,
                from_number=payload.from_number,
                to_number=payload.to_number,
                resolution_source=resolution.resolution_source,
                matched_phone_number=resolution.matched_phone_number or '',
                phone_number_id=resolution.phone_number_id or '',
                fallback_reason=resolution.fallback_reason or '',
                warnings=resolution.warnings,
            )
        )

        chosen_call = Call(
            tenant_id=resolution.tenant_id,
            agent_id=resolution.agent.id,
            external_call_id=payload.call_sid or None,
            direction=CallDirection.inbound,
            status=CallStatus.ringing,
            from_number=payload.from_number or 'unknown',
            to_number=payload.to_number or 'unknown',
            context_payload={
                'telephony': {
                    **resolution.to_context_payload(),
                    'webhook': {
                        'call_sid': payload.call_sid,
                        'from_number': payload.from_number,
                        'to_number': payload.to_number,
                        'correlation_id': correlation_id,
                        'metadata': payload.metadata,
                        'warnings': payload.warnings,
                        'webhook_received_at': utc_now_iso(),
                    },
                }
            },
        )
        db.add(chosen_call)
        await db.commit()
        await db.refresh(chosen_call)
        CALLS_STARTED.labels(tenant_id=resolution.tenant_id, direction='inbound').inc()

    base = get_settings().public_base_url.rstrip('/')
    if base.startswith('https://'):
        ws_base = 'wss://' + base.removeprefix('https://')
    elif base.startswith('http://'):
        ws_base = 'ws://' + base.removeprefix('http://')
    else:
        ws_base = 'wss://' + base
    ws_url = f"{ws_base}/api/v1/ws/telephony/{chosen_call.id}"
    await db.commit()

    logger.info(
        'telephony.inbound.webhook.twiml_issued',
        extra={
            'correlation_id': correlation_id,
            'tenant_id': str(chosen_call.tenant_id),
            'call_id': str(chosen_call.id),
            'call_sid': payload.call_sid,
            'route': (chosen_call.context_payload or {}).get('telephony', {}).get('route', 'inbound'),
            'agent_id': str(chosen_call.agent_id) if chosen_call.agent_id else '',
            'stream_url': ws_url,
        },
    )
    call_event_sink.record_event(
        call_event_sink.build_event(
            event_type='telephony.inbound.webhook.twiml_issued',
            level='info',
            call_id=str(chosen_call.id),
            call_sid=payload.call_sid,
            tenant_id=str(chosen_call.tenant_id),
            direction=(chosen_call.context_payload or {}).get('telephony', {}).get('route', 'inbound'),
            route=(chosen_call.context_payload or {}).get('telephony', {}).get('route', 'inbound'),
            agent_id=str(chosen_call.agent_id) if chosen_call.agent_id else '',
            correlation_id=correlation_id,
            from_number=chosen_call.from_number,
            to_number=chosen_call.to_number,
            stream_url=ws_url,
        )
    )
    twiml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
  <Connect>
    <Stream url=\"{ws_url}\" />
  </Connect>
    </Response>"""
    return Response(content=twiml, media_type='application/xml')


@router.post('/webhooks/telephony/fallback')
async def inbound_fallback(
    request: Request,
    call_sid: str = Form(default=''),
    from_number: str = Form(default=''),
    to_number: str = Form(default=''),
) -> Response:
    form = await request.form()
    payload = build_inbound_webhook_payload(
        dict(form),
        from_number=from_number,
        to_number=to_number,
        call_sid=call_sid,
    )
    logger.warning(
        'telephony.inbound.fallback_invoked',
        extra={
            'correlation_id': getattr(request.state, 'correlation_id', ''),
            'tenant_id': '',
            'call_id': '',
            'call_sid': payload.call_sid,
            'from_number': payload.from_number,
            'to_number': payload.to_number,
            'route': 'fallback',
            'warnings': payload.warnings,
            'metadata': payload.metadata,
        },
    )
    call_event_sink.record_event(
        call_event_sink.build_event(
            event_type='telephony.inbound.fallback_invoked',
            level='warning',
            call_sid=payload.call_sid,
            direction='fallback',
            route='fallback',
            correlation_id=getattr(request.state, 'correlation_id', ''),
            from_number=payload.from_number,
            to_number=payload.to_number,
            warnings=payload.warnings,
            metadata=payload.metadata,
        )
    )
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>We are temporarily unavailable. Please try again shortly.</Say>
  <Hangup />
</Response>"""
    return Response(content=twiml, media_type='application/xml')


@router.post('/webhooks/telephony/status')
async def call_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    call_sid: str = Form(default=''),
    call_status: str = Form(default=''),
) -> dict:
    form = await request.form()
    call_sid = call_sid or form.get('CallSid', '')
    call_status = call_status or form.get('CallStatus', '')

    call = (await db.execute(select(Call).where(Call.external_call_id == call_sid))).scalar_one_or_none()
    if not call:
        logger.warning(
            'telephony.status.unknown_call_sid',
            extra={
                'correlation_id': getattr(request.state, 'correlation_id', ''),
                'tenant_id': '',
                'call_id': '',
                'call_sid': call_sid,
                'provider_status': call_status,
            },
        )
        call_event_sink.record_event(
            call_event_sink.build_event(
                event_type='telephony.status.unknown_call_sid',
                level='warning',
                call_sid=call_sid,
                direction='unknown',
                route='status',
                correlation_id=getattr(request.state, 'correlation_id', ''),
                payload_status=call_status,
            )
        )
        return {'ok': True, 'message': 'Unknown call sid'}

    status_map = {
        'queued': CallStatus.queued,
        'ringing': CallStatus.ringing,
        'in-progress': CallStatus.in_progress,
        'completed': CallStatus.completed,
        'no-answer': CallStatus.no_answer,
        'failed': CallStatus.failed,
        'busy': CallStatus.failed,
    }
    next_status = status_map.get(call_status)
    terminal_statuses = {CallStatus.completed, CallStatus.failed, CallStatus.no_answer, CallStatus.escalated}
    if next_status:
        if call.status in terminal_statuses and next_status not in terminal_statuses:
            next_status = call.status
        if call.status == CallStatus.escalated and next_status == CallStatus.completed:
            next_status = CallStatus.escalated
        call.status = next_status
    if call.status in {CallStatus.completed, CallStatus.failed, CallStatus.no_answer}:
        call.ended_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info(
        'telephony.status.updated',
        extra={
            'correlation_id': getattr(request.state, 'correlation_id', ''),
            'tenant_id': str(call.tenant_id),
            'call_id': str(call.id),
            'call_sid': call_sid,
            'provider_status': call_status,
            'next_status': call.status.value,
        },
    )
    call_event_sink.record_event(
        call_event_sink.build_event(
            event_type='telephony.status.updated',
            level='info',
            call_id=str(call.id),
            call_sid=call_sid,
            tenant_id=str(call.tenant_id),
            direction=call.direction.value,
            route=(call.context_payload or {}).get('telephony', {}).get('route', call.direction.value),
            agent_id=str(call.agent_id) if call.agent_id else '',
            correlation_id=getattr(request.state, 'correlation_id', ''),
            from_number=call.from_number,
            to_number=call.to_number,
            provider_status=call_status,
            next_status=call.status.value,
        )
    )
    return {'ok': True}


@router.websocket('/ws/telephony/{call_id}')
async def telephony_ws(websocket: WebSocket, call_id: str, db: AsyncSession = Depends(get_db)) -> None:
    await session_manager.handle_ws(websocket, call_id, db)
