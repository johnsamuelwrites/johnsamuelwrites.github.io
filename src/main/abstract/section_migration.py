#!/usr/bin/env python3
"""Migrate legacy en/fr pages into Q315 pages rendered in every language.

A page is declared once in ``data/section-pages.csv``: its key, section and
parent, its abstract page item and Q315 document once minted, the item naming
the section in page titles, the slot naming the page, its en/fr item labels,
and its path in every language. The en/fr paths are the existing legacy pages;
the others are the routes the migration creates. ``P38``/``P39`` on the page
items are derived from those paths.

The content of one page is seeded from a translation table
(``section-translations.csv``, a working file): one row per bound slot,
identified by the ``(tag, class, role, occurrence)`` signature that
``render_page.py`` and ``verify_content_roundtrip.py`` use
(``tag|class|role|occurrence``, ``@alt`` for an attribute slot). A row reuses an
item (``qid``) or carries the eight values of a new one; ``kind`` is
``content``/``alt`` (an atomic ``Q3185`` item) or ``sentence`` (the ordered
parts of a paragraph composed by ``compose ordered paragraph``). Created items
are recorded by token in ``data/content-tokens.csv``. Once imported, the
Wikibase is the authority and the round-trip verifier keeps the pages equal.

    section_migration.py pages [--section S]       # CREATE abstract page items
    section_migration.py register-pages BATCH LOG  # record their QIDs
    section_migration.py hierarchy [--section S]   # P21 links to the parents
    section_migration.py fix-routes [--apply]      # P38/P39 to match the paths
    section_migration.py content PAGE              # CREATE content items
    section_migration.py register BATCH LOG        # record their QIDs
    section_migration.py structure PAGE            # P21/P41/P42 composition links
    section_migration.py build PAGE                # Q315 page + language pages
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from languages import ORDER as LANGUAGES
from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.prepare_missing_content import content_token
from abstract.render_page import SlotRewriter, load_labels

PAGES_CSV = DEFAULT_DATA_DIR / "section-pages.csv"
TOKENS_CSV = DEFAULT_DATA_DIR / "content-tokens.csv"
TRANSLATIONS = HERE / "section-translations.csv"
COMPOSE_ORDERED_PARAGRAPH = "Q4182"
ABSTRACT_PAGE_CLASS = "Q3017"
PAGE_DESCRIPTIONS = {
    "en": "language-independent page on John Samuel's website",
    "fr": "page indépendante de la langue du site de John Samuel",
}
CONTENT_DESCRIPTION = "language-independent content component used by an abstract page"
SENTENCE_DESCRIPTION = "language-independent sentence used in an abstract paragraph"
PARAGRAPH_DESCRIPTION = "language-independent paragraph composed from ordered abstract sentences"
TITLE_FORMAT = {"fr": "{name} - {section} : John Samuel"}
DEFAULT_TITLE_FORMAT = "{name} - {section}: John Samuel"
PAGE_FIELDS = (
    "page", "section", "parent", "item", "abstract_path", "title_item", "name_slot",
    "label_en", "label_fr", *LANGUAGES,
)


def quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


# --- page declarations -------------------------------------------------------


@dataclass
class Page:
    key: str
    section: str
    parent: str
    item: str
    abstract_path: str
    title_item: str
    name_slot: str
    labels: tuple[str, str]
    paths: dict[str, str]

    def route(self, language: str) -> str:
        """Language-root-relative path, the ``P39`` value."""
        return self.paths[language].split("/", 1)[1]

    def segment(self, language: str) -> str:
        """Localized path segment, the ``P38`` value."""
        route = Path(self.route(language))
        return route.parent.name if route.name == "index.html" else route.stem


def load_pages() -> dict[str, Page]:
    with PAGES_CSV.open(encoding="utf-8", newline="") as source:
        return {
            row["page"]: Page(
                key=row["page"],
                section=row["section"],
                parent=row["parent"],
                item=row["item"],
                abstract_path=row["abstract_path"],
                title_item=row["title_item"],
                name_slot=row["name_slot"],
                labels=(row["label_en"], row["label_fr"]),
                paths={language: row[language] for language in LANGUAGES},
            )
            for row in csv.DictReader(source)
        }


def save_pages(pages: dict[str, Page]) -> None:
    with PAGES_CSV.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=PAGE_FIELDS)
        writer.writeheader()
        for page in pages.values():
            writer.writerow({
                "page": page.key, "section": page.section, "parent": page.parent,
                "item": page.item, "abstract_path": page.abstract_path,
                "title_item": page.title_item, "name_slot": page.name_slot,
                "label_en": page.labels[0], "label_fr": page.labels[1], **page.paths,
            })


def parent_item(pages: dict[str, Page], page: Page) -> str:
    """The parent's item: a declared page's QID, or an external QID as given."""
    return pages[page.parent].item if page.parent in pages else page.parent


def default_abstract_path(pages: dict[str, Page], page: Page) -> str:
    """``Q315/<ancestors>/<item>.html``; a section root with pages under it is a
    directory index, and a hub's pages sit in a directory named by its item."""
    chain = []
    parent = page.parent
    while parent in pages:
        chain.append(pages[parent].item)
        parent = pages[parent].parent
    chain.append(parent)
    directory = "/".join(["Q315", *reversed(chain)])
    if page.parent not in pages and any(other.parent == page.key for other in pages.values()):
        return f"{directory}/{page.item}/index.html"
    return f"{directory}/{page.item}.html"


