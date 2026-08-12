import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from db1.models.Base1 import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    actor_id: int | None,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    commit: bool = False,
):
    """
    Записывает событие в audit_logs.
    commit=False по умолчанию — вызывающий код обычно уже делает свой db.commit()
    в той же транзакции (см. паттерн ниже), это дешевле и атомарнее.
    """
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=json.dumps(details, default=str) if details else None,
        ip_address=ip_address,
    )
    db.add(entry)
    if commit:
        try:
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to commit audit log: {e}")
            await db.rollback()
    return entry