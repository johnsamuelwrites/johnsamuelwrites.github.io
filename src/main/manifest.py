#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Incremental build manifest helpers for static-site generators."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from paths import REPO_ROOT

DEFAULT_MANIFEST_PATH = REPO_ROOT / "analysis" / "build-manifest.json"


def _as_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (REPO_ROOT / candidate).resolve()


def hash_file(path: str | Path) -> str:
    """Return the SHA-256 digest for a file."""
    file_path = _as_path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_paths(paths: Iterable[str | Path], extra: str = "") -> str:
    """Create a stable fingerprint for a set of source files."""
    digest = hashlib.sha256()
    for path in sorted({_as_path(path) for path in paths}, key=lambda item: str(item)):
        digest.update(str(path.relative_to(REPO_ROOT)).encode("utf-8", errors="replace"))
        if path.exists() and path.is_file():
            digest.update(hash_file(path).encode("ascii"))
        else:
            digest.update(b"<missing>")
    digest.update(extra.encode("utf-8", errors="replace"))
    return digest.hexdigest()


class BuildManifest:
    """Track source fingerprints for generated artifacts."""

    def __init__(self, manifest_path: str | Path = DEFAULT_MANIFEST_PATH):
        self.manifest_path = _as_path(manifest_path)
        self.data = self._load()

    def _load(self) -> dict:
        if not self.manifest_path.exists():
            return {"entries": {}}
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"entries": {}}

    def _save(self) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(self.data, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def is_current(
        self,
        name: str,
        sources: Iterable[str | Path],
        outputs: Iterable[str | Path],
        extra: str = "",
    ) -> bool:
        """Return True when outputs exist and the recorded fingerprint matches."""
        entry = self.data.get("entries", {}).get(name)
        if entry is None:
            return False
        output_paths = [_as_path(path) for path in outputs]
        if not output_paths or any(not path.exists() for path in output_paths):
            return False
        return entry.get("fingerprint") == fingerprint_paths(sources, extra=extra)

    def update(
        self,
        name: str,
        sources: Iterable[str | Path],
        outputs: Iterable[str | Path],
        extra: str = "",
    ) -> None:
        """Record the current state for a build step."""
        entry = {
            "fingerprint": fingerprint_paths(sources, extra=extra),
            "outputs": [
                str(_as_path(path).relative_to(REPO_ROOT)).replace("\\", "/")
                for path in outputs
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.data.setdefault("entries", {})[name] = entry
        self._save()