def selected(pages: dict[str, Page], section: str) -> list[Page]:
    return [page for page in pages.values() if not section or page.section == section]


def pages_batch(pages: dict[str, Page], section: str) -> str:
    blocks = []
    for page in selected(pages, section):
        if page.item:
            continue
        lines = [f"# page {page.key}", "CREATE"]
        for language, label in zip(("en", "fr"), page.labels):
            lines.append(f'LAST|L{language}|"{quote(label)}"')
            lines.append(f'LAST|D{language}|"{quote(PAGE_DESCRIPTIONS[language])}"')
        lines.append(f"LAST|P8|{ABSTRACT_PAGE_CLASS}")
        lines += [f'LAST|P38|{language}:"{quote(page.segment(language))}"' for language in LANGUAGES]
        lines += [f'LAST|P39|{language}:"{quote(page.route(language))}"' for language in LANGUAGES]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def created_qids(batch: Path, log: Path, marker: str) -> list[tuple[str, str]]:
    """Pair the ``# <marker> <key>`` comments of a batch with the logged QIDs."""
    keys = re.findall(rf"^# {marker} (\S+)$", batch.read_text(encoding="utf-8"), flags=re.M)
    qids = re.findall(r"^Wrote (Q\d+)$", log.read_text(encoding="utf-8"), flags=re.M)
    if len(keys) != len(qids):
        raise ValueError(f"{len(qids)} QIDs in {log} for {len(keys)} entries in {batch}")
    return list(zip(keys, qids))


def register_pages(batch: Path, log: Path) -> int:
    pages = load_pages()
    created = created_qids(batch, log, "page")
    for key, qid in created:
        pages[key].item = qid
    for key, _ in created:
        if not pages[key].abstract_path:
            pages[key].abstract_path = default_abstract_path(pages, pages[key])
    save_pages(pages)
    return len(created)


def hierarchy_batch(pages: dict[str, Page], section: str) -> str:
    return "".join(
        f"{page.item}|P21|{parent_item(pages, page)}\n" for page in selected(pages, section)
    )


def route_corrections(entity: dict, page: Page) -> list[dict]:
    """P38/P39 statements of a page item that disagree with its declared paths.

    Monolingual statements cannot be replaced through QuickStatements, so each
    differing statement is rewritten in place by its id; nothing is added, and a
    second run finds nothing to do.
    """
    expected = {
        "P38": {language: page.segment(language) for language in LANGUAGES},
        "P39": {language: page.route(language) for language in LANGUAGES},
    }
    changed = []
    for prop, values_by_language in expected.items():
        for claim in entity.get("claims", {}).get(prop, []):
            value = claim["mainsnak"]["datavalue"]["value"]
            wanted = values_by_language.get(value["language"])
            if wanted is not None and value["text"] != wanted:
                replacement = json.loads(json.dumps(claim))
                replacement["mainsnak"]["datavalue"]["value"]["text"] = wanted
                changed.append(replacement)
    return changed


