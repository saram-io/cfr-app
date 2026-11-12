from datetime import datetime, timezone
import json
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from ..audit import record_audit_event
from ..compliance import compute_next_run
from ..config import decrypt_env_dict, decrypt_secret
from ..database import get_db
from ..models import Asset, BackupJob, SnapshotRecord
from ..restic_manager import generate_resticprofile_yaml, profile_name_for_asset
from ..schemas import AgentReportInput

router = APIRouter(prefix="/agents", tags=["Endpoint Backup Agents"])


def _get_asset_by_token(x_agent_token: Optional[str], db: Session) -> Asset:
    if not x_agent_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Agent-Token header")
    asset = db.query(Asset).filter(Asset.agent_token == x_agent_token).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid X-Agent-Token")
    return asset


@router.get("/config")
def poll_agent_config(
    x_agent_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Polled by remote Windows, macOS, and Linux Restic/resticprofile agents to fetch dynamic schedules and credentials."""
    asset = _get_asset_by_token(x_agent_token, db)
    now = datetime.now(timezone.utc)
    asset.agent_last_seen_at = now
    db.commit()

    policy = asset.policy
    if not policy or not policy.repository:
        return {
            "asset_tag": asset.asset_tag,
            "is_gmp": asset.is_gmp,
            "policy_enabled": False,
            "should_run_now": False,
        }

    repo = policy.repository
    should_run_now = bool(policy.force_run_requested)
    if not should_run_now and policy.is_enabled:
        if policy.next_run_at is None:
            should_run_now = True
        else:
            next_utc = (
                policy.next_run_at.replace(tzinfo=timezone.utc)
                if policy.next_run_at.tzinfo is None
                else policy.next_run_at
            )
            if now >= next_utc:
                should_run_now = True

    return {
        "asset_tag": asset.asset_tag,
        "asset_name": asset.name,
        "is_gmp": asset.is_gmp,
        "criticality": asset.criticality,
        "policy_enabled": policy.is_enabled,
        "config_version": policy.config_version,
        "schedule_preset": policy.schedule_preset,
        "schedule_cron": policy.schedule_cron,
        "should_run_now": should_run_now,
        "vss_enabled": policy.vss_enabled,
        "backup_paths": json.loads(policy.backup_paths_json or "[]"),
        "exclude_patterns": json.loads(policy.exclude_patterns_json or "[]"),
        "repository_uri": repo.repo_uri,
        "repository_password": decrypt_secret(repo.encrypted_password),
        "repository_env": decrypt_env_dict(repo.encrypted_env_json),
        "resticprofile_name": profile_name_for_asset(asset),
        "resticprofile_yaml": generate_resticprofile_yaml(repo, asset, policy, for_gateway=False),
        "retention": {
            "keep_last": policy.retention_keep_last,
            "keep_daily": policy.retention_keep_daily,
            "keep_weekly": policy.retention_keep_weekly,
            "keep_monthly": policy.retention_keep_monthly,
            "keep_yearly": policy.retention_keep_yearly,
        },
    }


@router.get("/profile.yaml", response_class=PlainTextResponse)
def get_agent_resticprofile_yaml(
    x_agent_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Returns a declarative resticprofile profiles.yaml configuration for the authenticated endpoint agent."""
    asset = _get_asset_by_token(x_agent_token, db)
    policy = asset.policy
    if not policy or not policy.repository:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active backup policy configured for asset")
    return generate_resticprofile_yaml(policy.repository, asset, policy, for_gateway=False)


@router.post("/report")
def report_agent_backup_result(
    payload: AgentReportInput,
    x_agent_token: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Receives Restic backup completion telemetry from Windows, macOS, and Linux endpoint agents."""
    asset = _get_asset_by_token(x_agent_token, db)
    now = datetime.now(timezone.utc)
    asset.agent_last_seen_at = now

    policy = asset.policy
    if not policy:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No backup policy configured for asset")

    started_at = payload.started_at or now
    completed_at = payload.completed_at or now
    duration = max((completed_at - started_at).total_seconds(), 0.1)

    job = BackupJob(
        policy_id=policy.id,
        asset_id=asset.id,
        repository_id=policy.repository_id,
        triggered_by=f"ENDPOINT_AGENT ({asset.os_type})",
        execution_mode="ENDPOINT_AGENT",
        status=payload.status.upper(),
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=round(duration, 2),
        snapshot_id=payload.snapshot_id,
        files_new=payload.files_new,
        files_changed=payload.files_changed,
        files_unmodified=payload.files_unmodified,
        bytes_added=payload.bytes_added,
        total_bytes_processed=payload.total_bytes_processed,
        log_output=payload.log_output,
        error_message=payload.error_message,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if job.status == "COMPLETED":
        policy.last_run_at = completed_at
        policy.next_run_at = compute_next_run(policy.schedule_cron, completed_at)
        policy.force_run_requested = False

        if payload.snapshot_id:
            existing = db.query(SnapshotRecord).filter(SnapshotRecord.snapshot_id == payload.snapshot_id).first()
            if not existing:
                snap = SnapshotRecord(
                    snapshot_id=payload.snapshot_id,
                    short_id=payload.snapshot_id[:8],
                    asset_id=asset.id,
                    repository_id=policy.repository_id,
                    job_id=job.id,
                    hostname=asset.hostname_or_ip,
                    paths_json=policy.backup_paths_json,
                    tags_json=json.dumps([f"asset:{asset.asset_tag}", f"gmp:{asset.is_gmp}"]),
                    created_at=completed_at,
                    size_bytes=payload.total_bytes_processed,
                    file_count=payload.files_new + payload.files_changed + payload.files_unmodified,
                    is_verified=False,
                )
                db.add(snap)

    db.commit()

    record_audit_event(
        db,
        actor_username=f"agent:{asset.asset_tag}",
        actor_role="Endpoint_Agent",
        action="AGENT_BACKUP_REPORTED",
        entity_type="BackupJob",
        entity_id=str(job.id),
        summary=f"Endpoint agent for '{asset.asset_tag}' reported backup status={job.status} (snapshot={job.snapshot_id or 'N/A'})",
        new_value={"job_id": job.id, "status": job.status, "snapshot_id": job.snapshot_id},
    )
    return {"acknowledged": True, "job_id": job.id}
