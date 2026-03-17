#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Helpers for safely rewriting text files."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable


def rewrite_text_file(path: str | Path, transform: Callable[[str], str]) -> None:
    """Rewrite a text file using a temporary file in the same directory."""
    file_path = Path(path)
    original_content = file_path.read_text(encoding="utf-8")
    updated_content = transform(original_content)

    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=file_path.parent,
        delete=False,
        suffix=file_path.suffix,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(updated_content)

    temp_path.replace(file_path)
