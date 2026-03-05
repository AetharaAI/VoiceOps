from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, WebSocket
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import Agent, Call, CallDirection, CallStatus, PhoneNumber
from app.services.realtime.session_manager import session_manager

router = APIRouter(tags=['telephony-webhooks'])


@router.post('/webhooks/telephony/inbound')
async def inbound_call(
    request: Request,
    db: AsyncSession = Depends(get_db),
    call_id: str | None = Query(default=None),
    from_number: str = Form(default=''),
    to_number: str = Form(default=''),
    call_sid: str = Form(default=''),
) -> Response:
    if not from_number:
        form = await request.form()
        from_number = form.get('From', '')
        to_number = form.get('To', '')
        call_sid = form.get('CallSid', '')

    existing_call = None
    if call_id:
        existing_call = (await db.execute(select(Call).where(Call.id == call_id))).scalar_one_or_none()

    if existing_call:
        chosen_call = existing_call
    else:
        number_row = (await db.execute(select(PhoneNumber).where(PhoneNumber.phone_number == to_number))).scalar_one_or_none()
        if number_row and number_row.agent_id:
            agent_id = number_row.agent_id
            tenant_id = number_row.tenant_id
        else:
            fallback_agent = (await db.execute(select(Agent).order_by(Agent.created_at.asc()))).scalar_one_or_none()
            if not fallback_agent:
                raise HTTPException(status_code=500, detail='No agent configured for inbound calls')
            tenant_id = fallback_agent.tenant_id
            agent_id = fallback_agent.id

        chosen_call = Call(
            tenant_id=tenant_id,
            agent_id=agent_id,
            external_call_id=call_sid or None,
            direction=CallDirection.inbound,
            status=CallStatus.ringing,
            from_number=from_number or 'unknown',
            to_number=to_number or 'unknown',
            context_payload={},
        )
        db.add(chosen_call)
        await db.commit()
        await db.refresh(chosen_call)

    base = get_settings().public_base_url.rstrip('/')
    if base.startswith('https://'):
        ws_base = 'wss://' + base.removeprefix('https://')
    elif base.startswith('http://'):
        ws_base = 'ws://' + base.removeprefix('http://')
    else:
        ws_base = 'wss://' + base
    ws_url = f"{ws_base}/api/v1/ws/telephony/{chosen_call.id}"

    twiml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
  <Connect>
    <Stream url=\"{ws_url}\" track=\"both_tracks\" />
  </Connect>
    </Response>"""
    return Response(content=twiml, media_type='application/xml')


@router.post('/webhooks/telephony/fallback')
async def inbound_fallback() -> Response:
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
    if not call_sid:
        form = await request.form()
        call_sid = form.get('CallSid', '')
        call_status = form.get('CallStatus', '')

    call = (await db.execute(select(Call).where(Call.external_call_id == call_sid))).scalar_one_or_none()
    if not call:
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
    call.status = status_map.get(call_status, call.status)
    if call.status in {CallStatus.completed, CallStatus.failed, CallStatus.no_answer}:
        call.ended_at = datetime.now(timezone.utc)
    await db.commit()
    return {'ok': True}


@router.websocket('/ws/telephony/{call_id}')
async def telephony_ws(websocket: WebSocket, call_id: str, db: AsyncSession = Depends(get_db)) -> None:
    await session_manager.handle_ws(websocket, call_id, db)
