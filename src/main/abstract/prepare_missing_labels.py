#!/usr/bin/env python3
"""Prepare missing multilingual labels for QIDs bound in canonical Q315 pages."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.prepare_missing_content import alternate_pages, page_sources
from abstract.prepare_travel_content import LANGUAGES, content_bindings, quote, slots

DEFAULT_DATA = DEFAULT_DATA_DIR
DEFAULT_TRANSLATIONS = HERE / "missing-label-translations.csv"
DEFAULT_QUICKSTATEMENTS = HERE / "missing-label-updates.quickstatements"
API = "https://jsamwrites.wikibase.cloud/w/api.php"
TRANSLATE = "https://translate.googleapis.com/translate_a/single"
TOKEN_LABEL = re.compile(r"M[A-F0-9]{12} abstract content")
ATOMIC_CONTENT_ITEMTYPE = "Q3185"
COMPOSED_RESULT_ITEMTYPES = frozenset({"Q3835", "Q3836"})


def clean_text(value: str) -> str:
    """Remove QuickStatements escape characters accidentally stored as text."""
    return value.replace(r"\"", '"').replace(r"\|", "|").strip()


def exported_labels(data_dir: Path) -> dict[str, dict[str, str]]:
    with (data_dir / "labels-wikibase.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        return {row["identifier"]: row for row in csv.DictReader(source)}


def bound_qids(repo_root: Path) -> set[str]:
    result = set()
    pattern = re.compile(r'data-(?:content|entity)="local:(Q[1-9][0-9]*)"')
    for path in (repo_root / "Q315").rglob("*.html"):
        result.update(pattern.findall(path.read_text(encoding="utf-8")))
    return result


def aligned_values(
    repo_root: Path, wanted: set[str]
) -> dict[str, dict[str, Counter[str]]]:
    result: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    for _, relative in page_sources(repo_root):
        abstract = repo_root / relative
        bindings = content_bindings(abstract)
        localized = [slots(path) for path in alternate_pages(repo_root, abstract)]
        for key, qid in bindings.items():
            if qid not in wanted:
                continue
            for language, values in zip(LANGUAGES, localized):
                value = values.get(key, "").strip()
                if value and not re.fullmatch(r"Q[1-9][0-9]*", value):
                    result[qid][language][value] += 1
    return result


def conservative_page_rows(
    repo_root: Path,
    wanted: set[str],
    exported: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return only rows belonging to pages with fully corroborated translations.

    Legacy localized text is accepted only when its structurally corresponding
    English slot exactly matches the exported English label. Temporary items
    and function-composed paragraph/sentence entities are intentionally left
    for their dedicated reconciliation pipelines.
    """
    candidates = []
    observations: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for page_qid, relative in page_sources(repo_root):
        abstract = repo_root / relative
        bindings = content_bindings(abstract)
        localized = {
            language: slots(path)
            for language, path in zip(
                LANGUAGES, alternate_pages(repo_root, abstract)
            )
        }
        affected = {
            qid
            for qid in bindings.values()
            if qid in wanted
            and exported.get(qid, {}).get("itemtype", "").strip()
            == ATOMIC_CONTENT_ITEMTYPE
        }
        if not affected:
            continue
        values_by_qid: dict[str, dict[str, str]] = {}
        reasons = set()
        for key, qid in bindings.items():
            if qid not in affected:
                continue
            authoritative = clean_text(exported.get(qid, {}).get("en", ""))
            values = {
                language: clean_text(localized[language].get(key, ""))
                for language in LANGUAGES
            }
            if not authoritative or TOKEN_LABEL.fullmatch(authoritative):
                reasons.add(f"{qid}: temporary or missing English label")
                continue
            if values["en"].casefold() != authoritative.casefold():
                reasons.add(f"{qid}: English slot does not match exported label")
                continue
            missing = [language for language, value in values.items() if not value]
            if missing:
                reasons.add(f"{qid}: empty slots for {','.join(missing)}")
                continue
            previous = values_by_qid.get(qid)
            if previous and previous != values:
                reasons.add(f"{qid}: conflicting occurrences within page")
                continue
            values_by_qid[qid] = values
            for language, value in values.items():
                observations[qid][language].add(value)
        candidates.append(
            {
                "page_qid": page_qid,
                "page": relative.as_posix(),
                "qids": affected,
                "values": values_by_qid,
                "reasons": reasons,
            }
        )

    conflicts = {
        qid
        for qid, languages in observations.items()
        if any(len(values) != 1 for values in languages.values())
    }
    accepted: dict[str, dict[str, str]] = {}
    report = []
    for candidate in candidates:
        reasons = set(candidate["reasons"])
        missing_qids = candidate["qids"] - candidate["values"].keys()
        reasons.update(f"{qid}: not corroborated" for qid in missing_qids)
        reasons.update(
            f"{qid}: conflicting values across pages"
            for qid in candidate["qids"] & conflicts
        )
        status = "deferred" if reasons else "ready"
        if status == "ready":
            for qid, values in candidate["values"].items():
                accepted[qid] = values
        report.append(
            {
                "page_qid": candidate["page_qid"],
                "page": candidate["page"],
                "status": status,
                "affected_qids": str(len(candidate["qids"])),
                "reason": "; ".join(sorted(reasons)),
            }
        )
    rows = [
        {"qid": qid, "temporary": "", **values}
        for qid, values in sorted(
            accepted.items(), key=lambda item: int(item[0][1:])
        )
    ]
    return rows, report