def fix_routes(section: str, apply: bool) -> int:
    from wikibase_api import DEFAULT_API, WikibaseClient
    from wikibase_write import load_env

    load_env(DEFAULT_REPO_ROOT / ".env")
    pages = [page for page in selected(load_pages(), section) if page.item]
    client = WikibaseClient(os.getenv("WIKIBASE_API", DEFAULT_API), pause=0.6)
    entities = client.entities(page.item for page in pages)
    edits = {page.item: claims for page in pages if (claims := route_corrections(entities[page.item], page))}
    for item, claims in edits.items():
        for claim in claims:
            value = claim["mainsnak"]["datavalue"]["value"]
            print(f"{item} {claim['mainsnak']['property']} {value['language']}: {value['text']}")
    if apply and edits:
        client.login(os.environ["WIKIBASE_USERNAME"], os.environ["WIKIBASE_PASSWORD"])
        for item, claims in edits.items():
            client.edit_entity({"claims": claims}, entity_id=item, summary="Align page routes with their paths")
    print(f"{sum(map(len, edits.values()))} statement(s) on {len(edits)} item(s)"
          + ("" if apply else " would change; pass --apply to write"))
    return 0


# --- content items -------------------------------------------------------------


def signature(slot: str) -> tuple[tuple[str, str, str, int], str]:
    """``'p|hero-subtitle||0'`` -> ``(('p', 'hero-subtitle', '', 0), '')``."""
    slot, _, attribute = slot.partition("@")
    tag, css_class, role, occurrence = slot.split("|")
    return (tag, css_class, role, int(occurrence)), attribute


def values(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[language].strip() for language in LANGUAGES)


def load_rows(page: str, translations: Path = TRANSLATIONS) -> list[dict[str, str]]:
    with translations.open(encoding="utf-8", newline="") as source:
        rows = [row for row in csv.DictReader(source) if row["page"] == page]
    if not rows:
        raise ValueError(f"no translations for page {page!r}")
    for row in rows:
        if not row["qid"] and not all(values(row)):
            raise ValueError(f"{page} {row['slot']}: every language needs a value")
        # Labels are capped at 250 characters and P40 values at 400; a longer
        # text must be split into composed parts.
        limit = 400 if row["kind"] == "sentence" else 250
        if not row["qid"] and max(map(len, values(row))) > limit:
            raise ValueError(f"{page} {row['slot']}: a value exceeds {limit} characters")
    return rows


