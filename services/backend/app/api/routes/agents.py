from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_roles
from app.db.session import get_db
from app.models.models import Agent, UserRole
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdateConfig
from app.services.audit.service import audit_log

router = APIRouter(tags=['agents'])


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
