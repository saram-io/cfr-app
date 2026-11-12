from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..auth import get_current_user
from ..compliance import compute_asset_compliance
from ..database import get_db
from ..models import Asset, AuditLog, BackupJob, RestoreDrill, SnapshotRecord, StorageRepository, User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    assets = db.query(Asset).order_by(Asset.id.asc()).all()
    repos = db.query(StorageRepository).all()
    snapshots_count = db.query(SnapshotRecord).count()
    recent_jobs = db.query(BackupJob).order_by(BackupJob.started_at.desc()).limit(8).all()
    recent_drills = db.query(RestoreDrill).order_by(RestoreDrill.started_at.desc()).limit(6).all()
    audit_count = db.query(AuditLog).count()

    total_assets = len(assets)
    gmp_assets = sum(1 for a in assets if a.is_gmp)
    critical_assets = sum(1 for a in assets if a.criticality == "CRITICAL")

    compliant_count = 0
    at_risk_count = 0
    non_compliant_count = 0
    exempt_count = 0
    alerts = []

    for asset in assets:
        comp = compute_asset_compliance(asset)
        if comp.overall_status == "COMPLIANT":
            compliant_count += 1
        elif comp.overall_status == "AT_RISK":
            at_risk_count += 1
        elif comp.overall_status == "NON_COMPLIANT":
            non_compliant_count += 1
        else:
            exempt_count += 1

        for issue in comp.issues:
            alerts.append(
                {
                    "asset_id": asset.id,
                    "asset_tag": asset.asset_tag,
                    "asset_name": asset.name,
                    "is_gmp": asset.is_gmp,
                    "criticality": asset.criticality,
                    "severity": "HIGH" if comp.overall_status == "NON_COMPLIANT" else "MEDIUM",
                    "message": issue,
                }
            )

    regulated_total = max(total_assets - exempt_count, 1)
    compliance_score = round((compliant_count / regulated_total) * 100, 1)

    return {
        "kpis": {
            "total_assets": total_assets,
            "gmp_assets": gmp_assets,
            "critical_assets": critical_assets,
            "compliant_assets": compliant_count,
            "at_risk_assets": at_risk_count,
            "non_compliant_assets": non_compliant_count,
            "exempt_assets": exempt_count,
            "compliance_score_pct": compliance_score,
            "total_repositories": len(repos),
            "healthy_repositories": sum(1 for r in repos if r.status == "HEALTHY"),
            "total_snapshots": snapshots_count,
            "total_audit_records": audit_count,
        },
        "alerts": alerts,
        "recent_jobs": [
            {
                "id": j.id,
                "asset_id": j.asset_id,
                "asset_tag": j.asset.asset_tag if j.asset else "UNKNOWN",
                "asset_name": j.asset.name if j.asset else "Unknown",
                "status": j.status,
                "triggered_by": j.triggered_by,
                "execution_mode": j.execution_mode,
                "snapshot_id": j.snapshot_id,
                "bytes_added": j.bytes_added,
                "duration_seconds": j.duration_seconds,
                "started_at": j.started_at,
            }
            for j in recent_jobs
        ],
        "recent_drills": [
            {
                "id": d.id,
                "asset_id": d.asset_id,
                "asset_tag": d.asset.asset_tag if d.asset else "UNKNOWN",
                "snapshot_id": d.snapshot_id,
                "restore_type": d.restore_type,
                "status": d.status,
                "actual_rto_minutes": d.actual_rto_minutes,
                "target_rto_minutes": d.target_rto_minutes,
                "checksum_verified": d.checksum_verified,
                "executed_by": d.executed_by,
                "qa_signed_by": d.qa_signed_by,
                "started_at": d.started_at,
            }
            for d in recent_drills
        ],
    }
