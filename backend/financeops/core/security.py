from __future__ import annotations

import base64
import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import bcrypt as _bcrypt
import pyotp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt

from financeops.config import settings
from financeops.core.exceptions import AuthenticationError

log = logging.getLogger(__name__)

_NONCE_SIZE = 12  # 96-bit nonce for AES-256-GCM
_TOTP_ISSUER = "FinanceOps"


def _normalize_password(password: str) -> bytes:
    """SHA-256 pre-hash → 64-byte hex digest, safely under bcrypt's 72-byte limit."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt (SHA-256 pre-hashed)."""
    return _bcrypt.hashpw(_normalize_password(password), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return _bcrypt.checkpw(_normalize_password(plain), hashed.encode("utf-8"))
    except ValueError:
        log.warning("Stored password hash is invalid and could not be verified")
        return False


def _make_token(payload: dict, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {**payload, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    additional_claims: dict | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token (15 minutes by default)."""
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "type": "access",
    }
    if additional_claims:
        payload.update(additional_claims)
    return _make_token(
        payload,
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    """Create a JWT refresh token (7 days by default)."""
    return _make_token(
        {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "type": "refresh",
            "jti": str(uuid.uuid4()),
        },
        timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    Raises AuthenticationError on invalid or expired token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        log.debug("JWT decode failed: %s", exc)
        raise AuthenticationError("Invalid or expired token") from exc


def generate_totp_secret() -> str:
    """Generate a base32 TOTP secret compatible with common authenticator apps."""
    return pyotp.random_base32().strip().replace(" ", "").upper()


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code against a secret. Allows 1-step drift."""
    normalized_secret = str(secret).strip().replace(" ", "").upper()
    normalized_code = "".join(ch for ch in str(code).strip() if ch.isdigit())
    if not normalized_secret or len(normalized_code) != 6:
        return False
    totp = pyotp.TOTP(normalized_secret)
    return totp.verify(normalized_code, valid_window=1)


def get_totp_uri(secret: str, email: str) -> str:
    """Return the canonical otpauth:// URI for QR code generation."""
    normalized_secret = str(secret).strip().replace(" ", "").upper()
    normalized_email = str(email).strip().lower()
    encoded_issuer = quote(_TOTP_ISSUER, safe="")
    encoded_email = quote(normalized_email, safe="")
    return (
        f"otpauth://totp/{encoded_issuer}:{encoded_email}"
        f"?secret={normalized_secret}&issuer={encoded_issuer}"
    )


def _get_aes_key() -> bytes:
    """Decode the base64-encoded AES-256 key from settings (URL-safe base64)."""
    return base64.urlsafe_b64decode(settings.FIELD_ENCRYPTION_KEY)


def encrypt_field(plaintext: str) -> str:
    """
    Encrypt a string field using AES-256-GCM.
    Returns: base64(nonce + ciphertext_with_tag)
    """
    key = _get_aes_key()
    nonce = os.urandom(_NONCE_SIZE)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_field(ciphertext_b64: str) -> str:
    """
    Decrypt a base64-encoded AES-256-GCM ciphertext.
    Expects: base64(nonce + ciphertext_with_tag)
    """
    key = _get_aes_key()
    raw = base64.b64decode(ciphertext_b64)
    nonce = raw[:_NONCE_SIZE]
    ciphertext = raw[_NONCE_SIZE:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
