"""Ограниченная файловая очередь; реальные агенты подключаются явным submit.

Никаких сетевых вызовов, запуска CLI или фонового сервиса. Незавершённые
резервации после прерывания требуют решения координатора, а не повторного запроса.
"""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

STAGES = ("collect", "verify", "validate", "humanpacket", "metrics")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def immutable(path: Path, data: bytes) -> None:
    """Атомарная публикация полностью записанного файла без перезаписи."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".sfr-immutable-", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ValueError("Попытка перезаписи доказательства") from None
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)
