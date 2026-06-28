#
# SPDX-FileCopyrightText: 2026 John Samuel <johnsamuelwrites@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Generate QuickStatements for site pages missing from a Wikibase export."""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from config import SITE_URL, SUPPORTED_LANGUAGES
from paths import REPO_ROOT
from site_text import strip_author_from_title

WEB_PAGE = "Q45"
HTML = "Q1041"
CREATOR = "Q38"

# Language items observed in the current Wikibase instance. Unknown languages are
# deliberately reviewed instead of receiving an incorrect P17 statement.
LANGUAGE_ITEMS = {
    "en": "Q48",
    "fr": "Q49",
    "ml": "Q36",
    "pa": "Q50",
    "hi": "Q51",
    "it": "Q1763",
    "pt": "Q1764",
    "es": "Q1765",
}

TRAVEL_DIRECTORIES = {
    "travel",
    "travels",
    "voyage",
    "voyages",
    "viaje",
    "viajes",
    "viaggio",
    "viaggi",
    "viagem",
    "viagens",
    "यात्रा",
    "ਯਾਤਰਾ",
    "യാത്രകൾ",
}
TEACHING_DIRECTORIES = {
    "teaching",
    "enseignement",
    "अध्यापन",
    "ਅਧਿਆਪਨ",
    "അദ്ധ്യാപനം",
}
REFERENCE_DIRECTORIES = {"reference", "references", "référence", "références"}


@dataclass(frozen=True)
class FormInference:
    item: str | None
    label: str
    rule: str


@dataclass(frozen=True)
class Page:
    path: Path
    language: str
    title: str
    url: str
    created: int
    form: FormInference


def normalize_url(value: str) -> str:
    """Return a stable, percent-encoded URL for comparisons."""
    parts = urlsplit(value.strip())
    path = quote(unquote(parts.path), safe="/:@-._~!$&'()*+,;=")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def quickstatements_quote(value: str) -> str:
    """Escape a string for QuickStatements quoted-string syntax."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def read_existing_urls(csv_path: Path) -> set[str]:
    """Read existing page URLs from a query.csv-style export."""
    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or "url" not in reader.fieldnames:
            raise ValueError(f"{csv_path} must contain a 'url' column")
        return {
            normalize_url(row["url"])
            for row in reader
            if row.get("url", "").strip()
        }


def read_form_types(csv_path: Path) -> dict[str, str]:
    """Read creative-form labels and Q identifiers."""
    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not {"form", "label"} <= set(reader.fieldnames):
            raise ValueError(f"{csv_path} must contain 'form' and 'label' columns")
        return {
            row["label"].strip().casefold(): row["form"].rstrip("/").split("/")[-1]
            for row in reader
            if row.get("form") and row.get("label")
        }


def git_creation_dates(repo_root: Path) -> dict[str, int]:
    """Get each tracked HTML file's earliest commit timestamp in one Git pass."""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "-c",
            "core.quotepath=false",
            "log",
            "--format=--%ct",
            "--name-only",
            "--",
            ":(glob)*.html",
            ":(glob)**/*.html",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    created: dict[str, int] = {}
    timestamp: int | None = None
    for line in result.stdout.splitlines():
        if line.startswith("--"):
            timestamp = int(line[2:])
        elif line and timestamp is not None:
            path = line.replace("\\", "/")
            created[path] = min(created.get(path, timestamp), timestamp)
    return created


def infer_form(path: str, form_types: dict[str, str]) -> FormInference:
    """Infer creative form from directory and filename conventions."""
    lowered_parts = [part.casefold() for part in Path(path).parts]
    filename = lowered_parts[-1]
    stem = Path(filename).stem

    def match(label: str, rule: str) -> FormInference:
        return FormInference(form_types.get(label), label, rule)

    if stem.startswith("transcript"):
        return match("transcript", "transcript filename")

    if "slides" in lowered_parts[1:-1]:
        return match("slideshow", "slides directory")

    if "photography" in lowered_parts[1:-1]:
        return match("photography page", "photography directory")

    if any(part in TRAVEL_DIRECTORIES for part in lowered_parts[1:-1]):
        return match("photography page", "travel directory")

    if "blog" in lowered_parts[1:-1] or stem == "blog":
        return match("blog post", "blog path")

    teaching = any(part in TEACHING_DIRECTORIES for part in lowered_parts[1:-1])
    if teaching:
        if any(part in REFERENCE_DIRECTORIES for part in lowered_parts[1:-1]):
            return match("course reference", "course reference directory")
        if re.search(r"(?:^|[-_])(references?|références?)(?:[-_]|$)", stem):
            return match("course reference", "course reference filename")
        if re.search(r"(?:^|[-_])introduction\d*(?:[-_]|$)", stem):
            return match("course introduction", "course introduction filename")
        if re.match(r"^(class|cours|lecture|lesson)\d*$", stem):
            return match("slideshow", "course slideshow filename")
        if re.match(r"^(questions?|exam|examen|quiz)\d*$", stem):
            return match("course examination", "course examination filename")
        if re.match(
            r"^(practicals?|assignments?|exercises?|project(?:description)?|tp)\d*$",
            stem,
        ):
            return match("course assignment", "course assignment filename")
        if filename == "index.html":
            return match("course page", "teaching index page")

    return FormInference(None, "", "unclassified")


