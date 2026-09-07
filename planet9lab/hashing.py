from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: str | Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def object_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return sha256_bytes(payload)


def collect_hashes(paths: dict[str, str | Path], objects: dict[str, Any] | None = None) -> dict[str, str]:
    hashes = {name: file_hash(path) for name, path in paths.items()}
    for name, value in (objects or {}).items():
        hashes[name] = object_hash(value)
    return hashes
