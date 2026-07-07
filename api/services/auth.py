"""JWT Auth utilities."""

from typing import Optional
import hashlib
import hmac
import json
import base64
import time

from config import settings


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def _sign(payload: dict, expires_minutes: int, token_type: str = "access") -> str:
    now = int(time.time())
    claims = {
        **payload,
        "iat": now,
        "exp": now + expires_minutes * 60,
        "type": token_type,
    }
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps(claims).encode())
    sig_input = f"{header}.{body}".encode()
    sig = _b64(hmac.new(settings.JWT_SECRET.encode(), sig_input, hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"


def create_access_token(user_id: int) -> str:
    return _sign({"sub": str(user_id)}, settings.JWT_ACCESS_EXPIRE_MINUTES, "access")


def create_refresh_token(user_id: int) -> str:
    return _sign({"sub": str(user_id)}, settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60, "refresh")


def decode_token(token: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        expected_sig = _b64(
            hmac.new(
                settings.JWT_SECRET.encode(),
                f"{header}.{body}".encode(),
                hashlib.sha256,
            ).digest()
        )
        if not hmac.compare_digest(sig, expected_sig):
            return None
        claims = json.loads(_unb64(body))
        if claims.get("exp", 0) < time.time():
            return None
        return claims
    except Exception:
        return None
