"""Password hashing and JWT access tokens."""

from __future__ import annotations

import datetime as dt
from typing import Any

import bcrypt
import jwt

from .config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = dt.timedelta(days=7)


def _to_bytes(password: str) -> bytes:
    # bcrypt only considers the first 72 bytes; truncate defensively.
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(password), hashed.encode("ascii"))
    except ValueError:
        return False


def create_access_token(subject: str, **claims: Any) -> str:
    now = dt.datetime.now(tz=dt.timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
        **claims,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
