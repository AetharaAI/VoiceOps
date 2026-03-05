from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditEvent


async def audit_log(
    db: AsyncSession,
    *,
    tenant_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    actor_user_id: str | None,
    metadata: dict | None = None,
) -> None:
    event = AuditEvent(
        tenant_id=tenant_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_user_id=actor_user_id,
        event_metadata=metadata or {},
    )
    db.add(event)
    await db.flush()
