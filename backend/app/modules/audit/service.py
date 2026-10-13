from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


def record(
    session: AsyncSession,
    action: str,
    entity: str,
    entity_id: int | None = None,
    actor_id: int | None = None,
    **data,
) -> None:
    """Записать действие в журнал в рамках текущей транзакции."""
    session.add(AuditLog(actor_id=actor_id, action=action, entity=entity, entity_id=entity_id, data=data))
