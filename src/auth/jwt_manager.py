from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


class JWTManager:
    def __init__(self, secret: str, expiry_seconds: int = 3600) -> None:
        self._secret = secret.encode()
        self._expiry_seconds = expiry_seconds

    def create_token(self, key_id: str, name: str, role: str) -> str:
        header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
        now = int(time.time())
        payload = _b64encode(
            json.dumps(
                {"sub": key_id, "name": name, "role": role, "iat": now, "exp": now + self._expiry_seconds},
                separators=(",", ":"),
            ).encode()
        )
        signing_input = f"{header}.{payload}".encode()
        sig = _b64encode(hmac.new(self._secret, signing_input, hashlib.sha256).digest())
        return f"{header}.{payload}.{sig}"

    def verify_token(self, token: str) -> Optional[dict]:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header_b64, payload_b64, sig_b64 = parts
            signing_input = f"{header_b64}.{payload_b64}".encode()
            expected_sig = _b64encode(hmac.new(self._secret, signing_input, hashlib.sha256).digest())
            if not hmac.compare_digest(expected_sig, sig_b64):
                return None
            payload = json.loads(_b64decode(payload_b64))
            if int(time.time()) > payload.get("exp", 0):
                return None
            return payload
        except Exception:
            return None