def extract_title(path: Path) -> str:
    """Extract and clean the document title."""
    class TitleParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.in_title = False
            self.parts: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag.casefold() == "title":
                self.in_title = True

        def handle_endtag(self, tag: str) -> None:
            if tag.casefold() == "title":
                self.in_title = False

        def handle_data(self, data: str) -> None:
            if self.in_title:
                self.parts.append(data)

    parser = TitleParser()
    parser.feed(path.read_text(encoding="utf-8"))
    title = " ".join("".join(parser.parts).split())
    return strip_author_from_title(title) if title else ""


def collect_pages(
    repo_root: Path,
    existing_urls: set[str],
    form_types: dict[str, str],
) -> list[Page]:
    """Collect tracked language pages absent from the Wikibase URL export."""
    created = git_creation_dates(repo_root)
    pages: list[Page] = []
    for language in SUPPORTED_LANGUAGES:
        language_root = repo_root / language
        if not language_root.is_dir():
            continue
        for path in sorted(language_root.rglob("*.html")):
            relative = path.relative_to(repo_root).as_posix()
            if relative not in created or "/template" in f"/{relative}":
                continue
            content = path.read_text(encoding="utf-8")
            if "NOTE: Article in Progress" in content:
                continue
            url = normalize_url(f"{SITE_URL}/{relative}")
            if url in existing_urls:
                continue
            pages.append(
                Page(
                    path=Path(relative),
                    language=language,
                    title=extract_title(path),
                    url=url,
                    created=created[relative],
                    form=infer_form(relative, form_types),
                )
            )
    return pages


def page_warnings(page: Page) -> list[str]:
    warnings = []
    if not page.title:
        warnings.append("missing title")
    if page.language not in LANGUAGE_ITEMS:
        warnings.append("unknown Wikibase language item")
    if not page.form.item:
        warnings.append("unclassified creative form")
    return warnings


def blocking_warnings(page: Page) -> list[str]:
    """Return problems that make a CREATE block unsafe to generate."""
    return [
        warning
        for warning in page_warnings(page)
        if warning != "unknown Wikibase language item"
    ]


def render_page(page: Page) -> str:
    """Render one page as a QuickStatements CREATE block."""
    title = quickstatements_quote(page.title)
    date = datetime.fromtimestamp(page.created, timezone.utc).strftime("%Y-%m-%d")
    statements = [
        "CREATE",
        'LAST|Den|"web page"',
        'LAST|Dfr|"page web"',
        f'LAST|L{page.language}|"{title}"',
        f'LAST|P27|{page.language}:"{title}"',
    ]
    if page.language in LANGUAGE_ITEMS:
        statements.append(f"LAST|P17|{LANGUAGE_ITEMS[page.language]}")
    statements.extend(
        [
            f"LAST|P8|{WEB_PAGE}",
            f'LAST|P3|"{quickstatements_quote(page.url)}"',
            f"LAST|P13|{HTML}",
            f"LAST|P15|{CREATOR}",
            f"LAST|P10|+{date}T00:00:00Z/11",
            f"LAST|P29|{page.form.item}",
        ]
    )
    return "\n".join(statements)


def write_quickstatements(pages: Iterable[Page], output: Path) -> int:
    """Write safe, fully classified pages to a QuickStatements file."""
    safe_pages = [page for page in pages if not blocking_warnings(page)]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n\n".join(render_page(page) for page in safe_pages)
        + ("\n" if safe_pages else ""),
        encoding="utf-8",
    )
    return len(safe_pages)


def write_review(pages: Iterable[Page], output: Path) -> None:
    """Write inferred metadata and warnings for human review."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(
            ["path", "url", "language", "title", "created", "form", "form_item", "rule", "warnings"]
        )
        for page in pages:
            writer.writerow(
                [
                    page.path,
                    page.url,
                    page.language,
                    page.title,
                    datetime.fromtimestamp(page.created, timezone.utc).date(),
                    page.form.label,
                    page.form.item or "",
                    page.form.rule,
                    "; ".join(page_warnings(page)),
                ]
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create QuickStatements for local pages absent from a Wikibase CSV export."
    )
    parser.add_argument("existing", type=Path, help="query.csv-style existing-page list")
    parser.add_argument(
        "--form-types",
        type=Path,
        default=REPO_ROOT / "creativeformtype.csv",
        help="creative-form CSV (default: creativeformtype.csv)",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("quickstatements.txt")
    )
    parser.add_argument(
        "--review", type=Path, default=Path("quickstatements-review.csv")
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    existing_urls = read_existing_urls(args.existing)
    form_types = read_form_types(args.form_types)
    pages = collect_pages(args.repo_root.resolve(), existing_urls, form_types)
    generated = write_quickstatements(pages, args.output)
    write_review(pages, args.review)
    print(
        f"Found {len(pages)} missing pages; wrote {generated} CREATE blocks "
        f"and {len(pages) - generated} review-only rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
