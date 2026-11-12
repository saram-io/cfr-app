import base64
import hashlib
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
DOCS_DIR = Path(os.getenv("DOCS_DIR", str(BASE_DIR.parent / "docs"))).resolve()

DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "repos").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "sample_instruments").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "restores").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "landing_zones").mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'cfr_app.db'}")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "cfr-part11-default-jwt-secret-key-2026")
JWT_ALGORITHM = "HS256"
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://localhost:8080/api/v1")
RESTIC_REST_SERVER_URL = os.getenv("RESTIC_REST_SERVER_URL", "http://restic-server:8000")
RESTIC_DEFAULT_REPO_PASSWORD = os.getenv("RESTIC_DEFAULT_REPO_PASSWORD", "gmp-restic-repo-default-password")


def _get_fernet() -> Fernet:
    raw_key = os.getenv("MASTER_ENCRYPTION_KEY", "")
    if raw_key:
        try:
            return Fernet(raw_key.encode("utf-8"))
        except Exception:
            pass
    derived = base64.urlsafe_b64encode(hashlib.sha256(JWT_SECRET_KEY.encode("utf-8")).digest())
    return Fernet(derived)


FERNET = _get_fernet()


def encrypt_secret(plain_text: str) -> str:
    if not plain_text:
        return ""
    return FERNET.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    try:
        return FERNET.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def encrypt_env_dict(env_dict: dict) -> str:
    if not env_dict:
        return encrypt_secret("{}")
    return encrypt_secret(json.dumps(env_dict))


def decrypt_env_dict(cipher_text: str) -> dict:
    raw = decrypt_secret(cipher_text)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}
