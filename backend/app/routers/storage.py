from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..audit import record_audit_event
from ..auth import get_current_user, require_roles, verify_esignature
from ..config import decrypt_env_dict, encrypt_env_dict, encrypt_secret
from ..database import get_db
from ..models import StorageRepository, User
from ..restic_manager import check_repository, init_repository
from ..schemas import StorageRepoCreate, StorageRepoOut

router = APIRouter(prefix="/storage", tags=["Storage Repositories"])


def _serialize_repo(repo: StorageRepository) -> StorageRepoOut:
    env_dict = decrypt_env_dict(repo.encrypted_env_json)
    return StorageRepoOut(
        id=repo.id,
        name=repo.name,
        backend_type=repo.backend_type,
        repo_uri=repo.repo_uri,
        env_keys=list(env_dict.keys()),
        immutable_append_only=repo.immutable_append_only,
        is_initialized=repo.is_initialized,
        status=repo.status,
        last_check_output=repo.last_check_output,
        last_checked_at=repo.last_checked_at,
        notes=repo.notes,
        created_at=repo.created_at,
    )


@router.get("", response_model=List[StorageRepoOut])
def list_storage_repos(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    repos = db.query(StorageRepository).order_by(StorageRepository.id.asc()).all()
    return [_serialize_repo(r) for r in repos]


@router.post("", response_model=StorageRepoOut, status_code=status.HTTP_201_CREATED)
def create_storage_repo(
    payload: StorageRepoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Lab_Engineer")),
):
    existing = db.query(StorageRepository).filter(StorageRepository.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository name already exists")

    signer = current_user
    sig_verified = False
    sig_meaning = None
    reason = "Configured Restic storage backend"
    if payload.esignature:
        signer = verify_esignature(db, payload.esignature)
        sig_verified = True
        sig_meaning = payload.esignature.meaning
        reason = payload.esignature.reason

    repo = StorageRepository(
        name=payload.name.strip(),
        backend_type=payload.backend_type,
        repo_uri=payload.repo_uri.strip(),
        encrypted_password=encrypt_secret(payload.password),
        encrypted_env_json=encrypt_env_dict(payload.env_vars),
        immutable_append_only=payload.immutable_append_only,
        is_initialized=False,
        status="UNINITIALIZED",
        notes=payload.notes,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    if payload.initialize_now:
        ok, msg = init_repository(repo)
        repo.is_initialized = ok
        repo.status = "HEALTHY" if ok else "UNINITIALIZED"
        repo.last_check_output = msg
        repo.last_checked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(repo)

    record_audit_event(
        db,
        actor_username=signer.username,
        actor_role=signer.role,
        action="STORAGE_REPO_CREATED",
        entity_type="StorageRepository",
        entity_id=repo.name,
        summary=f"Created Restic repository '{repo.name}' ({repo.backend_type} -> {repo.repo_uri})",
        new_value={
            "name": repo.name,
            "backend_type": repo.backend_type,
            "repo_uri": repo.repo_uri,
            "immutable_append_only": repo.immutable_append_only,
            "status": repo.status,
        },
        reason=reason,
        signature_meaning=sig_meaning,
        signature_verified=sig_verified,
    )
    return _serialize_repo(repo)


@router.post("/{repo_id}/init", response_model=StorageRepoOut)
def initialize_repo_endpoint(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Lab_Engineer")),
):
    repo = db.query(StorageRepository).filter(StorageRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    ok, msg = init_repository(repo)
    repo.is_initialized = ok
    repo.status = "HEALTHY" if ok else "ERROR"
    repo.last_check_output = msg
    repo.last_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(repo)

    record_audit_event(
        db,
        actor_username=current_user.username,
        actor_role=current_user.role,
        action="STORAGE_REPO_INIT",
        entity_type="StorageRepository",
        entity_id=repo.name,
        summary=f"Initialized Restic repository '{repo.name}': {'SUCCESS' if ok else 'ERROR'}",
        new_value={"status": repo.status, "output": msg[:500]},
    )
    return _serialize_repo(repo)


@router.post("/{repo_id}/check", response_model=StorageRepoOut)
def check_repo_integrity_endpoint(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "QA_Compliance", "Lab_Engineer")),
):
    repo = db.query(StorageRepository).filter(StorageRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    ok, msg = check_repository(repo)
    repo.status = "HEALTHY" if ok else "ERROR"
    if ok:
        repo.is_initialized = True
    repo.last_check_output = msg
    repo.last_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(repo)

    record_audit_event(
        db,
        actor_username=current_user.username,
        actor_role=current_user.role,
        action="STORAGE_REPO_CHECK",
        entity_type="StorageRepository",
        entity_id=repo.name,
        summary=f"Executed 'restic check' on repository '{repo.name}': {'PASSED' if ok else 'FAILED'}",
        new_value={"status": repo.status, "output": msg[:500]},
    )
    return _serialize_repo(repo)
