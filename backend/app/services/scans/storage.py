"""Opaque, private, per-user filesystem storage for sanitized scan photos."""

from __future__ import annotations

import os
import re
import shutil
import stat
import uuid
from pathlib import Path

from backend.app.core.config import PROJECT_ROOT, Settings

_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class PrivateScanStorage:
    """Keep photos outside public assets and derive paths only from server-owned IDs."""

    def __init__(self, directory: Path, max_bytes: int) -> None:
        configured = Path(directory).expanduser()
        self.root = (
            configured if configured.is_absolute() else PROJECT_ROOT / configured
        ).resolve()
        if self.root == Path(self.root.anchor):
            raise ValueError("Private scan storage must not be a filesystem root")
        self.max_bytes = max_bytes

    @classmethod
    def from_settings(cls, settings: Settings) -> PrivateScanStorage:
        """Build the filesystem adapter from validated application settings."""
        return cls(settings.private_scan_storage_dir, settings.scan_max_upload_bytes)

    def store(self, user_id: uuid.UUID, data: bytes) -> str:
        """Write a photo using an unguessable generated key and restrictive permissions."""
        if not data or len(data) > self.max_bytes:
            raise ValueError("Stored image does not fit configured limits")
        user_directory = self._user_directory(user_id, create=True)

        for _ in range(3):
            key = uuid.uuid4().hex
            target = user_directory / f"{key}.jpg"
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                descriptor = os.open(target, flags, 0o600)
            except FileExistsError:
                continue
            try:
                with os.fdopen(descriptor, "wb") as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                if os.name == "posix":
                    os.chmod(target, 0o600)
            except Exception:
                target.unlink(missing_ok=True)
                raise
            return key
        raise OSError("Could not allocate a private image key")

    def read(self, user_id: uuid.UUID, key: str) -> bytes:
        """Read only a generated regular file beneath the authenticated user's directory."""
        target = self._target(user_id, key, create_user_directory=False)
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(target, flags)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise OSError("Stored scan image is not a regular file")
            with os.fdopen(descriptor, "rb") as source:
                data = source.read(self.max_bytes + 1)
            if len(data) > self.max_bytes:
                raise OSError("Stored scan image exceeds the configured limit")
            return data
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    def exists(self, user_id: uuid.UUID, key: str | None) -> bool:
        """Check photo availability without following symbolic links."""
        if key is None:
            return False
        try:
            target = self._target(user_id, key, create_user_directory=False)
            return stat.S_ISREG(target.lstat().st_mode)
        except (FileNotFoundError, OSError, ValueError):
            return False

    def delete(self, user_id: uuid.UUID, key: str) -> None:
        """Remove one generated photo; a missing file or user directory is idempotent."""
        try:
            target = self._target(user_id, key, create_user_directory=False)
        except FileNotFoundError:
            return
        try:
            target.unlink(missing_ok=True)
        except FileNotFoundError:
            return
        directory = target.parent
        try:
            directory.rmdir()
        except OSError:
            pass

    def delete_user_images(self, user_id: uuid.UUID) -> None:
        """Remove the complete user-only directory, including orphaned scan files."""
        directory = self._user_directory(user_id, create=False)
        if directory is None:
            return
        if directory.is_symlink() or not directory.is_dir():
            raise OSError("Private user storage directory is not a regular directory")
        shutil.rmtree(directory)

    def _target(self, user_id: uuid.UUID, key: str, *, create_user_directory: bool) -> Path:
        if not _KEY_PATTERN.fullmatch(key):
            raise ValueError("Invalid private image key")
        directory = self._user_directory(user_id, create=create_user_directory)
        if directory is None:
            raise FileNotFoundError("Private user storage directory does not exist")
        return directory / f"{key}.jpg"

    def _user_directory(self, user_id: uuid.UUID, *, create: bool) -> Path | None:
        root = self.root
        if create:
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
            if os.name == "posix":
                os.chmod(root, 0o700)
        elif not root.exists():
            return None

        resolved_root = root.resolve(strict=True)
        if resolved_root == Path(resolved_root.anchor) or not resolved_root.is_dir():
            raise OSError("Private scan storage root is invalid")
        directory = resolved_root / str(user_id)
        if create:
            directory.mkdir(mode=0o700, exist_ok=True)
            if os.name == "posix":
                os.chmod(directory, 0o700)
        elif not directory.exists() and not directory.is_symlink():
            return None
        if directory.is_symlink():
            raise OSError("Private user storage directory cannot be a symbolic link")
        resolved_directory = directory.resolve(strict=True)
        if resolved_directory.parent != resolved_root or not resolved_directory.is_dir():
            raise OSError("Private user storage directory escaped its storage root")
        return resolved_directory
