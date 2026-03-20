from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_roles
from app.core.config import get_settings
from app.db.session import get_db
from app.models.models import Agent, UserRole
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdateConfig, TTSVoiceOption
from app.services.audit.service import audit_log
from app.services.tts.voice_registry import list_tts_voices

router = APIRouter(tags=['agents'])


def derive_llm_models_url(llm_endpoint: str) -> str:
    parsed = urlsplit(llm_endpoint)
    path = parsed.path or ''

    if '/chat/completions' in path:
        model_path = path.replace('/chat/completions', '/models')
    elif path.endswith('/completions'):
        model_path = f"{path[: -len('/completions')]}/models"
    elif path.rstrip('/').endswith('/v1'):
        model_path = f'{path.rstrip("/")}/models'
    else:
        model_path = '/v1/models'

    return urlunsplit((parsed.scheme, parsed.netloc, model_path, '', ''))


def extract_llm_model_ids(payload: object) -> list[str]:
    items: list[object]
    if isinstance(payload, dict):
        data = payload.get('data')
        if isinstance(data, list):
            items = data
        else:
            items = []
    elif isinstance(payload, list):
        items = payload
    else:
        items = []

    model_ids: list[str] = []
    for item in items:
        if isinstance(item, str):
            candidate = item.strip()
        elif isinstance(item, dict):
            candidate = str(item.get('id', '')).strip()
        else:
            candidate = ''

        if candidate and candidate not in model_ids:
            model_ids.append(candidate)

    return model_ids


@router.post('/agents', response_model=AgentResponse)
async def create_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.owner, UserRole.admin)),
) -> AgentResponse:
    agent = Agent(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        persona=payload.persona,
        script=payload.script,
        required_fields=payload.required_fields,
        tools_config=payload.tools_config,
        policy_config=payload.policy_config,
        workflow_dsl=payload.workflow_dsl,
    )
    db.add(agent)
    await db.flush()

    await audit_log(
        db,
        tenant_id=current_user.tenant_id,
        action='agent.create',
        resource_type='agent',
        resource_id=str(agent.id),
        actor_user_id=current_user.id,
        metadata={'name': payload.name},
    )
    await db.commit()

    return AgentResponse(
        id=str(agent.id),
        tenant_id=str(agent.tenant_id),
        name=agent.name,
        persona=agent.persona,
        script=agent.script,
        required_fields=agent.required_fields,
        tools_config=agent.tools_config,
        policy_config=agent.policy_config,
        workflow_dsl=agent.workflow_dsl,
    )


@router.get('/agents', response_model=list[AgentResponse])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[AgentResponse]:
    rows = (
        await db.execute(select(Agent).where(Agent.tenant_id == current_user.tenant_id).order_by(Agent.created_at.desc()))
    ).scalars().all()
    return [
        AgentResponse(
            id=str(agent.id),
            tenant_id=str(agent.tenant_id),
            name=agent.name,
            persona=agent.persona,
            script=agent.script,
            required_fields=agent.required_fields,
            tools_config=agent.tools_config,
            policy_config=agent.policy_config,
            workflow_dsl=agent.workflow_dsl,
        )
        for agent in rows
    ]


@router.get('/tts/voices', response_model=list[TTSVoiceOption])
async def list_supported_tts_voices(
    current_user: CurrentUser = Depends(get_current_user),
) -> list[TTSVoiceOption]:
    _ = current_user
    return [TTSVoiceOption(**voice) for voice in list_tts_voices()]


@router.get('/llm/models', response_model=list[str])
async def list_live_llm_models(
    current_user: CurrentUser = Depends(get_current_user),
) -> list[str]:
    _ = current_user
    settings = get_settings()

    if not settings.llm_endpoint:
        raise HTTPException(status_code=503, detail='LLM endpoint is not configured')

    headers: dict[str, str] = {}
    if settings.llm_api_key:
        headers['Authorization'] = f'Bearer {settings.llm_api_key}'

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(derive_llm_models_url(settings.llm_endpoint), headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502, detail=f'Upstream model list failed with status {exc.response.status_code}'
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'Upstream model list failed: {exc}') from exc

    model_ids = extract_llm_model_ids(response.json())
    if not model_ids:
        raise HTTPException(status_code=502, detail='Upstream model list response did not contain any models')

    return model_ids


@router.put('/agents/{agent_id}/config', response_model=AgentResponse)
async def update_agent_config(
    agent_id: str,
    payload: AgentUpdateConfig,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.owner, UserRole.admin)),
) -> AgentResponse:
    agent = (
        await db.execute(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == current_user.tenant_id))
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail='Agent not found')

    changes = payload.model_dump(exclude_none=True)
    for key, value in changes.items():
        setattr(agent, key, value)

    await audit_log(
        db,
        tenant_id=current_user.tenant_id,
        action='agent.config.update',
        resource_type='agent',
        resource_id=str(agent.id),
        actor_user_id=current_user.id,
        metadata={'updated_fields': list(changes.keys())},
    )
    await db.commit()
    await db.refresh(agent)

    return AgentResponse(
        id=str(agent.id),
        tenant_id=str(agent.tenant_id),
        name=agent.name,
        persona=agent.persona,
        script=agent.script,
        required_fields=agent.required_fields,
        tools_config=agent.tools_config,
        policy_config=agent.policy_config,
        workflow_dsl=agent.workflow_dsl,
    )