def paragraphs(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """Group sentence rows by slot, ordered by ordinal."""
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["kind"] == "sentence":
            result[row["slot"]].append(row)
    for slot in result:
        result[slot].sort(key=lambda row: int(row["ordinal"]))
    return dict(result)


def paragraph_values(sentences: list[dict[str, str]]) -> tuple[str, ...]:
    return tuple(" ".join(row[language].strip() for row in sentences) for language in LANGUAGES)


def load_tokens() -> dict[str, str]:
    if not TOKENS_CSV.exists():
        return {}
    with TOKENS_CSV.open(encoding="utf-8", newline="") as source:
        return {row["token"]: row["qid"] for row in csv.DictReader(source)}


def save_tokens(tokens: dict[str, str]) -> None:
    with TOKENS_CSV.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(("token", "qid"))
        writer.writerows(sorted(tokens.items()))


def labels() -> dict[str, dict[str, str]]:
    return load_labels(DEFAULT_DATA_DIR)


def content_batch(rows: list[dict[str, str]]) -> str:
    """CREATE blocks for new items, each preceded by ``# token <token>``."""
    imported = load_tokens()
    blocks: list[str] = []
    seen: set[str] = set()
    # Wikibase refuses a second item sharing an English label and description,
    # and every content item has the same description: a label already taken
    # (a generic word such as "Cube") gets its token in the description.
    taken = {row["en"].strip() for row in labels().values() if row.get("itemtype", "").strip() == "Q3185"}

    def emit(token: str, lines: list[str]) -> None:
        if token in imported or token in seen:
            return
        seen.add(token)
        blocks.append("\n".join([f"# token {token}", "CREATE", *lines]))

    for row in rows:
        if row["qid"] or row["kind"] == "sentence":
            continue
        token = content_token(values(row))
        description = CONTENT_DESCRIPTION + (f" ({token})" if values(row)[0] in taken else "")
        emit(token, [
            *(f'LAST|L{language}|"{quote(value)}"' for language, value in zip(LANGUAGES, values(row))),
            *(f'LAST|P40|{language}:"{quote(value)}"' for language, value in zip(LANGUAGES, values(row))),
            f'LAST|Den|"{description}"', "LAST|P8|Q3185",
        ])
    for sentences in paragraphs(rows).values():
        for row in sentences:
            token = content_token(values(row))
            emit(token, [
                f'LAST|Len|"{token} abstract sentence"',
                *(f'LAST|P40|{language}:"{quote(value)}"' for language, value in zip(LANGUAGES, values(row))),
                f'LAST|Den|"{SENTENCE_DESCRIPTION}"', "LAST|P8|Q3836",
            ])
        token = content_token(paragraph_values(sentences))
        emit(token, [f'LAST|Len|"{token} abstract paragraph"', f'LAST|Den|"{PARAGRAPH_DESCRIPTION}"', "LAST|P8|Q3835"])
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def register(batch: Path, log: Path) -> int:
    tokens = load_tokens()
    created = created_qids(batch, log, "token")
    tokens.update(created)
    save_tokens(tokens)
    return len(created)


def structure_batch(rows: list[dict[str, str]], page_item: str) -> str:
    tokens = load_tokens()
    lines: list[str] = []
    for sentences in paragraphs(rows).values():
        paragraph = tokens[content_token(paragraph_values(sentences))]
        lines.append(f"{paragraph}|P41|{COMPOSE_ORDERED_PARAGRAPH}")
        lines.append(f"{paragraph}|P21|{page_item}")
        for row in sentences:
            lines.append(f'{tokens[content_token(values(row))]}|P21|{paragraph}|P42|"{row["ordinal"]}"')
    return "".join(f"{line}\n" for line in lines)


# --- markup ---------------------------------------------------------------------


class Elements(HTMLParser):
    """Record each element's signature with its source offsets."""

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
            "param", "source", "track", "wbr"}

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", source)]
        self.counts: dict[tuple[str, str, str], int] = defaultdict(int)
        self.stack: list[tuple[str, tuple, int, int]] = []
        # signature -> (start, start_tag_end, end_tag_start, end_tag_end)
        self.spans: dict[tuple, tuple[int, int, int, int]] = {}
        self.feed(source)

    def _offset(self) -> int:
        line, column = self.getpos()
        return self.line_starts[line - 1] + column

    def _key(self, tag, attrs) -> tuple:
        attributes = dict(attrs)
        base = (tag, ".".join(sorted((attributes.get("class") or "").split())), attributes.get("role") or "")
        index = self.counts[base]
        self.counts[base] += 1
        return (*base, index)

    def handle_starttag(self, tag, attrs) -> None:
        key = self._key(tag, attrs)
        start = self._offset()
        end = start + len(self.get_starttag_text())
        if tag in self.VOID:
            self.spans[key] = (start, end, end, end)
            return
        self.stack.append((tag, key, start, end))

    def handle_startendtag(self, tag, attrs) -> None:
        key = self._key(tag, attrs)
        start = self._offset()
        end = start + len(self.get_starttag_text())
        self.spans[key] = (start, end, end, end)

    def handle_endtag(self, tag) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                _, key, start, inner = self.stack[index]
                close = self._offset()
                self.spans[key] = (start, inner, close, self.source.index(">", close) + 1)
                del self.stack[index:]
                return


def set_attribute(start_tag: str, name: str, value: str) -> str:
    escaped = html.escape(value, quote=True)
    pattern = re.compile(rf'(\s{re.escape(name)}\s*=\s*)(["\']).*?\2', re.S)
    if pattern.search(start_tag):
        return pattern.sub(lambda m: f'{m.group(1)}"{escaped}"', start_tag, count=1)
    closing = "/>" if start_tag.endswith("/>") else ">"
    return f'{start_tag[: -len(closing)].rstrip()} {name}="{escaped}"{closing}'


def indentation(source: str, offset: int) -> str:
    line_start = source.rfind("\n", 0, offset) + 1
    prefix = source[line_start:offset]
    return prefix if not prefix.strip() else ""


