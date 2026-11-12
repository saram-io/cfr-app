from datetime import datetime, timezone
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..audit import record_audit_event
from ..auth import get_current_user, require_roles, verify_esignature
from ..compliance import compute_next_run, resolve_cron_expression
from ..database import get_db
from ..models import Asset, BackupJob, BackupPolicy, SnapshotRecord, StorageRepository, User
from ..restic_manager import (
    init_repository,
    list_snapshot_files,
    run_gateway_backup,
    validate_resticprofile,
    write_asset_resticprofile,
)
from ..schemas import BackupPolicyCreateUpdate, BackupPolicyOut

router = APIRouter(prefix="/policies", tags=["Backup Policies & Schedules"])


def _serialize_policy(policy: BackupPolicy) -> BackupPolicyOut:
    return BackupPolicyOut(
        id=policy.id,
        asset_id=policy.asset_id,
        asset_tag=policy.asset.asset_tag if policy.asset else "UNKNOWN",
        asset_name=policy.asset.name if policy.asset else "Unknown",
        is_gmp=policy.asset.is_gmp if policy.asset else False,
        criticality=policy.asset.criticality if policy.asset else "MINOR",
        repository_id=policy.repository_id,
        repository_name=policy.repository.name if policy.repository else "Unknown",
        backend_type=policy.repository.backend_type if policy.repository else "LOCAL_NAS",
        name=policy.name,
        is_enabled=policy.is_enabled,
        execution_mode=policy.execution_mode,
        schedule_preset=policy.schedule_preset,
        schedule_cron=policy.schedule_cron,
        backup_paths=json.loads(policy.backup_paths_json or "[]"),
        exclude_patterns=json.loads(policy.exclude_patterns_json or "[]"),
        rpo_hours=policy.rpo_hours,
        rto_hours=policy.rto_hours,
        retention_keep_last=policy.retention_keep_last,
        retention_keep_daily=policy.retention_keep_daily,
        retention_keep_weekly=policy.retention_keep_weekly,
        retention_keep_monthly=policy.retention_keep_monthly,
        retention_keep_yearly=policy.retention_keep_yearly,
        vss_enabled=policy.vss_enabled,
        pre_backup_hook=policy.pre_backup_hook,
        gateway_share_uri=policy.gateway_share_uri,
        force_run_requested=policy.force_run_requested,
        config_version=policy.config_version,
        last_run_at=policy.last_run_at,
        next_run_at=policy.next_run_at,
        updated_at=policy.updated_at,
    )


