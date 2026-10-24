"""Storage service: filesystem-backed content storage.

The interface is designed so an S3-compatible backend can replace the local
filesystem without changing business logic. ``content_path`` resolves a file
record's storage location safely (no traversal).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import aiofiles

from app.core.config import settings


class StorageBackend:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def new_storage_id(self) -> str:
        return uuid.uuid4().hex

    def relative_path(self, storage_id: str) -> str:
        # Shard by first two hex chars to avoid huge directories.
        return os.path.join(storage_id[:2], storage_id[2:])

    def resolve(self, storage_path: str) -> Path:
        # Guard against traversal: resolve must stay within root.
        candidate = (self.root / storage_path).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("invalid storage path")
        return candidate

    async def write(self, storage_path: str, data: bytes) -> int:
        path = self.resolve(storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as fh:
            await fh.write(data)
        return len(data)

    async def write_stream(self, storage_path: str, stream) -> int:
        """Stream an async chunked upload to disk, returning bytes written."""
        path = self.resolve(storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        async with aiofiles.open(path, "wb") as fh:
            async for chunk in stream:
                await fh.write(chunk)
                total += len(chunk)
        return total

    async def read(self, storage_path: str) -> bytes:
        path = self.resolve(storage_path)
        async with aiofiles.open(path, "rb") as fh:
            return await fh.read()

    def open_path(self, storage_path: str) -> Path:
        return self.resolve(storage_path)

    def delete(self, storage_path: str) -> None:
        path = self.resolve(storage_path)
        try:
            path.unlink()
        except FileNotFoundError:
            pass


storage = StorageBackend(settings.storage_path)