def wrap_hero_description(source: str) -> str:
    """Put hero prose in a classless ``<p>`` (the Q3636 research-page shape)."""

    def wrap(match: re.Match[str]) -> str:
        opening, body, closing = match.group(1), match.group(2), match.group(3)
        if "<p" in body:
            return match.group(0)
        indent = indentation(match.string, match.start(1))
        return f"{opening}\n{indent}    <p>{' '.join(body.split())}</p>\n{indent}{closing}"

    return re.sub(r'(<div class="hero-description">)(.*?)(</div>)', wrap, source, count=1, flags=re.S)


INLINE_TAGS = {"strong", "b", "em", "i"}


def _split_inline(match: re.Match[str]) -> str:
    """Make a ``<p>``/``<li>`` with inline markup bindable.

    A slot must be pure text, so mixed content is reshaped once in the English
    markup that every language is built from:

    * a leading ``<strong>Label:</strong>`` or ``<b>Title</b>`` followed by text
      becomes ``<strong><span>Label:</span></strong> <span>text</span>``: a
      label and its description translate independently;
    * a leading link followed by text keeps the link and wraps the text;
    * a label with keys, ``Keyboard: <span class="kbd">T</span>``, becomes a
      label span, the key span and any trailing phrase;
    * emphasis inside a sentence is unwrapped: splitting the sentence would
      break word order in the languages that reorder it.

    A text span starts its own line (whitespace either way) because
    ``render_abstract.py`` locates a composed element by a line-anchored pattern.
    """
    tag, attrs, body = match.group(1), match.group(2) or "", match.group(3)
    tags = set(re.findall(r"<(\w+)", body))
    if not tags:
        return match.group(0)
    lead = re.fullmatch(r"(\s*)<(strong|b)>([^<]+)</\2>([^<]+)", body, flags=re.S)
    if lead and (lead.group(2) == "b" or lead.group(3).strip().endswith(":")):
        space, inline, label, rest = lead.groups()
        rest = " ".join(rest.split())
        gap = "" if rest[:1] in ",.;:" else (space if "\n" in space else " ")
        return (
            f"<{tag}{attrs}>{space}<{inline}><span>{' '.join(label.split())}</span></{inline}>{gap}"
            f"<span>{rest}</span></{tag}>"
        )
    link = re.fullmatch(r"(\s*)(<a\b[^>]*>[^<]*</a>)([^<]+)", body, flags=re.S)
    if link and link.group(3).strip():
        space, anchor, rest = link.groups()
        gap = space if "\n" in space else " "
        return f"<{tag}{attrs}>{space}{anchor}{gap}<span>{' '.join(rest.split())}</span></{tag}>"
    keys = re.fullmatch(r'(\s*)([^<]+?)\s*(<span class="kbd">[^<]+</span>)([^<]*)', body, flags=re.S)
    if keys and keys.group(2).strip():
        space, label, kbd, rest = keys.groups()
        tail = f" <span>{' '.join(rest.split())}</span>" if rest.strip() else ""
        return f"<{tag}{attrs}>{space}<span>{' '.join(label.split())}</span> {kbd}{tail}</{tag}>"
    if tags <= INLINE_TAGS:
        return f"<{tag}{attrs}>{re.sub(r'</?(?:strong|b|em|i)>', '', body)}</{tag}>"
    return match.group(0)


def prepare_english(source: str) -> str:
    """The English markup every language page and the Q315 page are built from."""
    source = wrap_hero_description(source)
    # A label introducing a nested list: `<li><strong>Label</strong><ul>`.
    source = re.sub(
        r"(<li>\s*)<strong>([^<]+)</strong>(\s*<ul)",
        lambda m: f"{m.group(1)}<strong><span>{' '.join(m.group(2).split())}</span></strong>{m.group(3)}",
        source,
    )
    body = source.index("<body")
    head, rest = source[:body], source[body:]
    rest = re.sub(r"<(p|li)(\s[^>]*)?>((?:(?!<(?:p|li|ul|ol|div)\b).)*?)</\1>", _split_inline, rest, flags=re.S)
    # Markup split by an earlier build: keep the text span on its own line.
    rest = re.sub(
        r"(?m)^([ \t]*)(<(strong|b)><span>[^<]*</span></\3>|<a\b[^>]*>[^<]*</a>) (<span\b)", r"\1\2\n\1\4", rest
    )
    return head + rest


