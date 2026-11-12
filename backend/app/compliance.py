from datetime import datetime, timedelta, timezone
from typing import Optional
from croniter import croniter
from .models import Asset
from .schemas import AssetComplianceStatus

PRESET_CRON_MAP = {
    "HOURLY": "0 * * * *",
    "EVERY_4_HOURS": "0 */4 * * *",
    "DAILY": "0 2 * * *",
    "WEEKLY": "0 3 * * 0",
}


def resolve_cron_expression(preset: str, custom_cron: str) -> str:
    if preset in PRESET_CRON_MAP:
        return PRESET_CRON_MAP[preset]
    return custom_cron.strip() or "0 2 * * *"


def compute_next_run(cron_expr: str, base_time: Optional[datetime] = None) -> datetime:
    now = base_time or datetime.now(timezone.utc)
    try:
        itr = croniter(cron_expr, now)
        nxt = itr.get_next(datetime)
        if nxt.tzinfo is None:
            nxt = nxt.replace(tzinfo=timezone.utc)
        return nxt
    except Exception:
        return now + timedelta(hours=24)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_asset_compliance(asset: Asset) -> AssetComplianceStatus:
    now = datetime.now(timezone.utc)
    backup_required = bool(asset.criticality == "CRITICAL" or asset.is_gmp)
    has_active_policy = bool(asset.policy and asset.policy.is_enabled)
    has_approved_sop = bool(asset.sop and asset.sop.status == "APPROVED")

    # Find latest backup timestamp
    last_backup_at: Optional[datetime] = None
    if asset.policy and asset.policy.last_run_at:
        last_backup_at = _ensure_utc(asset.policy.last_run_at)
    if asset.snapshots:
        latest_snap = max((_ensure_utc(s.created_at) for s in asset.snapshots if s.created_at), default=None)
        if latest_snap and (not last_backup_at or latest_snap > last_backup_at):
            last_backup_at = latest_snap

    rpo_hours = asset.policy.rpo_hours if asset.policy else (asset.sop.target_rpo_hours if asset.sop else 24)
    rpo_compliant = True
    if backup_required:
        if not last_backup_at:
            rpo_compliant = False
        else:
            age_hours = (now - last_backup_at).total_seconds() / 3600.0
            rpo_compliant = age_hours <= (rpo_hours + 1)

    # Find latest restore drill
    last_restore_drill_at: Optional[datetime] = None
    qa_approved_drill_at: Optional[datetime] = None
    pending_qa_drill = False
    if asset.restore_drills:
        for d in asset.restore_drills:
            dt = _ensure_utc(d.completed_at or d.started_at)
            if dt and (not last_restore_drill_at or dt > last_restore_drill_at):
                last_restore_drill_at = dt
            if d.status == "QA_APPROVED" and dt:
                if not qa_approved_drill_at or dt > qa_approved_drill_at:
                    qa_approved_drill_at = dt
            elif d.status == "COMPLETED_PENDING_QA":
                pending_qa_drill = True

    drill_interval_days = asset.sop.drill_interval_days if asset.sop else 90
    restore_drill_compliant = True
    if asset.criticality == "CRITICAL":
        if not qa_approved_drill_at:
            restore_drill_compliant = False
        else:
            drill_age_days = (now - qa_approved_drill_at).total_seconds() / 86400.0
            restore_drill_compliant = drill_age_days <= drill_interval_days

    issues = []
    if not backup_required and not has_active_policy:
        return AssetComplianceStatus(
            overall_status="EXEMPT",
            backup_required=False,
            has_active_policy=False,
            has_approved_sop=has_approved_sop,
            rpo_compliant=True,
            restore_drill_compliant=True,
            last_backup_at=last_backup_at,
            last_restore_drill_at=last_restore_drill_at,
            issues=[],
        )

    if backup_required and not has_active_policy:
        issues.append("Missing active Restic backup policy (mandatory for Critical/GMP asset)")
    if backup_required and not has_approved_sop:
        issues.append("No approved Backup & Restore SOP linked to asset")
    if backup_required and not rpo_compliant:
        if not last_backup_at:
            issues.append(f"No Restic backup snapshot recorded (Target RPO: {rpo_hours}h)")
        else:
            issues.append(f"Last backup exceeded RPO window of {rpo_hours}h")
    if asset.criticality == "CRITICAL" and not restore_drill_compliant:
        if pending_qa_drill:
            issues.append("Restore verification drill executed; awaiting QA Electronic Signature sign-off")
        else:
            issues.append(f"No QA-approved SOP Restore Verification Drill within {drill_interval_days} days")

    if not issues:
        overall = "COMPLIANT"
    elif (not has_active_policy) or (not has_approved_sop) or (not rpo_compliant):
        overall = "NON_COMPLIANT"
    else:
        overall = "AT_RISK"

    return AssetComplianceStatus(
        overall_status=overall,
        backup_required=backup_required,
        has_active_policy=has_active_policy,
        has_approved_sop=has_approved_sop,
        rpo_compliant=rpo_compliant,
        restore_drill_compliant=restore_drill_compliant,
        last_backup_at=last_backup_at,
        last_restore_drill_at=last_restore_drill_at,
        issues=issues,
    )
