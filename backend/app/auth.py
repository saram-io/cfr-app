from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .config import JWT_ALGORITHM, JWT_SECRET_KEY
from .database import get_db
from .models import User
from .schemas import ElectronicSignatureInput

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = "cfr-part11-salt-v1"
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    if not stored_hash or not stored_hash.startswith("pbkdf2_sha256$"):
        return False
    parts = stored_hash.split("$")
    if len(parts) != 3:
        return False
    salt = parts[1]
    expected_hex = parts[2]
    dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return hmac.compare_digest(dk.hex(), expected_hex)


def create_access_token(user: User, expires_hours: int = 24) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    payload = {
        "sub": user.username,
        "role": user.role,
        "full_name": user.full_name,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_roles(*allowed_roles: str):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorized. Required: {', '.join(allowed_roles)}",
            )
        return current_user

    return dependency


def verify_esignature(
    db: Session,
    esig: Optional[ElectronicSignatureInput],
    required_roles: Optional[list[str]] = None,
) -> User:
    """Validates a 21 CFR Part 11 Electronic Signature (username + password re-authentication + meaning + reason)."""
    if not esig:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="21 CFR Part 11 Electronic Signature is required for this GMP operation.",
        )
    signer = db.query(User).filter(User.username == esig.username, User.is_active == True).first()
    if not signer or not verify_password(esig.password, signer.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Electronic Signature authentication failed: invalid username or password.",
        )
    if required_roles and signer.role not in required_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Electronic Signature user '{signer.username}' ({signer.role}) lacks required role: {required_roles}",
        )
    if not esig.reason or len(esig.reason.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Electronic Signature requires a meaningful reason for change (at least 3 characters).",
        )
    return signer
