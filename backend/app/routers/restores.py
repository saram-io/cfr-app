from datetime import datetime, timezone
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from ..audit import record_audit_event
from ..auth import get_current_user, require_roles, verify_esignature
from ..config import DATA_DIR
from ..database import get_db
from ..models import Asset, RestoreDrill, SnapshotRecord, StorageRepository, User
from ..restic_manager import execute_restore_and_verify
from ..schemas import RestoreExecuteRequest, RestoreSignOffRequest

router = APIRouter(prefix="/restores", tags=["Restore & SOP Verification Drills"])


def _serialize_drill(d: RestoreDrill) -> dict:
    return {
        "id": d.id,
        "asset_id": d.asset_id,
        "asset_tag": d.asset.asset_tag if d.asset else "UNKNOWN",
        "asset_name": d.asset.name if d.asset else "Unknown",
        "is_gmp": d.asset.is_gmp if d.asset else False,
        "criticality": d.asset.criticality if d.asset else "MINOR",
        "repository_id": d.repository_id,
        "snapshot_id": d.snapshot_id,
        "sop_id": d.sop_id,
        "restore_type": d.restore_type,
        "target_path": d.target_path,
        "status": d.status,
        "started_at": d.started_at,
        "completed_at": d.completed_at,
        "actual_rto_minutes": d.actual_rto_minutes,
        "target_rto_minutes": d.target_rto_minutes,
        "restored_file_count": d.restored_file_count,
        "restored_bytes": d.restored_bytes,
        "checksum_verified": d.checksum_verified,
        "sha256_manifest": json.loads(d.sha256_manifest_json or "[]"),
        "checklist_results": json.loads(d.checklist_results_json or "[]"),
        "executed_by": d.executed_by,
        "qa_signed_by": d.qa_signed_by,
        "qa_signed_at": d.qa_signed_at,
        "qa_signature_meaning": d.qa_signature_meaning,
        "notes": d.notes,
    }