def rebase_links(source: str, origin: str, destination: str, language: str, pages: dict[str, Page]) -> str:
    """Re-express the relative URLs of ``origin`` from ``destination``.

    A link to another declared page goes to its ``language`` version when it
    exists; ``localize_links.py`` handles every other page.
    """
    by_english = {page.paths["en"]: page for page in pages.values()}
    origin_dir = os.path.dirname(origin)
    target_dir = os.path.dirname(destination)

    def rewrite(match: re.Match[str]) -> str:
        attribute, quote_char, value = match.group(1), match.group(2), match.group(3)
        parsed = urlsplit(html.unescape(value))
        if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
            return match.group(0)
        target = os.path.normpath(os.path.join(origin_dir, unquote(parsed.path))).replace(os.sep, "/")
        page = by_english.get(target)
        if page and language != "en":
            localized = page.paths[language]
            if (DEFAULT_REPO_ROOT / localized).is_file() or localized == destination:
                target = localized
        new = os.path.relpath(target, target_dir).replace(os.sep, "/")
        if parsed.query:
            new += f"?{parsed.query}"
        if parsed.fragment:
            new += f"#{parsed.fragment}"
        return f"{attribute}{quote_char}{html.escape(new, quote=True)}{quote_char}"

    return re.sub(r'(\s(?:href|src)\s*=\s*)(["\'])(.*?)\2', rewrite, source)


def with_alternates(source: str, destination: str, page: Page) -> str:
    source = re.sub(r'[ \t]*<link rel="alternate" hreflang="[^"]+" href="[^"]*" />\n', "", source)
    match = re.search(r"\n([ \t]*)<meta charset", source)
    indent = match.group(1) if match else "    "
    directory = os.path.dirname(destination)
    links = "".join(
        f'{indent}<link rel="alternate" hreflang="{language}" '
        f'href="{os.path.relpath(page.paths[language], directory)}" />\n'
        for language in LANGUAGES
    )
    head = source.index("<head>") + len("<head>")
    newline = source.index("\n", head) + 1
    return source[:newline] + links + source[newline:]


def paragraph_anchors(elements: Elements, key: tuple) -> list[tuple[tuple, int, int]]:
    """``(signature, start, end)`` of the links inside a paragraph, in order."""
    _, inner, close, _ = elements.spans[key]
    return sorted(
        ((k, s, e) for k, (s, _, _, e) in elements.spans.items() if k[0] == "a" and inner <= s < close),
        key=lambda anchor: anchor[1],
    )


def with_paragraph_anchors(source: str, rows, text_targets: dict, destination: str) -> str:
    """Write composed paragraphs that contain links.

    The stored text marks each link's position with ``()``, the convention
    ``render_abstract.py`` fills with the page's own anchors, in order; the
    links keep their markup and their own translated text.
    """
    elements = Elements(source)
    edits = []
    for slot in paragraphs(rows):
        key, _ = signature(slot)
        anchors = paragraph_anchors(elements, key)
        if not anchors:
            continue
        text = html.escape(text_targets.pop(key))
        if text.count("()") != len(anchors):
            raise ValueError(f"{destination} {slot}: {len(anchors)} links but {text.count('()')} ()")
        for anchor_key, start, end in anchors:
            markup = source[start:end]
            label = text_targets.get(anchor_key)
            if label is not None:
                markup = re.sub(r">[^<]*</a>$", f">{html.escape(label)}</a>", markup, flags=re.S)
            text = text.replace("()", f"({markup})", 1)
        _, inner, close, _ = elements.spans[key]
        edits.append((inner, close, text))
    for start, end, text in sorted(edits, reverse=True):
        source = source[:start] + text + source[end:]
    return source


def page_title(page: Page, rows, tokens, store, language: str) -> str:
    """``<name> - <section>: John Samuel``, the name taken from the page's naming
    slot (``name_slot``, else its first ``<h1>``) and the section from its
    ``title_item``; a section root names itself once."""
    by_slot = {row["slot"]: row for row in rows}
    slot = page.name_slot or next((row["slot"] for row in rows if row["slot"].startswith("h1|")), "")
    row = by_slot.get(slot)
    if row is None:
        raise ValueError(f"{page.key}: no slot names the page")
    qid = row["qid"] or tokens.get(content_token(values(row)))
    name = store[qid][language].strip() if qid in store else row[language].strip()
    if not page.title_item:
        return f"{name}{' :' if language == 'fr' else ':'} John Samuel"
    section = store[page.title_item][language].strip()
    title = TITLE_FORMAT.get(language, DEFAULT_TITLE_FORMAT).format(name=name, section=section)
    return title.replace(f"{name} - ", "", 1) if name == section else title


