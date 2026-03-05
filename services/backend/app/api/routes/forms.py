from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_roles
from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import Call, CallDirection, CallStatus, Form, FormSubmission, UserRole
from app.schemas.form import FormCreate, FormResponse, FormSubmissionResponse, FormSubmitRequest
from app.services.audit.service import audit_log
from app.services.telephony.providers import get_telephony_provider
from app.services.workflow.service import workflow_engine

router = APIRouter(tags=['forms'])


@router.post('/forms', response_model=FormResponse)
async def create_form(
    payload: FormCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.owner, UserRole.admin)),
) -> FormResponse:
    form = Form(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        schema=payload.form_schema,
        workflow_config=payload.workflow_config,
    )
    db.add(form)
    await db.flush()
    await audit_log(
        db,
        tenant_id=current_user.tenant_id,
        action='form.create',
        resource_type='form',
        resource_id=str(form.id),
        actor_user_id=current_user.id,
        metadata={'name': form.name},
    )
    await db.commit()

    return FormResponse(
        id=str(form.id),
        tenant_id=str(form.tenant_id),
        name=form.name,
        form_schema=form.schema,
        workflow_config=form.workflow_config,
    )


@router.get('/forms', response_model=list[FormResponse])
async def list_forms(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[FormResponse]:
    forms = (
        await db.execute(select(Form).where(Form.tenant_id == current_user.tenant_id).order_by(Form.created_at.desc()))
    ).scalars().all()
    return [
        FormResponse(
            id=str(f.id),
            tenant_id=str(f.tenant_id),
            name=f.name,
            form_schema=f.schema,
            workflow_config=f.workflow_config,
        )
        for f in forms
    ]


@router.post('/forms/{form_id}/submit', response_model=FormSubmissionResponse)
async def submit_form(
    form_id: str,
    payload: FormSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> FormSubmissionResponse:
    form = (
        await db.execute(select(Form).where(Form.id == form_id, Form.tenant_id == current_user.tenant_id))
    ).scalar_one_or_none()
    if not form:
        raise HTTPException(status_code=404, detail='Form not found')

    workflow_result = await workflow_engine.execute_form_submission(form.workflow_config, payload.payload)

    linked_call_id = None
    if workflow_result['action'] == 'call_now':
        phone = payload.payload.get('phone') or payload.payload.get('phone_number')
        agent_id = form.workflow_config.get('on_submit', {}).get('agent_id')
        if phone and agent_id:
            call = Call(
                tenant_id=current_user.tenant_id,
                agent_id=agent_id,
                direction=CallDirection.outbound,
                status=CallStatus.queued,
                from_number=get_settings().twilio_from_number or '+10000000000',
                to_number=phone,
                context_payload=workflow_result.get('context_payload', {}),
            )
            db.add(call)
            await db.flush()
            linked_call_id = call.id
            provider = get_telephony_provider('twilio')
            callback_url = f"{get_settings().public_base_url}/api/v1/webhooks/telephony/inbound?call_id={call.id}"
            result = await provider.create_outbound_call(phone, call.from_number, callback_url)
            call.external_call_id = result.external_call_id
            call.status = CallStatus.ringing

    submission = FormSubmission(
        tenant_id=current_user.tenant_id,
        form_id=form.id,
        payload=payload.payload,
        linked_call_id=linked_call_id,
    )
    db.add(submission)

    await audit_log(
        db,
        tenant_id=current_user.tenant_id,
        action='form.submit',
        resource_type='form_submission',
        resource_id=str(submission.id),
        actor_user_id=current_user.id,
        metadata={'form_id': str(form.id), 'workflow_action': workflow_result['action']},
    )

    await db.commit()
    await db.refresh(submission)

    return FormSubmissionResponse(
        id=str(submission.id),
        form_id=str(submission.form_id),
        tenant_id=str(submission.tenant_id),
        payload=submission.payload,
        linked_call_id=str(submission.linked_call_id) if submission.linked_call_id else None,
        created_at=submission.created_at,
    )
