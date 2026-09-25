from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User

EVENT_TYPES = (
    "REPORT_CREATED",
    "REPORT_ANALYZED",
    "SIF_CLASSIFIED",
    "RULE_MAPPED",
    "REVIEW_STARTED",
    "REVIEW_COMPLETED",
    "TAXONOMY_CHANGED",
    "MODEL_CHANGED",
    "IMPORT_COMPLETED",
    "SETTINGS_CHANGED",
    "PATTERNS_MINED",
    "USER_LOGIN",
    "DATASET_SEEDED",
)


def log_event(
    db: Session,
    event_type: str,
    summary: str,
    *,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    actor: User | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        actor_id=actor.id if actor else None,
        actor_name=actor.full_name if actor else "system",
        summary=summary,
        details=details or {},
    )
    db.add(entry)
    return entry
