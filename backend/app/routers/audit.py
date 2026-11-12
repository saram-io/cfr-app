import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..audit import verify_audit_chain
from ..auth import get_current_user
from ..database import get_db
from ..models import AuditLog, User

router = APIRouter(prefix="/audit", tags=["21 CFR Part 11 Audit Trail"])


@router.get("")
def list_audit_logs(
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "timestamp": l.timestamp,
            "actor_username": l.actor_username,
            "actor_role": l.actor_role,
            "action": l.action,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "summary": l.summary,
            "old_value": json.loads(l.old_value_json) if l.old_value_json else None,
            "new_value": json.loads(l.new_value_json) if l.new_value_json else None,
            "reason": l.reason,
            "signature_meaning": l.signature_meaning,
            "signature_verified": l.signature_verified,
            "previous_hash": l.previous_hash,
            "record_hash": l.record_hash,
        }
        for l in logs
    ]


@router.get("/verify")
def verify_audit_trail_integrity(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return verify_audit_chain(db)
