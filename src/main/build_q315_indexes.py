#!/usr/bin/env python3
"""Generate Q315-scoped page list and search index artifacts."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Sequence

from paths import REPO_ROOT


Q315_ROOT = REPO_ROOT / "Q315"
LABELS_PATH = REPO_ROOT / "src/main/abstract/data/labels-wikibase.csv"
SEARCH_INDEX_PATH = Q315_ROOT / "search-index.json"
PAGE_LIST_PATH = Q315_ROOT / "Q3634.html"
CONTENT_START = '<div class="years-container" id="yearsContainer">'
CONTENT_END = "</div>\n            </main>"
QID_RE = re.compile(r"Q[1-9][0-9]*")
SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL
)
TAG_RE = re.compile(r"<[^>]+>")
ABSTRACT_PAGE_RE = re.compile(r'data-abstract-page="local:(Q[1-9][0-9]*)"')


@dataclass(frozen=True)
class Q315Page:
    qid: str
    path: Path
    relative_path: str
    url: str
    title: str
    category: str
    content: str
    year: int


class TitleParser(HTMLParser):
    """Extract the first title-like text from an HTML page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current: str | None = None
        self.values: dict[str, str] = {}

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag in {"title", "h1", "h2"} and tag not in self.values:
            self.current = tag

    def handle_endtag(self, tag: str) -> None:
        if self.current == tag:
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.current is None:
            return
        value = " ".join(data.split())
        if value:
            self.values.setdefault(self.current, value)


def load_english_labels(path: Path = LABELS_PATH) -> dict[str, str]:
    """Load QID to English label mappings from the Wikibase label export."""
    labels: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            qid = (row.get("identifier") or row.get("qid") or "").strip()
            label = row.get("en", "").strip()
            if qid and label:
                labels[qid] = label
    return labels


def qid_for_page(path: Path, source: str) -> str:
    """Return the abstract page QID declared by a Q315 HTML page."""
    match = ABSTRACT_PAGE_RE.search(source)
    if match:
        return match.group(1)
    return path.stem if QID_RE.fullmatch(path.stem) else ""


def category_for(relative_path: str, qid: str) -> str:
    """Assign a Q315-local category used by the search filter."""
    if relative_path.startswith("Q3062/"):
        return "travel"
    if relative_path.startswith("Q3636/") or qid in {"Q3636", "Q7944"}:
        return "research"
    if relative_path.startswith("Q3638/") or qid in {"Q3638", "Q3634"}:
        return "writings"
    if relative_path.startswith("Q7945/"):
        return "teaching"
    if relative_path.startswith("Q7947/"):
        return "linguistics"
    if qid == "Q3647":
        return "search"
    return "general"


def replace_qids_with_labels(text: str, labels: dict[str, str]) -> str:
    """Expand QID tokens with labels while keeping the QID searchable."""

    def replacement(match: re.Match[str]) -> str:
        qid = match.group(0)
        label = labels.get(qid)
        return f"{label} {qid}" if label else qid

    return QID_RE.sub(replacement, text)


def visible_text(source: str, labels: dict[str, str]) -> str:
    """Extract compact visible text for the client-side search index."""
    without_code = SCRIPT_STYLE_RE.sub(" ", source)
    text = TAG_RE.sub(" ", without_code)
    text = html.unescape(text)
    text = replace_qids_with_labels(text, labels)
    return " ".join(text.split())


def extract_title(source: str, qid: str, labels: dict[str, str]) -> str:
    """Prefer Wikibase labels, then page headings, then the QID."""
    if qid in labels:
        return labels[qid]
    parser = TitleParser()
    parser.feed(source)
    for key in ("h1", "h2", "title"):
        value = parser.values.get(key)
        if value:
            return replace_qids_with_labels(value, labels)
    return qid


def iter_q315_pages(root: Path = Q315_ROOT) -> Iterable[Path]:
    """Yield canonical Q315 HTML pages, excluding generated aliases."""
    for path in sorted(root.rglob("*.html")):
        relative = path.relative_to(root).as_posix()
        if relative == "search.html":
            continue
        yield path


def collect_q315_pages(
    root: Path = Q315_ROOT, labels: dict[str, str] | None = None
) -> list[Q315Page]:
    """Collect Q315 pages with normalized metadata."""
    labels = labels or load_english_labels()
    pages: list[Q315Page] = []
    for path in iter_q315_pages(root):
        source = path.read_text(encoding="utf-8")
        qid = qid_for_page(path, source)
        if not qid:
            continue
        relative_path = path.relative_to(root).as_posix()
        title = extract_title(source, qid, labels)
        pages.append(
            Q315Page(
                qid=qid,
                path=path,
                relative_path=relative_path,
                url=relative_path,
                title=title,
                category=category_for(relative_path, qid),
                content=visible_text(source, labels),
                year=2026,
            )
        )
    return pages


def write_search_index(
    pages: Sequence[Q315Page], output_path: Path = SEARCH_INDEX_PATH
) -> None:
    """Write the Q315-only search index consumed by Q3647.html."""
    payload = [
        {
            "qid": page.qid,
            "url": page.url,
            "title": page.title,
            "category": page.category,
            "content": page.content,
        }
        for page in pages
    ]
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def page_list_markup(pages: Sequence[Q315Page]) -> str:
    """Build the Q315 page registry section for Q3634.html."""
    items: list[str] = []
    for position, page in enumerate(pages, start=1):
        title = html.escape(page.title)
        qid = html.escape(page.qid)
        url = html.escape(page.url, quote=True)
        category = html.escape(page.category)
        items.append(
            f"""
            <li property='itemListElement' typeof='ListItem' class="article-item" data-year="{page.year}" data-category="{category}">
                <meta typeof="ListItem" property="position" content="{position}"/>
                <div class="article-main">
                    <a property='item' typeof='WebPage' href="{url}" class="article-link">
                        <span property='name' class="article-title">{title}</span>
                    </a>
                    <span class="updated-badge" title="{qid}">{qid}</span>
                </div>
                <div class="article-meta">
                    <span class="meta-item creation-date" title="Q315">Q315</span>
                    <span class="meta-item reading-time" title="Category">{category}</span>
                    <span class="meta-item word-count" title="Path">{html.escape(page.relative_path)}</span>
                </div>
            </li>
        """
        )
    return f"""
                    <!-- Q315 page registry generated by src/main/build_q315_indexes.py -->
                    <div class="year-section" id="year-2026">
                        <div class="year-header">
                            <h3 class="year-title">Q315</h3>
                            <span class="year-count">{len(pages)} Q315 pages</span>
                        </div>
                        <ul vocab='http://schema.org/' typeof='ItemList' class="article-list">
                            {''.join(items)}
                        </ul>
                    </div>
                    """


def update_page_list(
    pages: Sequence[Q315Page], page_path: Path = PAGE_LIST_PATH
) -> None:
    """Replace the generated list region in Q3634.html."""
    source = page_path.read_text(encoding="utf-8")
    start = source.index(CONTENT_START) + len(CONTENT_START)
    end = source.index(CONTENT_END, start)
    updated = source[:start] + "\n" + page_list_markup(pages) + "\n            " + source[end:]
    page_path.write_text(updated, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report the page count without writing generated artifacts.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pages = collect_q315_pages()
    if args.check:
        print(f"Would index {len(pages)} Q315 page(s)")
        return 0
    write_search_index(pages)
    update_page_list(pages)
    print(f"Indexed {len(pages)} Q315 page(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
