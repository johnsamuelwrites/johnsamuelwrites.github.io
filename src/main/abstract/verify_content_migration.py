#!/usr/bin/env python3
"""Verify every discovered abstract page through the generic migration stages."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_REPO_ROOT
from abstract.discover_content_migration import discover
from abstract.prepare_missing_content import inventory, page_sources
from abstract.prepare_travel_content import LANGUAGES
from abstract.validate_abstract_html import validate
from abstract.verify_content_roundtrip import verify as verify_roundtrip

DEFAULT_REPORT = HERE / "content-migration-report.json"


def verify(
    repo_root: Path,
    data_dir: Path,
    page: str = "",
) -> tuple[dict, list[str]]:
    registry = discover(repo_root)
    abstract_rows = [
        row
        for row in registry
        if row["abstract_path"] and (not page or row["page_qid"] == page)
    ]
    if page and not abstract_rows:
        raise ValueError(f"no abstract page declares QID {page}")

    errors: list[str] = []
    page_reports = []
    for row in sorted(abstract_rows, key=lambda row: row["abstract_path"]):
        abstract_path = row["abstract_path"]
        missing_targets = [
            language
            for language in LANGUAGES
            if not row[f"target_{language}"]
            or not (repo_root / row[f"target_{language}"]).is_file()
        ]
        if missing_targets:
            errors.append(
                f"{abstract_path}: missing targets: {', '.join(missing_targets)}"
            )
        if row["render_ownership"] == "legacy":
            for language in ("en", "fr"):
                if not row[f"{language}_source"]:
                    errors.append(f"{abstract_path}: missing temporary {language} source")
        abstract_errors = validate(repo_root / abstract_path)
        errors.extend(abstract_errors)
        page_reports.append(
            {
                "page_qid": row["page_qid"],
                "abstract_path": abstract_path,
                "migration_state": row["migration_state"],
                "render_ownership": row["render_ownership"],
                "targets": {
                    language: row[f"target_{language}"] for language in LANGUAGES
                },
                "abstract_contract": "valid" if not abstract_errors else "invalid",
            }
        )

    content_rows = inventory(repo_root, data_dir, page_sources(repo_root, page))
    statuses = Counter(row["status"] for row in content_rows)
    unresolved = sum(
        count
        for status, count in statuses.items()
        if status in {
            "ambiguous-review",
            "existing-english-review",
            "missing-ready",
            "missing-translations",
        }
    )
    report = {
        "schema_version": 1,
        "pages": page_reports,
        "content_inventory": {
            "slots": len(content_rows),
            "statuses": dict(sorted(statuses.items())),
            "unresolved_slots": unresolved,
        },
        "structural_pipeline": "valid" if not errors else "invalid",
        "release_ready": not errors and unresolved == 0,
    }
    return report, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_REPO_ROOT.parent / "Q42761025" / "data",
    )
    parser.add_argument(
        "--page",
        default="",
        help="restrict verification to a single abstract page QID",
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--release-ready",
        action="store_true",
        help="also fail while reviewed/imported content work remains",
    )
    args = parser.parse_args()
    try:
        repo_root = args.repo_root.resolve()
        data_dir = args.data_dir.resolve()
        report, errors = verify(repo_root, data_dir, args.page)
        roundtrip = verify_roundtrip(
            repo_root, data_dir, page_sources(repo_root, args.page)
        )
        report["roundtrip_status"] = roundtrip["status"]
        report["roundtrip_mismatch_count"] = roundtrip["mismatch_count"]
        report["release_ready"] = (
            report["release_ready"] and roundtrip["status"] == "equivalent"
        )
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"Wrote {args.report}")
    print(
        f"Structural pipeline: {report['structural_pipeline']}; "
        f"unresolved content slots: "
        f"{report['content_inventory']['unresolved_slots']}; "
        f"round-trip: {report['roundtrip_status']}"
    )
    if errors or (args.release_ready and not report["release_ready"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
