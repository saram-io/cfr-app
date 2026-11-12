from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Optional
from sqlalchemy.orm import Session
from .models import AuditLog

GENESIS_HASH = "0" * 64


def _compute_record_hash(
    previous_hash: str,
    timestamp_iso: str,
    actor_username: str,
    actor_role: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    old_value_json: str,
    new_value_json: str,
    reason: str,
    signature_meaning: str,
    signature_verified: bool,
) -> str:
    canonical = "|".join(
        [
            previous_hash,
            timestamp_iso,
            actor_username,
            actor_role,
            action,
            entity_type,
            str(entity_id),
            summary,
            old_value_json or "",
            new_value_json or "",
            reason or "",
            signature_meaning or "",
            "1" if signature_verified else "0",
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_audit_event(
    db: Session,
    *,
    actor_username: str,
    actor_role: str,
    action: str,
    entity_type: str,
    entity_id: Any,
    summary: str,
    old_value: Any = None,
    new_value: Any = None,
    reason: Optional[str] = None,
    signature_meaning: Optional[str] = None,
    signature_verified: bool = False,
) -> AuditLog:
    last_entry = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    previous_hash = last_entry.record_hash if last_entry else GENESIS_HASH

    now = datetime.now(timezone.utc).replace(microsecond=0)
    ts_iso = now.isoformat()
    old_str = json.dumps(old_value, sort_keys=True, default=str) if old_value is not None else ""
    new_str = json.dumps(new_value, sort_keys=True, default=str) if new_value is not None else ""

    record_hash = _compute_record_hash(
        previous_hash=previous_hash,
        timestamp_iso=ts_iso,
        actor_username=actor_username,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        summary=summary,
        old_value_json=old_str,
        new_value_json=new_str,
        reason=reason or "",
        signature_meaning=signature_meaning or "",
        signature_verified=signature_verified,
    )

    entry = AuditLog(
        timestamp=now,
        actor_username=actor_username,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        summary=summary,
        old_value_json=old_str or None,
        new_value_json=new_str or None,
        reason=reason,
        signature_meaning=signature_meaning,
        signature_verified=signature_verified,
        previous_hash=previous_hash,
        record_hash=record_hash,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def verify_audit_chain(db: Session) -> dict:
    """Re-computes every SHA-256 link in the audit log to verify 21 CFR Part 11 immutability."""
    entries = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    expected_prev = GENESIS_HASH
    broken_links = []

    for entry in entries:
        ts_iso = entry.timestamp.replace(tzinfo=timezone.utc, microsecond=0).isoformat()
        recomputed = _compute_record_hash(
            previous_hash=entry.previous_hash,
            timestamp_iso=ts_iso,
            actor_username=entry.actor_username,
            actor_role=entry.actor_role,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            summary=entry.summary,
            old_value_json=entry.old_value_json or "",
            new_value_json=entry.new_value_json or "",
            reason=entry.reason or "",
            signature_meaning=entry.signature_meaning or "",
            signature_verified=bool(entry.signature_verified),
        )
        if entry.previous_hash != expected_prev or recomputed != entry.record_hash:
            broken_links.append(
                {
                    "id": entry.id,
                    "expected_previous_hash": expected_prev,
                    "actual_previous_hash": entry.previous_hash,
                    "expected_record_hash": recomputed,
                    "actual_record_hash": entry.record_hash,
                }
            )
        expected_prev = entry.record_hash

    return {
        "valid": len(broken_links) == 0,
        "total_records": len(entries),
        "head_hash": expected_prev,
        "broken_links": broken_links,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
