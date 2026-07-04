#!/usr/bin/env python3
"""Stamp the ``data-abstract-page`` contract onto canonical Q315 pages.

Discovery, verification, inventory, and round-trip all key on the
``data-abstract-page="local:Q…"`` declaration carried by the ``<html>`` element
of a canonical page. Pages authored without it are invisible to the whole
pipeline even when they already carry complete ``hreflang`` alternates and
content bindings.

The page QID is not guessed: it is the stable identity already encoded in the
page's own path under ``Q315/``. A file named ``Q3027.html`` is page ``Q3027``;
``Q3062/index.html`` is the collection page ``Q3062``; the repository-root
``Q315/index.html`` is ``Q315``. This tool derives that identity, refuses any
ambiguity or collision, and writes the declaration without otherwise touching
the document. It never invents an identity for a path that does not already
encode one.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_REPO_ROOT

QID = re.compile(r"Q[1-9][0-9]*")
HTML_TAG = re.compile(r"<html\b([^>]*)>", re.IGNORECASE)
DECLARED = re.compile(r'data-abstract-page\s*=\s*"local:(Q[1-9][0-9]*)"')
ABSTRACT_VERSION = "1"


@dataclass(frozen=True)
class PageStamp:
    path: Path
    qid: str
    declared: str  # QID already declared on <html>, or "" if none


def page_qid_from_path(repo_root: Path, path: Path) -> str | None:
    """Return the page QID a Q315 path encodes, or ``None`` if it encodes none.

    ``Q315/index.html`` → ``Q315``; ``Q315/Q3062/index.html`` → ``Q3062``;
    ``Q315/Q3062/Q3027.html`` → ``Q3027``. A path whose file stem is not a QID
    and whose parent segment is not a QID does not encode an identity and is
    left for a human to author explicitly.
    """
    relative = path.relative_to(repo_root / "Q315")
    if QID.fullmatch(path.stem):
        return path.stem
    if path.name == "index.html":
        if relative.parent == Path("."):
            return "Q315"
        segment = relative.parent.name
        if QID.fullmatch(segment):
            return segment
    return None


def collect(repo_root: Path) -> tuple[list[PageStamp], list[str]]:
    directory = repo_root / "Q315"
    stamps: list[PageStamp] = []
    errors: list[str] = []
    by_qid: dict[str, Path] = {}
    for path in sorted(directory.rglob("*.html")):
        relative = path.relative_to(repo_root).as_posix()
        qid = page_qid_from_path(repo_root, path)
        if qid is None:
            errors.append(f"{relative}: path encodes no page QID; author it explicitly")
            continue
        raw = path.read_text(encoding="utf-8")
        match = HTML_TAG.search(raw)
        if not match:
            errors.append(f"{relative}: no <html> element")
            continue
        declared_match = DECLARED.search(match.group(1))
        declared = declared_match.group(1) if declared_match else ""
        if declared and declared != qid:
            errors.append(
                f"{relative}: declares {declared} but its path encodes {qid}"
            )
            continue
        previous = by_qid.get(qid)
        if previous is not None:
            errors.append(
                f"{relative}: page QID {qid} collides with "
                f"{previous.relative_to(repo_root).as_posix()}"
            )
            continue
        by_qid[qid] = path
        stamps.append(PageStamp(path=path, qid=qid, declared=declared))
    return stamps, errors


def stamp_html(raw: str, qid: str) -> str:
    match = HTML_TAG.search(raw)
    attributes = match.group(1)
    injected = f' data-abstract-page="local:{qid}" data-abstract-version="{ABSTRACT_VERSION}"'
    if "data-abstract-version" not in attributes:
        replacement = f"<html{attributes}{injected}>"
    else:
        replacement = f'<html{attributes} data-abstract-page="local:{qid}">'
    return raw[: match.start()] + replacement + raw[match.end() :]


def apply(repo_root: Path, check: bool) -> tuple[int, list[str]]:
    stamps, errors = collect(repo_root)
    pending = [stamp for stamp in stamps if not stamp.declared]
    if check or errors:
        return len(pending), errors
    for stamp in pending:
        raw = stamp.path.read_text(encoding="utf-8")
        stamp.path.write_text(stamp_html(raw, stamp.qid), encoding="utf-8")
    return len(pending), errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report pages missing the declaration without modifying them",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    pending, errors = apply(repo_root, args.check)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    if args.check:
        print(f"{pending} page(s) missing data-abstract-page")
        return 1 if pending else 0
    print(f"Stamped data-abstract-page on {pending} page(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
