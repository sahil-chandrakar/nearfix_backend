import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin_audit_log import AdminAuditLog
from app.models.user import User
from app.schemas.admin import AdminAuditLogRead


class AuditRepository:
    @staticmethod
    def create(
        db: Session,
        *,
        admin_user: User,
        action: str,
        target_type: str,
        target_id: str | int | None = None,
        metadata: dict | None = None,
    ) -> AdminAuditLog:
        audit_log = AdminAuditLog(
            admin_user_id=admin_user.id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            metadata_json=json.dumps(metadata, default=str) if metadata else None,
        )
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return audit_log

    @staticmethod
    def list_recent(db: Session, *, limit: int = 100) -> list[AdminAuditLogRead]:
        rows = list(
            db.scalars(
                select(AdminAuditLog)
                .order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
                .limit(limit)
            )
        )
        return [
            AdminAuditLogRead(
                id=row.id,
                admin_user_id=row.admin_user_id,
                action=row.action,
                target_type=row.target_type,
                target_id=row.target_id,
                metadata=json.loads(row.metadata_json) if row.metadata_json else None,
                created_at=row.created_at,
            )
            for row in rows
        ]
