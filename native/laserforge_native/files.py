"""Filesystem adapter independent of Qt. Project contents remain opaque core bytes."""
from pathlib import Path
import os
import tempfile

MAX_FILE = 64 * 1024 * 1024


def read_project(path: str | Path) -> bytes:
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError("File exceeds the native preview's 64 MiB input limit. Use the legacy app for larger files.")
    return data


def atomic_write(path: str | Path, data: bytes):
    """Same-filesystem atomic replacement; failures leave the previous project intact."""
    destination = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
