#!/usr/bin/env python3
"""Generate QuickStatements for language-independent travel-page items."""

from __future__ import annotations

import argparse
import csv
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from paths import REPO_ROOT
from wikibase_quickstatements import quickstatements_quote


LANGUAGES = ("en", "fr", "ml", "pa", "hi", "pt", "es", "it")
SUPPLEMENTAL_LANGUAGES = ("ml", "pa", "hi")
TRAVEL_ROOTS = {
    "fr": REPO_ROOT / "fr/voyages",
    "es": REPO_ROOT / "es/viajes",
    "it": REPO_ROOT / "it/viaggi",
    "pt": REPO_ROOT / "pt/viagens",
}
DESCRIPTIONS = {
    "en": "language-independent travel page",
    "fr": "page de voyage indépendante de la langue",
    "ml": "ഭാഷാ-സ്വതന്ത്ര യാത്രാ താൾ",
    "pa": "ਭਾਸ਼ਾ-ਸੁਤੰਤਰ ਯਾਤਰਾ ਸਫ਼ਾ",
    "hi": "भाषा-स्वतंत्र यात्रा पृष्ठ",
    "es": "página de viajes independiente del idioma",
    "it": "pagina di viaggio indipendente dalla lingua",
    "pt": "página de viagens independente do idioma",
}
LOCALIZED_PATH_SEGMENT = "P38"
LOCALIZED_RELATIVE_PATH_OVERRIDE = "P39"
TITLE_PREFIXES = {
    "en": ("Photography:",),
    "fr": ("Photographie :", "Photographie:"),
    "ml": ("ഛായാഗ്രഹണം:",),
    "pa": ("ਫੋਟੋਗ੍ਰਾਫੀ:",),
    "hi": ("छायाचित्र:",),
    "es": ("Fotografía:", "Fotograf?a:"),
    "it": ("Fotografia:",),
    "pt": ("Fotografia:",),
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.links: dict[str, str] = {}
        self.language_stack: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title" and not self.title_parts:
            self.in_title = True
        if tag == "span":
            self.language_stack.append(values.get("lang"))
        if tag == "a" and values.get("class") == "langlink":
            language = values.get("lang") or next(
                (lang for lang in reversed(self.language_stack) if lang),
                None,
            )
            href = values.get("href")
            if language in LANGUAGES and href:
                self.links[language] = unquote(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "span" and self.language_stack:
            self.language_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())


def parse_page(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def clean_title(title: str, language: str) -> str:
    title = title.removesuffix(": John Samuel").strip()
    title = title.removesuffix(" - John Samuel").strip()
    if "Ã" in title:
        try:
            title = title.encode("latin-1").decode("utf-8")
        except UnicodeError:
            pass
    if language == "es":
        title = title.replace("Fotograf?a", "Fotografía")
        title = title.replace("?rboles", "Árboles")
        title = title.replace("Peregrinaci?n", "Peregrinación")
    if language == "hi":
        title = title.removeprefix("Kक")
        if title.startswith("ई"):
            title = "क" + title
    for prefix in TITLE_PREFIXES.get(language, ()):
        if title.startswith(prefix):
            return title.removeprefix(prefix).strip()
    return title


def resolve_link(source: Path, href: str) -> Path:
    return (source.parent / href).resolve()


def groups() -> list[dict[str, Path]]:
    grouped: dict[str, dict[str, Path]] = {}
    for language, root in TRAVEL_ROOTS.items():
        for page in sorted(root.glob("*.html")):
            parsed = parse_page(page)
            links = {
                lang: resolve_link(page, href)
                for lang, href in parsed.links.items()
                if resolve_link(page, href).is_file()
            }
            links[language] = page.resolve()
            key = str(links.get("en", page.resolve()))
            grouped.setdefault(key, {}).update(links)
    return sorted(
        grouped.values(),
        key=lambda item: str(item.get("en", next(iter(item.values())))),
    )


def render_item(group: dict[str, Path], class_item: str) -> str:
    statements = ["CREATE"]
    for language in LANGUAGES:
        path = group.get(language)
        if path:
            title = clean_title(parse_page(path).title, language)
            statements.append(
                f'LAST|L{language}|"{quickstatements_quote(title)}"'
            )
    for language in LANGUAGES:
        statements.append(
            f'LAST|D{language}|"{quickstatements_quote(DESCRIPTIONS[language])}"'
        )
    for language in LANGUAGES:
        path = group.get(language)
        if path:
            segment = path.parent.name if path.name == "index.html" else path.stem
            statements.append(
                f'LAST|{LOCALIZED_PATH_SEGMENT}|'
                f'{language}:"{quickstatements_quote(segment)}"'
            )
    for language in LANGUAGES:
        path = group.get(language)
        if path:
            relative_path = path.relative_to(REPO_ROOT / language).as_posix()
            statements.append(
                f'LAST|{LOCALIZED_RELATIVE_PATH_OVERRIDE}|'
                f'{language}:"{quickstatements_quote(relative_path)}"'
            )
    statements.append(f"LAST|P8|{class_item}")
    return "\n".join(statements)


def write_assigned_manifest(
    grouped_pages: list[dict[str, Path]],
    first_item: int,
    output: Path,
) -> None:
    with output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(("abstract_item", "language", "path", "path_segment"))
        for offset, group in enumerate(grouped_pages):
            item = f"Q{first_item + offset}"
            for language in LANGUAGES:
                path = group.get(language)
                if not path:
                    continue
                relative_path = path.relative_to(REPO_ROOT).as_posix()
                segment = path.parent.name if path.name == "index.html" else path.stem
                writer.writerow((item, language, relative_path, segment))


def write_page_links(
    grouped_pages: list[dict[str, Path]],
    first_item: int,
    pages_csv: Path,
    output: Path,
) -> tuple[int, list[str]]:
    page_items: dict[str, str] = {}
    with pages_csv.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            url = row.get("url", "")
            item = row.get("item", "").rstrip("/").split("/")[-1]
            path = unquote(urlsplit(url).path).lstrip("/")
            if path and item:
                page_items[path] = item

    statements: list[str] = []
    missing: list[str] = []
    for offset, group in enumerate(grouped_pages):
        abstract_item = f"Q{first_item + offset}"
        for path in group.values():
            relative_path = path.relative_to(REPO_ROOT).as_posix()
            page_item = page_items.get(relative_path)
            if page_item:
                statements.append(f"{page_item}|P12|{abstract_item}")
            else:
                missing.append(relative_path)
    output.write_text(
        "\n".join(sorted(set(statements))) + ("\n" if statements else ""),
        encoding="utf-8",
    )
    return len(set(statements)), sorted(set(missing))


def write_supplemental_languages(
    grouped_pages: list[dict[str, Path]],
    first_item: int,
    pages_csv: Path,
    output: Path,
) -> tuple[int, int]:
    page_items: dict[str, str] = {}
    with pages_csv.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            url = row.get("url", "")
            item = row.get("item", "").rstrip("/").split("/")[-1]
            path = unquote(urlsplit(url).path).lstrip("/")
            if path and item:
                page_items[path] = item

    statements: list[str] = []
    abstract_updates = 0
    page_links = 0
    for offset, group in enumerate(grouped_pages):
        abstract_item = f"Q{first_item + offset}"
        for language in SUPPLEMENTAL_LANGUAGES:
            path = group.get(language)
            if not path:
                continue
            title = clean_title(parse_page(path).title, language)
            segment = path.parent.name if path.name == "index.html" else path.stem
            relative_output = path.relative_to(REPO_ROOT / language).as_posix()
            relative_repository = path.relative_to(REPO_ROOT).as_posix()
            statements.extend(
                [
                    f'{abstract_item}|L{language}|"{quickstatements_quote(title)}"',
                    f'{abstract_item}|D{language}|'
                    f'"{quickstatements_quote(DESCRIPTIONS[language])}"',
                    f'{abstract_item}|{LOCALIZED_PATH_SEGMENT}|'
                    f'{language}:"{quickstatements_quote(segment)}"',
                    f'{abstract_item}|{LOCALIZED_RELATIVE_PATH_OVERRIDE}|'
                    f'{language}:"{quickstatements_quote(relative_output)}"',
                ]
            )
            abstract_updates += 1
            page_item = page_items.get(relative_repository)
            if page_item:
                statements.append(f"{page_item}|P12|{abstract_item}")
                page_links += 1
    output.write_text("\n".join(statements) + "\n", encoding="utf-8")
    return abstract_updates, page_links


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--class-item",
        default="Q3017",
        help="Wikibase QID for the language-independent travel-page class",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "quickstatements-abstract-items.txt",
    )
    parser.add_argument(
        "--first-assigned-item",
        type=int,
        help="first assigned numeric QID; also writes the manifest and P12 links",
    )
    args = parser.parse_args()
    grouped_pages = groups()
    output = "\n\n".join(
        render_item(group, args.class_item) for group in grouped_pages
    )
    args.output.write_text(output + "\n", encoding="utf-8")
    print(f"Wrote {len(grouped_pages)} abstract items to {args.output}")
    if args.first_assigned_item is not None:
        manifest = REPO_ROOT / "abstract-items.csv"
        links = REPO_ROOT / "quickstatements-link-pages-to-abstract.txt"
        supplemental = REPO_ROOT / "quickstatements-add-hi-ml-pa.txt"
        write_assigned_manifest(
            grouped_pages,
            args.first_assigned_item,
            manifest,
        )
        count, missing = write_page_links(
            grouped_pages,
            args.first_assigned_item,
            REPO_ROOT / "pages.csv",
            links,
        )
        print(f"Wrote assigned-item manifest to {manifest}")
        print(f"Wrote {count} P12 page links to {links}")
        if missing:
            print(f"{len(missing)} concrete paths have no item in pages.csv")
        updates, supplemental_links = write_supplemental_languages(
            grouped_pages,
            args.first_assigned_item,
            REPO_ROOT / "pages.csv",
            supplemental,
        )
        print(
            f"Wrote {updates} abstract-language updates and "
            f"{supplemental_links} P12 links to {supplemental}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
