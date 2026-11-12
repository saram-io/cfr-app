from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..audit import record_audit_event
from ..auth import create_access_token, get_current_user, verify_password
from ..database import get_db
from ..models import User
from ..schemas import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username, User.is_active == True).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(user)
    record_audit_event(
        db,
        actor_username=user.username,
        actor_role=user.role,
        action="USER_LOGIN",
        entity_type="User",
        entity_id=user.username,
        summary=f"User '{user.full_name}' ({user.role}) authenticated into CFR-App",
    )
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.get("/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    users = db.query(User).order_by(User.id.asc()).all()
    return [UserOut.model_validate(u) for u in users]
