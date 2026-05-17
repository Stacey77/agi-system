from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class KeyRole(str, Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


@dataclass
class ApiKey:
    key_id: str
    hashed_key: str
    name: str
    role: KeyRole
    created_at: float
    active: bool = True


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class KeyStore:
    def __init__(self) -> None:
        self._keys: Dict[str, ApiKey] = {}
        self._hash_index: Dict[str, str] = {}
        self._load_from_env()

    def _load_from_env(self) -> None:
        raw_list = os.getenv("API_KEYS")
        if raw_list:
            try:
                entries = json.loads(raw_list)
                for entry in entries:
                    raw_key = entry["key"]
                    name = entry.get("name", "env-key")
                    role = KeyRole(entry.get("role", "admin"))
                    self._store(raw_key, name, role)
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

        single_key = os.getenv("API_KEY")
        if single_key and single_key not in {k.hashed_key for k in self._keys.values()}:
            h = _hash(single_key)
            already = any(ak.hashed_key == h for ak in self._keys.values())
            if not already:
                self._store(single_key, "default", KeyRole.ADMIN)

    def _store(self, raw_key: str, name: str, role: KeyRole) -> ApiKey:
        h = _hash(raw_key)
        key_id = secrets.token_hex(8)
        api_key = ApiKey(
            key_id=key_id,
            hashed_key=h,
            name=name,
            role=role,
            created_at=time.time(),
        )
        self._keys[key_id] = api_key
        self._hash_index[h] = key_id
        return api_key

    def create_key(self, name: str, role: KeyRole) -> Tuple[str, ApiKey]:
        raw_key = f"sk-{secrets.token_hex(32)}"
        api_key = self._store(raw_key, name, role)
        return raw_key, api_key

    def validate_key(self, raw_key: str) -> Optional[ApiKey]:
        h = _hash(raw_key)
        key_id = self._hash_index.get(h)
        if key_id is None:
            return None
        api_key = self._keys.get(key_id)
        if api_key is None or not api_key.active:
            return None
        return api_key

    def revoke_key(self, key_id: str) -> bool:
        api_key = self._keys.get(key_id)
        if api_key is None:
            return False
        api_key.active = False
        return True

    def list_keys(self) -> List[ApiKey]:
        return list(self._keys.values())