def language_page(page: Page, language: str, rows, tokens, english: str, pages: dict[str, Page]) -> str:
    """The ``language`` rendering of ``page`` from the English markup."""
    destination = page.paths[language]
    # The English page is the markup source: its links already resolve.
    source = english if language == "en" else rebase_links(english, page.paths["en"], destination, language, pages)
    source = re.sub(r'<html lang="[^"]*">', f'<html lang="{language}">', source, count=1)
    source = re.sub(r'(http-equiv="Content-Language" content=")[^"]*(")', rf"\g<1>{language}\2", source, count=1)
    store = labels()
    text_targets: dict[tuple, str] = {}
    attribute_targets: dict[tuple, str] = {}
    for row in rows:
        if row["kind"] == "sentence":
            continue
        key, attribute = signature(row["slot"])
        value = store[row["qid"]][language].strip() if row["qid"] else row[language].strip()
        if attribute:
            attribute_targets[(key, attribute)] = value
        else:
            text_targets[key] = value
    for slot, sentences in paragraphs(rows).items():
        text_targets[signature(slot)[0]] = " ".join(row[language].strip() for row in sentences)
    source = with_paragraph_anchors(source, rows, text_targets, destination)
    rewriter = SlotRewriter(source, text_targets, None, attribute_targets)
    source = rewriter.rewrite()
    missing = set(text_targets) - rewriter.applied
    if missing:
        raise ValueError(f"{destination}: slots not found {sorted(missing)}")
    # Mark each composed paragraph with its item, as render_abstract.py does, so
    # the renderer can address it even when its class is shared or absent.
    elements = Elements(source)
    marks = []
    for slot, sentences in paragraphs(rows).items():
        token = content_token(paragraph_values(sentences))
        if token not in tokens:
            continue
        start, inner, _, _ = elements.spans[signature(slot)[0]]
        tag = set_attribute(source[start:inner], "data-q315-source", f"local:{tokens[token]}")
        marks.append((start, inner, set_attribute(tag, "data-q315-function", f"local:{COMPOSE_ORDERED_PARAGRAPH}")))
    for start, inner, tag in sorted(marks, reverse=True):
        source = source[:start] + tag + source[inner:]
    title = html.escape(page_title(page, rows, tokens, store, language))
    source = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", source, count=1, flags=re.S)
    return with_alternates(source, destination, page)


def abstract_page(page: Page, rows, tokens, english: str, pages: dict[str, Page]) -> str:
    """The canonical Q315 document of ``page``."""
    destination = page.abstract_path
    source = rebase_links(english, page.paths["en"], destination, "en", pages)
    elements = Elements(source)
    edits: list[tuple[int, int, str]] = []
    composed = {signature(slot)[0] for slot in paragraphs(rows)}
    inside = {anchor for key in composed for anchor, _, _ in paragraph_anchors(elements, key)}
    qid_of = {
        signature(row["slot"])[0]: row["qid"] or tokens[content_token(values(row))]
        for row in rows
        if row["kind"] != "sentence" and not signature(row["slot"])[1]
    }
    for row in rows:
        if row["kind"] == "sentence":
            continue
        key, attribute = signature(row["slot"])
        if key in inside:
            continue
        qid = row["qid"] or tokens[content_token(values(row))]
        start, inner, close, _ = elements.spans[key]
        start_tag = source[start:inner]
        if attribute:
            start_tag = set_attribute(set_attribute(start_tag, attribute, ""), f"data-content-{attribute}", f"local:{qid}")
            edits.append((start, inner, start_tag))
        else:
            edits.append((start, inner, set_attribute(start_tag, "data-content", f"local:{qid}")))
            edits.append((inner, close, qid))
    for slot, sentences in paragraphs(rows).items():
        key, _ = signature(slot)
        start, inner, close, _ = elements.spans[key]
        indent = indentation(source, start)
        paragraph = tokens[content_token(paragraph_values(sentences))]
        parts = "".join(
            f'{indent}            <span data-content="local:{tokens[content_token(values(row))]}">'
            f"{tokens[content_token(values(row))]}</span>\n"
            for row in sentences
        )
        # Links inside the paragraph stay after the composition, bound to their
        # own items: the composed text marks their places with ().
        links = "".join(
            f"{indent}    "
            + set_attribute(source[s:source.index(">", s) + 1], "data-content", f"local:{qid_of[k]}")
            + f"{qid_of[k]}</a>\n"
            for k, s, _ in paragraph_anchors(elements, key)
        )
        body = (
            f'\n{indent}    <q-call data-function="local:{COMPOSE_ORDERED_PARAGRAPH}">\n'
            f'{indent}        <q-arg data-name="parts">\n{parts}'
            f"{indent}        </q-arg>\n{indent}    </q-call>\n{links}{indent}"
        )
        edits.append((start, inner, set_attribute(source[start:inner], "data-content", f"local:{paragraph}")))
        edits.append((inner, close, body))
    for start, end, replacement in sorted(edits, key=lambda edit: edit[0], reverse=True):
        source = source[:start] + replacement + source[end:]
    source = re.sub(
        r'<html lang="[^"]*">',
        f'<html data-abstract-page="local:{page.item}" data-abstract-version="1" lang="zxx">',
        source, count=1,
    )
    source = re.sub(r'(http-equiv="Content-Language" content=")[^"]*(")', r"\g<1>zxx\2", source, count=1)
    source = re.sub(r"<title>.*?</title>", f"<title>{page.item}</title>", source, count=1, flags=re.S)
    return with_alternates(source, destination, page)


