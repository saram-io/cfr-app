import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..auth import get_current_user
from ..database import get_db
from ..models import Asset, BackupJob, SnapshotRecord, StorageRepository, User
from ..restic_manager import dump_snapshot_zip, list_repo_snapshots, list_snapshot_files

router = APIRouter(prefix="/backups", tags=["Snapshots & Backup Jobs"])


@router.get("/jobs")
def list_backup_jobs(
    asset_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(BackupJob)
    if asset_id is not None:
        q = q.filter(BackupJob.asset_id == asset_id)
    jobs = q.order_by(BackupJob.started_at.desc()).limit(50).all()
    return [
        {
            "id": j.id,
            "policy_id": j.policy_id,
            "asset_id": j.asset_id,
            "asset_tag": j.asset.asset_tag if j.asset else "UNKNOWN",
            "asset_name": j.asset.name if j.asset else "Unknown",
            "repository_id": j.repository_id,
            "triggered_by": j.triggered_by,
            "execution_mode": j.execution_mode,
            "status": j.status,
            "started_at": j.started_at,
            "completed_at": j.completed_at,
            "duration_seconds": j.duration_seconds,
            "snapshot_id": j.snapshot_id,
            "files_new": j.files_new,
            "files_changed": j.files_changed,
            "files_unmodified": j.files_unmodified,
            "bytes_added": j.bytes_added,
            "total_bytes_processed": j.total_bytes_processed,
            "log_output": j.log_output,
            "error_message": j.error_message,
        }
        for j in jobs
    ]


@router.get("/snapshots")
def list_snapshots(
    asset_id: Optional[int] = Query(None),
    repository_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(SnapshotRecord)
    if asset_id is not None:
        q = q.filter(SnapshotRecord.asset_id == asset_id)
    if repository_id is not None:
        q = q.filter(SnapshotRecord.repository_id == repository_id)
    snaps = q.order_by(SnapshotRecord.created_at.desc()).all()
    repos = {r.id: r.name for r in db.query(StorageRepository).all()}
    return [
        {
            "id": s.id,
            "snapshot_id": s.snapshot_id,
            "short_id": s.short_id,
            "asset_id": s.asset_id,
            "asset_tag": s.asset.asset_tag if s.asset else "UNKNOWN",
            "asset_name": s.asset.name if s.asset else "Unknown",
            "is_gmp": s.asset.is_gmp if s.asset else False,
            "criticality": s.asset.criticality if s.asset else "MINOR",
            "repository_id": s.repository_id,
            "repository_name": repos.get(s.repository_id, "Repository"),
            "hostname": s.hostname,
            "paths": json.loads(s.paths_json or "[]"),
            "tags": json.loads(s.tags_json or "[]"),
            "created_at": s.created_at,
            "size_bytes": s.size_bytes,
            "file_count": s.file_count,
            "is_verified": s.is_verified,
        }
        for s in snaps
    ]


@router.post("/snapshots/sync")
def sync_snapshots_from_restic(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Queries all initialized Restic repositories directly via 'restic snapshots --json' and syncs records."""
    repos = db.query(StorageRepository).filter(StorageRepository.is_initialized == True).all()
    assets_by_tag = {a.asset_tag: a for a in db.query(Asset).all()}
    synced_count = 0

    for repo in repos:
        raw_snaps = list_repo_snapshots(repo)
        for rs in raw_snaps:
            full_id = rs.get("id") or rs.get("short_id")
            if not full_id:
                continue
            existing = db.query(SnapshotRecord).filter(SnapshotRecord.snapshot_id == full_id).first()
            if existing:
                continue
            tags = rs.get("tags") or []
            matched_asset = None
            for t in tags:
                if t.startswith("asset:"):
                    tag_val = t.split("asset:", 1)[1]
                    matched_asset = assets_by_tag.get(tag_val)
            if not matched_asset and assets_by_tag:
                matched_asset = next(iter(assets_by_tag.values()))
            if not matched_asset:
                continue

            summary = rs.get("summary") or {}
            snap_rec = SnapshotRecord(
                snapshot_id=full_id,
                short_id=rs.get("short_id", full_id[:8]),
                asset_id=matched_asset.id,
                repository_id=repo.id,
                hostname=rs.get("hostname", matched_asset.hostname_or_ip),
                paths_json=json.dumps(rs.get("paths") or []),
                tags_json=json.dumps(tags),
                size_bytes=int(summary.get("total_bytes_processed", 0)),
                file_count=int(summary.get("files_new", 0)) + int(summary.get("files_unmodified", 0)),
                is_verified=False,
            )
            db.add(snap_rec)
            synced_count += 1

    db.commit()
    return {"synced_new_snapshots": synced_count}


@router.get("/snapshots/{snapshot_id}/files")
def get_snapshot_file_tree(
    snapshot_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    snap = (
        db.query(SnapshotRecord)
        .filter((SnapshotRecord.snapshot_id == snapshot_id) | (SnapshotRecord.short_id == snapshot_id))
        .first()
    )
    if not snap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    repo = db.query(StorageRepository).filter(StorageRepository.id == snap.repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    files = list_snapshot_files(repo, snap.snapshot_id)
    return {
        "snapshot_id": snap.snapshot_id,
        "short_id": snap.short_id,
        "asset_tag": snap.asset.asset_tag if snap.asset else "UNKNOWN",
        "files": files,
    }


@router.get("/snapshots/{snapshot_id}/download")
def download_snapshot_zip(
    snapshot_id: str,
    path: str = Query("/"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    snap = (
        db.query(SnapshotRecord)
        .filter((SnapshotRecord.snapshot_id == snapshot_id) | (SnapshotRecord.short_id == snapshot_id))
        .first()
    )
    if not snap:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    repo = db.query(StorageRepository).filter(StorageRepository.id == snap.repository_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    try:
        zip_bytes = dump_snapshot_zip(repo, snap.snapshot_id, path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    filename = f"cfr_restore_{snap.asset.asset_tag if snap.asset else 'asset'}_{snap.short_id}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