def claims(qids: set[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = defaultdict(dict)
    ordered = sorted(qids, key=lambda value: int(value[1:]))
    for start in range(0, len(ordered), 50):
        query = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(ordered[start : start + 50]),
                "props": "claims",
                "format": "json",
            }
        )
        request = urllib.request.Request(
            f"{API}?{query}", headers={"User-Agent": "Q315-label-reconciler/1.0"}
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            entities = json.load(response)["entities"]
        for qid, entity in entities.items():
            for claim in entity.get("claims", {}).get("P40", []):
                value = (
                    claim.get("mainsnak", {})
                    .get("datavalue", {})
                    .get("value", {})
                )
                language = value.get("language", "")
                text = clean_text(value.get("text", ""))
                if language in LANGUAGES and text:
                    result[qid].setdefault(language, text)
    return result


SEPARATOR = "\n|||Q315LABEL|||\n"


def translate_many(texts: list[str], target: str) -> list[str]:
    query = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "en",
            "tl": target,
            "dt": "t",
            "q": SEPARATOR.join(texts),
        }
    )
    request = urllib.request.Request(
        f"{TRANSLATE}?{query}",
        headers={"User-Agent": "Q315-label-reconciler/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.load(response)
    combined = "".join(part[0] for part in payload[0] if part and part[0])
    result = [value.strip() for value in combined.split(SEPARATOR.strip())]
    if len(result) != len(texts) or any(not value for value in result):
        if len(texts) == 1:
            raise ValueError(f"translation shape mismatch for {target}")
        midpoint = len(texts) // 2
        return translate_many(texts[:midpoint], target) + translate_many(
            texts[midpoint:], target
        )
    return result


def safe_label(qid: str, language: str, value: str) -> str:
    if qid == "Q7434" and language == "en":
        return "Queen — Reine"
    # A literal pipe is valid Wikibase text but conflicts with the
    # QuickStatements field separator. Labels are administrative display
    # terms; P40 retains the original content punctuation.
    value = value.replace(r"\|", "—").replace("|", "—")
    return value if len(value) <= 250 else value[:247] + "..."


def disambiguated_labels(
    rows: list[dict[str, str]], exported: dict[str, dict[str, str]]
) -> dict[tuple[str, str], str]:
    existing: dict[str, dict[str, set[str]]] = {
        language: defaultdict(set) for language in LANGUAGES
    }
    for qid, values in exported.items():
        for language in LANGUAGES:
            value = clean_text(values.get(language, ""))
            if value:
                existing[language][value.casefold()].add(qid)
    result = {}
    for language in LANGUAGES:
        proposed = Counter(
            safe_label(row["qid"], language, row[language]).casefold()
            for row in rows
        )
        for row in rows:
            qid = row["qid"]
            value = safe_label(qid, language, row[language])
            conflicts = existing[language].get(value.casefold(), set()) - {qid}
            if conflicts or proposed[value.casefold()] > 1:
                context = row["fr"] if language == "en" else row["en"]
                candidate = safe_label(qid, language, f"{value} — {context}")
                if (
                    existing[language].get(candidate.casefold(), set()) - {qid}
                    or sum(
                        safe_label(other["qid"], language, f"{safe_label(other['qid'], language, other[language])} — {other['fr'] if language == 'en' else other['en']}").casefold()
                        == candidate.casefold()
                        for other in rows
                    )
                    > 1
                ):
                    candidate = safe_label(qid, language, f"{value} — {qid}")
                value = candidate
            result[(qid, language)] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--translations", type=Path, default=DEFAULT_TRANSLATIONS)
    parser.add_argument("--quickstatements", type=Path, default=DEFAULT_QUICKSTATEMENTS)
    parser.add_argument(
        "--page-report",
        type=Path,
        default=HERE / "missing-label-page-status.csv",
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    labels = exported_labels(args.data_dir.resolve())
    qids = bound_qids(root)
    wanted = {
        qid
        for qid in qids
        if qid not in labels
        or TOKEN_LABEL.fullmatch(labels[qid].get("en", "").strip())
        or any(not labels[qid].get(language, "").strip() for language in LANGUAGES)
    }
    rows, page_report = conservative_page_rows(root, wanted, labels)
    p40 = claims({row["qid"] for row in rows})

    with args.page_report.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=("page_qid", "page", "status", "affected_qids", "reason"),
        )
        writer.writeheader()
        writer.writerows(page_report)

    with args.translations.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination, fieldnames=("qid", "temporary", *LANGUAGES)
        )
        writer.writeheader()
        writer.writerows(rows)

    labels_to_write = disambiguated_labels(rows, labels)
    blocks = []
    for row in rows:
        statements = []
        qid = row["qid"]
        exported = labels.get(qid, {})
        for language in LANGUAGES:
            value = row[language]
            if row["temporary"] or not exported.get(language, "").strip():
                statements.append(
                    f'{qid}|L{language}|"{quote(labels_to_write[(qid, language)])}"'
                )
            if (
                exported.get("itemtype", "").strip() == ATOMIC_CONTENT_ITEMTYPE
                and not p40.get(qid, {}).get(language, "")
            ):
                content_value = value.replace("|", "—")
                statements.append(
                    f'{qid}|P40|{language}:"{quote(content_value)}"'
                )
        if statements:
            blocks.append("\n".join(statements))
    args.quickstatements.write_text(
        "\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8"
    )
    print(
        f"Prepared {len(rows)} QIDs in {args.translations}; "
        f"{len(blocks)} update blocks in {args.quickstatements}; "
        f"page decisions in {args.page_report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
