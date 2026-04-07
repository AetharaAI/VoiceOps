import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str, tenant_id: str, role: str, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode: dict[str, Any] = {
        'sub': subject,
        'tenant_id': tenant_id,
        'role': role,
        'exp': expire,
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def password_fingerprint(hashed_password: str) -> str:
    return hashlib.sha256(hashed_password.encode('utf-8')).hexdigest()


def create_password_reset_token(
    *,
    subject: str,
    tenant_id: str,
    email: str,
    password_fingerprint_value: str,
    expires_minutes: int,
) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode: dict[str, Any] = {
        'sub': subject,
        'tenant_id': tenant_id,
        'email': email,
        'scope': 'password_reset',
        'pwdv': password_fingerprint_value,
        'exp': expire,
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