@router.get("")
def list_restore_drills(
    asset_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(RestoreDrill)
    if asset_id is not None:
        q = q.filter(RestoreDrill.asset_id == asset_id)
    drills = q.order_by(RestoreDrill.started_at.desc()).all()
    return [_serialize_drill(d) for d in drills]


@router.post("/execute", status_code=status.HTTP_201_CREATED)
def execute_restore_drill(
    payload: RestoreExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "QA_Compliance", "Lab_Engineer")),
):
    asset = db.query(Asset).filter(Asset.id == payload.asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    snap = (
        db.query(SnapshotRecord)
        .filter(
            (SnapshotRecord.snapshot_id == payload.snapshot_id)
            | (SnapshotRecord.short_id == payload.snapshot_id)
        )
        .first()
    )
    if not snap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")

    repo = db.query(StorageRepository).filter(StorageRepository.id == snap.repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Storage repository not found")

    target_dir = payload.target_path or str(
        DATA_DIR / "restores" / f"{asset.asset_tag}_{snap.short_id}_{int(datetime.now(timezone.utc).timestamp())}"
    )

    started_at = datetime.now(timezone.utc)
    restore_res = execute_restore_and_verify(repo, snap.snapshot_id, target_dir)
    completed_at = datetime.now(timezone.utc)

    target_rto_hours = asset.policy.rto_hours if asset.policy else (asset.sop.target_rto_hours if asset.sop else 4)
    target_rto_minutes = float(target_rto_hours * 60)

    default_checklist = payload.checklist_results or [
        {"step": "1. Locate snapshot in Restic repository", "passed": True},
        {"step": "2. Execute restic restore to isolated verification target", "passed": restore_res["success"]},
        {"step": "3. Compute & verify SHA-256 manifest of restored files", "passed": restore_res["success"]},
        {
            "step": f"4. Confirm Actual RTO ({restore_res['actual_rto_minutes']}m) <= Target RTO ({target_rto_minutes}m)",
            "passed": restore_res["actual_rto_minutes"] <= target_rto_minutes,
        },
    ]

    qa_signed_by = None
    qa_signed_at = None
    qa_sig_meaning = None
    sig_verified = False
    drill_status = "COMPLETED_PENDING_QA" if restore_res["success"] else "FAILED"

    # If the operator also provided a QA/Admin Electronic Signature during execution, record it immediately
    if payload.esignature and restore_res["success"]:
        signer = verify_esignature(db, payload.esignature, required_roles=["Admin", "QA_Compliance"])
        qa_signed_by = f"{signer.full_name} ({signer.username})"
        qa_signed_at = completed_at
        qa_sig_meaning = payload.esignature.meaning
        sig_verified = True
        drill_status = "QA_APPROVED"
        snap.is_verified = True

    drill = RestoreDrill(
        asset_id=asset.id,
        repository_id=repo.id,
        snapshot_id=snap.snapshot_id,
        sop_id=asset.sop_id,
        restore_type=payload.restore_type,
        target_path=target_dir,
        status=drill_status,
        started_at=started_at,
        completed_at=completed_at,
        actual_rto_minutes=restore_res["actual_rto_minutes"],
        target_rto_minutes=target_rto_minutes,
        restored_file_count=restore_res["restored_file_count"],
        restored_bytes=restore_res["restored_bytes"],
        checksum_verified=restore_res["success"],
        sha256_manifest_json=json.dumps(restore_res["sha256_manifest"]),
        checklist_results_json=json.dumps(default_checklist),
        executed_by=f"{current_user.full_name} ({current_user.username})",
        qa_signed_by=qa_signed_by,
        qa_signed_at=qa_signed_at,
        qa_signature_meaning=qa_sig_meaning,
        notes=payload.notes or restore_res.get("error_message"),
    )
    db.add(drill)
    db.commit()
    db.refresh(drill)

    record_audit_event(
        db,
        actor_username=current_user.username,
        actor_role=current_user.role,
        action="RESTORE_DRILL_EXECUTED",
        entity_type="RestoreDrill",
        entity_id=str(drill.id),
        summary=(
            f"Executed {drill.restore_type} for '{asset.asset_tag}' from snapshot {snap.short_id}: "
            f"{drill.restored_file_count} files ({drill.restored_bytes} B) verified in {drill.actual_rto_minutes}m "
            f"[{drill.status}]"
        ),
        new_value={
            "drill_id": drill.id,
            "asset_tag": asset.asset_tag,
            "snapshot_id": snap.short_id,
            "status": drill.status,
            "restored_file_count": drill.restored_file_count,
            "actual_rto_minutes": drill.actual_rto_minutes,
        },
        reason=payload.esignature.reason if payload.esignature else "SOP Restore Verification execution",
        signature_meaning=qa_sig_meaning,
        signature_verified=sig_verified,
    )
    return _serialize_drill(drill)


@router.post("/{drill_id}/qa-signoff")
def sign_off_restore_drill(
    drill_id: int,
    payload: RestoreSignOffRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin", "QA_Compliance")),
):
    drill = db.query(RestoreDrill).filter(RestoreDrill.id == drill_id).first()
    if not drill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restore drill record not found")

    signer = verify_esignature(db, payload.esignature, required_roles=["Admin", "QA_Compliance"])
    now = datetime.now(timezone.utc)

    drill.status = "QA_APPROVED"
    drill.qa_signed_by = f"{signer.full_name} ({signer.username})"
    drill.qa_signed_at = now
    drill.qa_signature_meaning = payload.esignature.meaning
    if payload.notes:
        drill.notes = (drill.notes + " | " if drill.notes else "") + f"QA Note: {payload.notes}"

    snap = db.query(SnapshotRecord).filter(SnapshotRecord.snapshot_id == drill.snapshot_id).first()
    if snap:
        snap.is_verified = True

    db.commit()
    db.refresh(drill)

    record_audit_event(
        db,
        actor_username=signer.username,
        actor_role=signer.role,
        action="RESTORE_DRILL_QA_SIGNED",
        entity_type="RestoreDrill",
        entity_id=str(drill.id),
        summary=f"QA Electronic Signature ({payload.esignature.meaning}) applied to Restore Drill #{drill.id} for '{drill.asset.asset_tag if drill.asset else ''}'",
        old_value={"status": "COMPLETED_PENDING_QA"},
        new_value={"status": "QA_APPROVED", "qa_signed_by": drill.qa_signed_by},
        reason=payload.esignature.reason,
        signature_meaning=payload.esignature.meaning,
        signature_verified=True,
    )
    return _serialize_drill(drill)