def build(key: str, translations: Path = TRANSLATIONS) -> list[str]:
    pages = load_pages()
    page = pages[key]
    if not page.item or not page.abstract_path:
        raise ValueError(f"{key}: mint and register its page item first")
    rows = load_rows(key, translations)
    tokens = load_tokens()
    english = prepare_english((DEFAULT_REPO_ROOT / page.paths["en"]).read_text(encoding="utf-8"))
    written = []
    for language in LANGUAGES:
        destination = DEFAULT_REPO_ROOT / page.paths[language]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(language_page(page, language, rows, tokens, english, pages), encoding="utf-8")
        written.append(page.paths[language])
    target = DEFAULT_REPO_ROOT / page.abstract_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(abstract_page(page, rows, tokens, english, pages), encoding="utf-8")
    written.append(page.abstract_path)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("pages", "hierarchy", "fix-routes"):
        command = commands.add_parser(name)
        command.add_argument("--section", default="")
        if name == "fix-routes":
            command.add_argument("--apply", action="store_true")
    for name in ("register-pages", "register"):
        command = commands.add_parser(name)
        command.add_argument("batch", type=Path)
        command.add_argument("log", type=Path)
    for name in ("content", "structure", "build"):
        command = commands.add_parser(name)
        command.add_argument("page")
        command.add_argument("--translations", type=Path, default=TRANSLATIONS)
    args = parser.parse_args(argv)

    if args.command == "pages":
        output = HERE / f"section-{args.section or 'all'}-pages.quickstatements"
        output.write_text(pages_batch(load_pages(), args.section), encoding="utf-8")
        print(f"Wrote {output.name}")
    elif args.command == "register-pages":
        print(f"Registered {register_pages(args.batch, args.log)} page item(s) in {PAGES_CSV.name}")
    elif args.command == "hierarchy":
        output = HERE / f"section-{args.section or 'all'}-hierarchy.quickstatements"
        output.write_text(hierarchy_batch(load_pages(), args.section), encoding="utf-8")
        print(f"Wrote {output.name}")
    elif args.command == "fix-routes":
        return fix_routes(args.section, args.apply)
    elif args.command == "content":
        output = HERE / f"section-{args.page}-content.quickstatements"
        output.write_text(content_batch(load_rows(args.page, args.translations)), encoding="utf-8")
        print(f"Wrote {output.name}")
    elif args.command == "register":
        print(f"Registered {register(args.batch, args.log)} QID(s) in {TOKENS_CSV.name}")
    elif args.command == "structure":
        output = HERE / f"section-{args.page}-structure.quickstatements"
        page_item = load_pages()[args.page].item
        output.write_text(structure_batch(load_rows(args.page, args.translations), page_item), encoding="utf-8")
        print(f"Wrote {output.name}")
    else:
        for written in build(args.page, args.translations):
            print(f"wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
