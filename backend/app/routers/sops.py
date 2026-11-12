from datetime import datetime, timezone
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..audit import record_audit_event
from ..auth import get_current_user, require_roles, verify_esignature
from ..config import DOCS_DIR
from ..database import get_db
from ..models import SOPDocument, User
from ..schemas import SOPCreate, SOPOut

router = APIRouter(prefix="/sops", tags=["SOPs & Equipment Backup Guides"])


def _serialize_sop(sop: SOPDocument) -> SOPOut:
    return SOPOut(
        id=sop.id,
        sop_code=sop.sop_code,
        title=sop.title,
        version=sop.version,
        status=sop.status,
        target_rpo_hours=sop.target_rpo_hours,
        target_rto_hours=sop.target_rto_hours,
        drill_interval_days=sop.drill_interval_days,
        content_markdown=sop.content_markdown,
        checklist=json.loads(sop.checklist_json or "[]"),
        approved_by=sop.approved_by,
        approved_at=sop.approved_at,
        updated_at=sop.updated_at,
    )


@router.get("", response_model=List[SOPOut])
def list_sops(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    sops = db.query(SOPDocument).order_by(SOPDocument.id.asc()).all()
    return [_serialize_sop(s) for s in sops]


@router.post("", response_model=SOPOut, status_code=status.HTTP_201_CREATED)
def create_sop(
    payload: SOPCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "QA_Compliance", "Lab_Engineer")),
):
    existing = db.query(SOPDocument).filter(SOPDocument.sop_code == payload.sop_code).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SOP Code already exists")

    signer = current_user
    sig_verified = False
    sig_meaning = None
    reason = "SOP creation"
    approved_by = None
    approved_at = None

    if payload.status == "APPROVED":
        signer = verify_esignature(db, payload.esignature, required_roles=["Admin", "QA_Compliance"])
        sig_verified = True
        sig_meaning = payload.esignature.meaning
        reason = payload.esignature.reason
        approved_by = f"{signer.full_name} ({signer.username})"
        approved_at = datetime.now(timezone.utc)

    sop = SOPDocument(
        sop_code=payload.sop_code.strip().upper(),
        title=payload.title.strip(),
        version=payload.version,
        status=payload.status,
        target_rpo_hours=payload.target_rpo_hours,
        target_rto_hours=payload.target_rto_hours,
        drill_interval_days=payload.drill_interval_days,
        content_markdown=payload.content_markdown,
        checklist_json=json.dumps(payload.checklist),
        approved_by=approved_by,
        approved_at=approved_at,
    )
    db.add(sop)
    db.commit()
    db.refresh(sop)

    record_audit_event(
        db,
        actor_username=signer.username,
        actor_role=signer.role,
        action="SOP_CREATED",
        entity_type="SOPDocument",
        entity_id=sop.sop_code,
        summary=f"Created SOP '{sop.sop_code} v{sop.version}' ({sop.title}) [Status: {sop.status}]",
        new_value={"sop_code": sop.sop_code, "version": sop.version, "status": sop.status},
        reason=reason,
        signature_meaning=sig_meaning,
        signature_verified=sig_verified,
    )
    return _serialize_sop(sop)


@router.get("/guides")
def list_equipment_guides(_: User = Depends(get_current_user)):
    """Returns the complete Markdown equipment backup guidelines from /docs."""
    guides = []
    if DOCS_DIR.exists():
        for md_file in sorted(DOCS_DIR.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            first_line = content.splitlines()[0].lstrip("# ").strip() if content else md_file.stem
            guides.append(
                {
                    "slug": md_file.stem,
                    "filename": md_file.name,
                    "title": first_line,
                    "content_markdown": content,
                }
            )
    return guides
