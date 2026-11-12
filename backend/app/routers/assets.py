import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from ..agent_templates import generate_agent_bundle
from ..audit import record_audit_event
from ..auth import get_current_user, require_roles, verify_esignature
from ..compliance import compute_asset_compliance
from ..database import get_db
from ..models import Asset, User
from ..schemas import AssetCreate, AssetOut, AssetUpdate

router = APIRouter(prefix="/assets", tags=["Life Science Assets"])


def _serialize_asset(asset: Asset) -> AssetOut:
    comp = compute_asset_compliance(asset)
    return AssetOut(
        id=asset.id,
        asset_tag=asset.asset_tag,
        name=asset.name,
        category=asset.category,
        vendor=asset.vendor,
        model=asset.model,
        serial_number=asset.serial_number,
        software_version=asset.software_version,
        location=asset.location,
        hostname_or_ip=asset.hostname_or_ip,
        os_type=asset.os_type,
        is_gmp=asset.is_gmp,
        criticality=asset.criticality,
        system_owner=asset.system_owner,
        qa_owner=asset.qa_owner,
        sop_id=asset.sop_id,
        sop_code=asset.sop.sop_code if asset.sop else None,
        agent_token=asset.agent_token,
        agent_last_seen_at=asset.agent_last_seen_at,
        notes=asset.notes,
        policy_id=asset.policy.id if asset.policy else None,
        policy_schedule=f"{asset.policy.schedule_preset} ({asset.policy.schedule_cron})" if asset.policy else None,
        repository_name=asset.policy.repository.name if (asset.policy and asset.policy.repository) else None,
        compliance=comp,
        created_at=asset.created_at,
    )


@router.get("", response_model=List[AssetOut])
def list_assets(
    is_gmp: Optional[bool] = Query(None),
    criticality: Optional[str] = Query(None),
    compliance_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Asset)
    if is_gmp is not None:
        query = query.filter(Asset.is_gmp == is_gmp)
    if criticality:
        query = query.filter(Asset.criticality == criticality.upper())

    assets = query.order_by(Asset.id.asc()).all()
    results = []
    for asset in assets:
        if search:
            q = search.lower()
            haystack = f"{asset.asset_tag} {asset.name} {asset.vendor} {asset.model} {asset.location} {asset.category}".lower()
            if q not in haystack:
                continue
        serialized = _serialize_asset(asset)
        if compliance_status and serialized.compliance.overall_status != compliance_status.upper():
            continue
        results.append(serialized)
    return results


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return _serialize_asset(asset)


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "QA_Compliance", "Lab_Engineer")),
):
    existing = db.query(Asset).filter(Asset.asset_tag == payload.asset_tag).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Asset tag '{payload.asset_tag}' already exists")

    signer = current_user
    sig_verified = False
    sig_meaning = None
    reason = "Initial asset registration"

    if payload.is_gmp or payload.criticality.upper() == "CRITICAL":
        if payload.esignature:
            signer = verify_esignature(db, payload.esignature)
            sig_verified = True
            sig_meaning = payload.esignature.meaning
            reason = payload.esignature.reason

    token = f"cfr_agt_{payload.asset_tag.lower().replace('-', '_')}_{secrets.token_hex(8)}"
    asset = Asset(
        asset_tag=payload.asset_tag.strip().upper(),
        name=payload.name.strip(),
        category=payload.category,
        vendor=payload.vendor,
        model=payload.model,
        serial_number=payload.serial_number,
        software_version=payload.software_version,
        location=payload.location,
        hostname_or_ip=payload.hostname_or_ip,
        os_type=payload.os_type,
        is_gmp=payload.is_gmp,
        criticality=payload.criticality.upper(),
        system_owner=payload.system_owner,
        qa_owner=payload.qa_owner,
        sop_id=payload.sop_id,
        agent_token=token,
        notes=payload.notes,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    record_audit_event(
        db,
        actor_username=signer.username,
        actor_role=signer.role,
        action="ASSET_REGISTERED",
        entity_type="Asset",
        entity_id=asset.asset_tag,
        summary=f"Registered {'GMP' if asset.is_gmp else 'Non-GMP'} {asset.criticality} asset '{asset.name}' ({asset.asset_tag})",
        new_value={
            "asset_tag": asset.asset_tag,
            "name": asset.name,
            "is_gmp": asset.is_gmp,
            "criticality": asset.criticality,
            "os_type": asset.os_type,
        },
        reason=reason,
        signature_meaning=sig_meaning,
        signature_verified=sig_verified,
    )
    return _serialize_asset(asset)


@router.put("/{asset_id}", response_model=AssetOut)
def update_asset(
    asset_id: int,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "QA_Compliance", "Lab_Engineer")),
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    old_snapshot = {
        "name": asset.name,
        "is_gmp": asset.is_gmp,
        "criticality": asset.criticality,
        "os_type": asset.os_type,
        "sop_id": asset.sop_id,
        "location": asset.location,
    }

    # Changing GMP status or Criticality on a regulated asset requires 21 CFR Part 11 E-Signature
    changing_gmp_or_crit = (
        (payload.is_gmp is not None and payload.is_gmp != asset.is_gmp)
        or (payload.criticality is not None and payload.criticality.upper() != asset.criticality)
    )
    requires_esig = asset.is_gmp or asset.criticality == "CRITICAL" or changing_gmp_or_crit

    signer = current_user
    sig_verified = False
    sig_meaning = None
    reason = "Asset metadata update"

    if requires_esig:
        signer = verify_esignature(db, payload.esignature)
        sig_verified = True
        sig_meaning = payload.esignature.meaning
        reason = payload.esignature.reason

    update_fields = payload.model_dump(exclude={"esignature"}, exclude_unset=True)
    for k, v in update_fields.items():
        if k == "criticality" and v is not None:
            v = v.upper()
        setattr(asset, k, v)

    db.commit()
    db.refresh(asset)

    new_snapshot = {
        "name": asset.name,
        "is_gmp": asset.is_gmp,
        "criticality": asset.criticality,
        "os_type": asset.os_type,
        "sop_id": asset.sop_id,
        "location": asset.location,
    }

    record_audit_event(
        db,
        actor_username=signer.username,
        actor_role=signer.role,
        action="ASSET_UPDATED",
        entity_type="Asset",
        entity_id=asset.asset_tag,
        summary=f"Updated asset '{asset.asset_tag}' (GMP={asset.is_gmp}, Criticality={asset.criticality})",
        old_value=old_snapshot,
        new_value=new_snapshot,
        reason=reason,
        signature_meaning=sig_meaning,
        signature_verified=sig_verified,
    )
    return _serialize_asset(asset)


@router.get("/{asset_id}/agent-bundle")
def get_asset_agent_bundle(
    asset_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    policy = asset.policy
    repo = policy.repository if policy else None
    return generate_agent_bundle(asset, policy, repo)