@router.get("", response_model=List[BackupPolicyOut])
def list_policies(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    policies = db.query(BackupPolicy).order_by(BackupPolicy.id.asc()).all()
    return [_serialize_policy(p) for p in policies]


@router.post("", response_model=BackupPolicyOut)
def create_or_update_policy(
    payload: BackupPolicyCreateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "QA_Compliance", "Lab_Engineer")),
):
    asset = db.query(Asset).filter(Asset.id == payload.asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    repo = db.query(StorageRepository).filter(StorageRepository.id == payload.repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Storage repository not found")

    existing = db.query(BackupPolicy).filter(BackupPolicy.asset_id == payload.asset_id).first()

    signer = current_user
    sig_verified = False
    sig_meaning = None
    reason = "Configured backup policy and retention schedule"

    # Modifying an existing GMP or Critical asset's backup policy requires 21 CFR Part 11 E-Signature
    if existing and (asset.is_gmp or asset.criticality == "CRITICAL"):
        signer = verify_esignature(db, payload.esignature)
        sig_verified = True
        sig_meaning = payload.esignature.meaning
        reason = payload.esignature.reason
    elif payload.esignature:
        signer = verify_esignature(db, payload.esignature)
        sig_verified = True
        sig_meaning = payload.esignature.meaning
        reason = payload.esignature.reason

    cron_expr = resolve_cron_expression(payload.schedule_preset, payload.schedule_cron)
    next_run = compute_next_run(cron_expr)

    old_val = None
    if existing:
        old_val = {
            "schedule_preset": existing.schedule_preset,
            "schedule_cron": existing.schedule_cron,
            "repository_id": existing.repository_id,
            "backup_paths": json.loads(existing.backup_paths_json or "[]"),
            "is_enabled": existing.is_enabled,
            "rpo_hours": existing.rpo_hours,
            "config_version": existing.config_version,
        }
        existing.repository_id = payload.repository_id
        existing.name = payload.name
        existing.is_enabled = payload.is_enabled
        existing.execution_mode = payload.execution_mode
        existing.schedule_preset = payload.schedule_preset
        existing.schedule_cron = cron_expr
        existing.backup_paths_json = json.dumps(payload.backup_paths)
        existing.exclude_patterns_json = json.dumps(payload.exclude_patterns)
        existing.rpo_hours = payload.rpo_hours
        existing.rto_hours = payload.rto_hours
        existing.retention_keep_last = payload.retention_keep_last
        existing.retention_keep_daily = payload.retention_keep_daily
        existing.retention_keep_weekly = payload.retention_keep_weekly
        existing.retention_keep_monthly = payload.retention_keep_monthly
        existing.retention_keep_yearly = payload.retention_keep_yearly
        existing.vss_enabled = payload.vss_enabled
        existing.pre_backup_hook = payload.pre_backup_hook
        existing.gateway_share_uri = payload.gateway_share_uri
        existing.config_version = (existing.config_version or 1) + 1
        existing.next_run_at = next_run
        policy = existing
        action_name = "BACKUP_POLICY_UPDATED"
    else:
        policy = BackupPolicy(
            asset_id=payload.asset_id,
            repository_id=payload.repository_id,
            name=payload.name,
            is_enabled=payload.is_enabled,
            execution_mode=payload.execution_mode,
            schedule_preset=payload.schedule_preset,
            schedule_cron=cron_expr,
            backup_paths_json=json.dumps(payload.backup_paths),
            exclude_patterns_json=json.dumps(payload.exclude_patterns),
            rpo_hours=payload.rpo_hours,
            rto_hours=payload.rto_hours,
            retention_keep_last=payload.retention_keep_last,
            retention_keep_daily=payload.retention_keep_daily,
            retention_keep_weekly=payload.retention_keep_weekly,
            retention_keep_monthly=payload.retention_keep_monthly,
            retention_keep_yearly=payload.retention_keep_yearly,
            vss_enabled=payload.vss_enabled,
            pre_backup_hook=payload.pre_backup_hook,
            gateway_share_uri=payload.gateway_share_uri,
            config_version=1,
            next_run_at=next_run,
        )
        db.add(policy)
        action_name = "BACKUP_POLICY_CREATED"

    db.commit()
    db.refresh(policy)

    # Materialize declarative resticprofile YAML in DATA_DIR/profiles
    write_asset_resticprofile(repo, asset, policy)

    record_audit_event(
        db,
        actor_username=signer.username,
        actor_role=signer.role,
        action=action_name,
        entity_type="BackupPolicy",
        entity_id=f"{asset.asset_tag}:v{policy.config_version}",
        summary=f"{'Updated' if old_val else 'Created'} backup policy for '{asset.asset_tag}' (Schedule: {policy.schedule_preset} [{policy.schedule_cron}], Repo: {repo.name})",
        old_value=old_val,
        new_value={
            "schedule_preset": policy.schedule_preset,
            "schedule_cron": policy.schedule_cron,
            "repository_id": policy.repository_id,
            "backup_paths": payload.backup_paths,
            "is_enabled": policy.is_enabled,
            "rpo_hours": policy.rpo_hours,
            "config_version": policy.config_version,
        },
        reason=reason,
        signature_meaning=sig_meaning,
        signature_verified=sig_verified,
    )
    return _serialize_policy(policy)


@router.get("/{policy_id}/resticprofile")
def get_policy_resticprofile(
    policy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Returns the generated resticprofile profiles.yaml and validated 'resticprofile show' output."""
    policy = db.query(BackupPolicy).filter(BackupPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup policy not found")
    return validate_resticprofile(policy.repository, policy.asset, policy)


@router.post("/{policy_id}/run-now")
def trigger_backup_now(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "QA_Compliance", "Lab_Engineer")),
):
    policy = db.query(BackupPolicy).filter(BackupPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup policy not found")

    asset = policy.asset
    repo = policy.repository

    # Ensure repository is initialized
    if not repo.is_initialized:
        ok, msg = init_repository(repo)
        repo.is_initialized = ok
        repo.status = "HEALTHY" if ok else "ERROR"
        repo.last_check_output = msg
        db.commit()

    # Flag force_run_requested for remote polling agents AND execute gateway/local snapshot immediately
    policy.force_run_requested = True
    started_at = datetime.now(timezone.utc)
    job = BackupJob(
        policy_id=policy.id,
        asset_id=asset.id,
        repository_id=repo.id,
        triggered_by=f"MANUAL ({current_user.username})",
        execution_mode=policy.execution_mode,
        status="RUNNING",
        started_at=started_at,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    result = run_gateway_backup(repo, asset, policy)
    completed_at = datetime.now(timezone.utc)

    job.status = result["status"]
    job.completed_at = completed_at
    job.duration_seconds = result["duration_seconds"]
    job.snapshot_id = result["snapshot_id"]
    job.files_new = result["files_new"]
    job.files_changed = result["files_changed"]
    job.files_unmodified = result["files_unmodified"]
    job.bytes_added = result["bytes_added"]
    job.total_bytes_processed = result["total_bytes_processed"]
    job.log_output = result["log_output"]
    job.error_message = result["error_message"]

    snapshot_record = None
    if result["status"] == "COMPLETED" and result.get("snapshot_id"):
        snap_id = result["snapshot_id"]
        policy.last_run_at = completed_at
        policy.next_run_at = compute_next_run(policy.schedule_cron, completed_at)
        policy.force_run_requested = False

        existing_snap = db.query(SnapshotRecord).filter(SnapshotRecord.snapshot_id == snap_id).first()
        if not existing_snap:
            files = list_snapshot_files(repo, snap_id)
            file_count = sum(1 for f in files if f.get("type") == "file") or (
                result["files_new"] + result["files_changed"] + result["files_unmodified"]
            )
            snapshot_record = SnapshotRecord(
                snapshot_id=snap_id,
                short_id=snap_id[:8],
                asset_id=asset.id,
                repository_id=repo.id,
                job_id=job.id,
                hostname=asset.hostname_or_ip or asset.asset_tag,
                paths_json=policy.backup_paths_json,
                tags_json=json.dumps([f"asset:{asset.asset_tag}", f"gmp:{asset.is_gmp}", f"criticality:{asset.criticality}"]),
                created_at=completed_at,
                size_bytes=result["total_bytes_processed"],
                file_count=file_count,
                is_verified=False,
            )
            db.add(snapshot_record)

    db.commit()
    db.refresh(job)

    record_audit_event(
        db,
        actor_username=current_user.username,
        actor_role=current_user.role,
        action="BACKUP_EXECUTED",
        entity_type="BackupJob",
        entity_id=str(job.id),
        summary=f"Executed Restic backup for '{asset.asset_tag}' -> Status: {job.status}, Snapshot: {job.snapshot_id or 'N/A'}",
        new_value={
            "job_id": job.id,
            "asset_tag": asset.asset_tag,
            "status": job.status,
            "snapshot_id": job.snapshot_id,
            "bytes_added": job.bytes_added,
            "total_bytes_processed": job.total_bytes_processed,
        },
    )

    return {
        "job_id": job.id,
        "status": job.status,
        "snapshot_id": job.snapshot_id,
        "duration_seconds": job.duration_seconds,
        "files_new": job.files_new,
        "files_changed": job.files_changed,
        "files_unmodified": job.files_unmodified,
        "bytes_added": job.bytes_added,
        "total_bytes_processed": job.total_bytes_processed,
        "error_message": job.error_message,
        "log_output": job.log_output,
    }
