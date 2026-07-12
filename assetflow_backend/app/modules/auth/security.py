from __future__ import annotations

import hmac
import json
import base64
import hashlib
from typing import Any, Protocol
from datetime import UTC, datetime, timedelta

from app.core.config import settings


class _PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, hash: str) -> bool: ...


try:
    from pwdlib import PasswordHash

    _password_hasher: _PasswordHasher = PasswordHash.recommended()
except ImportError:  # pragma: no cover - optional dependency fallback
    try:
        from passlib.hash import argon2

        _password_hasher = argon2
    except ImportError as exc:  # pragma: no cover - explicit runtime guard
        raise ImportError(
            "Install pwdlib or passlib[argon2] to enable password hashing."
        ) from exc


_JWT_HASH_ALGORITHMS: dict[str, Any] = {
    "HS256": hashlib.sha256,
    "HS384": hashlib.sha384,
    "HS512": hashlib.sha512,
}


class JWTError(ValueError):
    """Raised when a JWT is invalid or cannot be processed."""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


def _json_dumps(data: dict[str, Any]) -> bytes:
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _json_loads(data: bytes) -> dict[str, Any]:
    loaded = json.loads(data)
    if not isinstance(loaded, dict):
        raise JWTError("JWT payload must be a JSON object.")
    return loaded


def _hash_algorithm() -> Any:
    try:
        return _JWT_HASH_ALGORITHMS[settings.algorithm]
    except KeyError as exc:
        supported = ", ".join(sorted(_JWT_HASH_ALGORITHMS))
        raise JWTError(
            f"Unsupported JWT algorithm: {settings.algorithm}. Supported: {supported}"
        ) from exc


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bool(_password_hasher.verify(plain_password, hashed_password))


def hash_password(password: str) -> str:
    return str(_password_hasher.hash(password))


def create_access_token(
    subject: str | None = None,
    expires_delta: timedelta | None = None,
    **additional_claims: Any,
) -> str:
    now = datetime.now(tz=UTC)
    expire = now + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )

    payload: dict[str, Any] = {
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        **additional_claims,
    }
    if subject is not None:
        payload["sub"] = subject

    header = {"alg": settings.algorithm, "typ": "JWT"}
    header_segment = _b64url_encode(_json_dumps(header))
    payload_segment = _b64url_encode(_json_dumps(payload))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")

    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        signing_input,
        _hash_algorithm(),
    ).digest()

    return f"{header_segment}.{payload_segment}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".", maxsplit=2)
    except ValueError as exc:
        raise JWTError("Invalid JWT structure.") from exc

    header = _json_loads(_b64url_decode(header_segment))
    if header.get("typ") != "JWT":
        raise JWTError("Invalid JWT type.")

    if header.get("alg") != settings.algorithm:
        raise JWTError("JWT algorithm mismatch.")

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        signing_input,
        _hash_algorithm(),
    ).digest()

    if not hmac.compare_digest(signature_segment, _b64url_encode(expected_signature)):
        raise JWTError("Invalid JWT signature.")

    payload = _json_loads(_b64url_decode(payload_segment))
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise JWTError("JWT expiration claim is missing or invalid.")
    if datetime.now(tz=UTC).timestamp() >= exp:
        raise JWTError("JWT has expired.")

    return payload