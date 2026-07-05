#!/usr/bin/env python3
"""Model prose slots as composed abstract paragraphs, not flat content items.

An abstract site does not store a paragraph as one opaque string per language.
It stores ordered *sentences* (``Q3836``) and a *paragraph* (``Q3835``) whose
constructor is an abstract function (``Q3834``) — here ``compose ordered
paragraph`` — so the same language-independent structure renders in every
language. ``prepare_missing_content.py`` proposes flat ``Q3185`` items, which
is right for an atomic label but wrong for prose. This tool is the prose path.

For every unbound prose slot (a slot whose text carries sentence-terminal
punctuation) it segments each language into sentences. Because one paragraph
shares a single ordered set of sentence items across all languages, the parts
can only differ per language in wording, never in count: when the present
languages disagree on how many sentences the text has, the tool keeps the slot
as a single-sentence paragraph rather than inventing a misaligned split. Every
prose slot still becomes a composition; only its granularity is guarded.

Because plain QuickStatements cannot link two items created in the same batch,
work is two-phase, mirroring ``prepare_abstract_paragraph.py``:

1. default run — CREATE the deduplicated sentence and paragraph items and write
   a reconciliation manifest (``abstract-composition-review.csv``);
2. ``--structure`` run — once the manifest carries the returned QIDs and the
   ``compose ordered paragraph`` function QID, emit the ``P21``/``P41``/``P42``
   links and the ``<q-call>`` markup that binds each slot on its abstract page.

Nothing is imported and no HTML is changed automatically.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.prepare_missing_content import (
    alternate_pages,
    content_token,
    page_sources,
    slot_metadata,
)
from abstract.prepare_travel_content import (
    LANGUAGES,
    QID_TEXT,
    content_bindings,
    quote,
    slots,
)

DEFAULT_DATA = DEFAULT_DATA_DIR
DEFAULT_QUICKSTATEMENTS = HERE / "abstract-composition.quickstatements"
DEFAULT_PARTIAL_QUICKSTATEMENTS = HERE / "abstract-composition-partial.quickstatements"
DEFAULT_REVIEW = HERE / "abstract-composition-review.csv"
DEFAULT_STRUCTURE = HERE / "abstract-composition-structure.quickstatements"
DEFAULT_MARKUP = HERE / "abstract-composition-markup.txt"
DEFAULT_TRANSLATIONS = HERE / "abstract-composition-translations.csv"

ABSTRACT_PARAGRAPH_CLASS = "Q3835"
ABSTRACT_SENTENCE_CLASS = "Q3836"
INSTANCE_OF = "P8"
PART_OF = "P21"
MONOLINGUAL_CONTENT_PROPERTY = "P40"
CONSTRUCTOR_FUNCTION_PROPERTY = "P41"
SEQUENCE_ORDINAL_PROPERTY = "P42"
COMPOSE_FUNCTION_TOKEN = "FN_COMPOSE_ORDERED_PARAGRAPH"

# A sentence boundary is terminal punctuation followed by whitespace. The em
# dash and comma are deliberately excluded: they occur mid-sentence in this
# content. The danda (।) serves Hindi and Punjabi.
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?।؟])\s+")
TERMINAL_PUNCTUATION = re.compile(r"[.!?।؟]")


def split_sentences(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    pieces = [piece.strip() for piece in SENTENCE_BOUNDARY.split(stripped)]
    return [piece for piece in pieces if piece] or [stripped]


def is_prose(english: str) -> bool:
    """A slot is prose when its text *ends* in sentence-terminal punctuation.

    Requiring the terminator at the end, rather than anywhere, keeps names and
    labels whose only punctuation is an internal abbreviation dot — ``A. R.
    Rahman``, ``H.G. Wells`` — out of the paragraph path. Those remain flat
    content items handled by ``prepare_missing_content.py``.
    """
    stripped = english.strip()
    return bool(stripped) and stripped[-1] in ".!?।؟"


def segment(values: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Return per-sentence language tuples, aligned across present languages.

    ``values`` is one string per language (``""`` when absent). The result is a
    list of sentence tuples in the same language order. A multi-sentence split
    is used only when every present language yields the same sentence count;
    otherwise the whole slot is a single sentence, so no language is forced into
    a boundary it does not have.
    """
    per_language = [split_sentences(value) for value in values]
    counts = {len(pieces) for pieces, value in zip(per_language, values) if value}
    if len(counts) == 1 and counts != {0}:
        count = counts.pop()
        if count > 1:
            return [
                tuple(
                    pieces[index] if value else ""
                    for pieces, value in zip(per_language, values)
                )
                for index in range(count)
            ]
    return [values]


class Composition:
    """A planned paragraph and its ordered sentence parts."""

    def __init__(self, token: str, values: tuple[str, ...]) -> None:
        self.token = token
        self.values = values
        self.sentences: list[tuple[str, tuple[str, ...]]] = []


def load_translations(path: Path) -> dict[str, dict[str, str]]:
    """Read reviewed translations that fill a sentence's missing languages.

    The long-format file has ``token,language,text`` rows. The token is the
    sentence's stable identity — the same ``M…`` shown in the review CSV — so a
    filled translation never changes which item the sentence is, it only adds a
    language it was missing. Only empty languages are ever filled; a value the
    source pages already provide is never overwritten.
    """
    result: dict[str, dict[str, str]] = {}
    if not path.exists():
        return result
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            token = (row.get("token") or "").strip()
            language = (row.get("language") or "").strip()
            text = (row.get("text") or "").strip()
            if token and language in LANGUAGES and text:
                result.setdefault(token, {})[language] = text
    return result


def _fill(sentence: tuple[str, ...], fills: dict[str, str]) -> tuple[str, ...]:
    if not fills:
        return sentence
    return tuple(
        value if value else fills.get(language, "")
        for language, value in zip(LANGUAGES, sentence)
    )


def plan(
    repo_root: Path,
    sources: list[tuple[str, Path]],
    translations: dict[str, dict[str, str]] | None = None,
) -> tuple[list[Composition], dict[str, tuple[str, ...]], list[dict[str, str]]]:
    translations = translations or {}
    paragraphs: dict[str, Composition] = {}
    sentence_values: dict[str, tuple[str, ...]] = {}
    slot_rows: list[dict[str, str]] = []
    for page_id, relative in sources:
        abstract_page = (repo_root / relative).resolve()
        localized = [slots(page) for page in alternate_pages(repo_root, abstract_page)]
        # Occurrence-based keys only align across languages when the pages share
        # the same repeated structure. When a language page has a different
        # number of same-signature elements (a list of different length, a
        # missing section), position N in that page is a different element, so
        # its text is unrelated to the English sentence. Counting signatures
        # per page lets a mismatch drop that language instead of importing an
        # unrelated string as though it were a translation.
        signature_counts = [
            Counter(key[:3] for key in page) for page in localized
        ]
        bindings = content_bindings(abstract_page)
        metadata = slot_metadata(abstract_page)
        for key, abstract_text in slots(abstract_page).items():
            if key in bindings or QID_TEXT.fullmatch(abstract_text):
                continue
            english_count = signature_counts[0].get(key[:3], 0)
            values = tuple(
                page.get(key, "")
                if signature_counts[index].get(key[:3], 0) == english_count
                else ""
                for index, page in enumerate(localized)
            )
            english = values[0]
            if not english or not is_prose(english):
                continue
            segmented = segment(values)
            # Only a genuinely multi-sentence slot is a composition. A single
            # sentence is an atomic content item — wrapping it in a one-part
            # paragraph would duplicate its identity (paragraph and sentence
            # would hash to the same token) and adds no structure. Those slots
            # are left to prepare_missing_content.py as flat content items.
            if len(segmented) < 2:
                continue
            paragraph_token = content_token(values)
            composition = paragraphs.get(paragraph_token)
            if composition is None:
                composition = Composition(paragraph_token, values)
                for sentence in segmented:
                    # The token is the source sentence's identity; reviewed
                    # translations then fill the languages the pages lacked
                    # without changing that identity.
                    token = content_token(sentence)
                    filled = _fill(sentence, translations.get(token, {}))
                    sentence_values.setdefault(token, filled)
                    composition.sentences.append((token, filled))
                paragraphs[paragraph_token] = composition
            tag, class_name, role, occurrence = key
            slot_rows.append(
                {
                    "page": page_id,
                    "path": relative.as_posix(),
                    "tag": tag,
                    "class": class_name,
                    "role": role,
                    "occurrence": str(occurrence),
                    "paragraph_token": paragraph_token,
                }
            )
    return list(paragraphs.values()), sentence_values, slot_rows


def _sentence_block(token: str, values: tuple[str, ...]) -> str:
    statements = ["CREATE", f'LAST|Len|"{token} abstract sentence"']
    statements.extend(
        f'LAST|{MONOLINGUAL_CONTENT_PROPERTY}|{language}:"{quote(value)}"'
        for language, value in zip(LANGUAGES, values)
        if value
    )
    statements.extend(
        (
            'LAST|Den|"language-independent sentence used in an abstract paragraph"',
            f"LAST|{INSTANCE_OF}|{ABSTRACT_SENTENCE_CLASS}",
        )
    )
    return "\n".join(statements)


def _paragraph_block(token: str) -> str:
    return "\n".join(
        (
            "CREATE",
            f'LAST|Len|"{token} abstract paragraph"',
            'LAST|Den|"language-independent paragraph composed from '
            'ordered abstract sentences"',
            f"LAST|{INSTANCE_OF}|{ABSTRACT_PARAGRAPH_CLASS}",
        )
    )


def create_quickstatements(
    compositions: list[Composition],
    sentence_values: dict[str, tuple[str, ...]],
    already_imported: set[str] | None = None,
) -> tuple[str, str]:
    """Return ``(complete, partial)`` create batches.

    A sentence whose eight languages are all present is import-ready; one that
    is missing a language is held in the partial batch as an explicit
    translation backlog, never padded with an English fallback. Paragraph items
    carry no monolingual value, so they always accompany the complete batch.

    Tokens already present in the export are skipped so the batch is safe to
    re-run: Wikibase refuses a second item with the same label and description,
    so re-emitting an imported item would fail the whole import.
    """
    imported = already_imported or set()
    complete: list[str] = []
    partial: list[str] = []
    for token, values in sentence_values.items():
        if token in imported:
            continue
        block = _sentence_block(token, values)
        (complete if all(values) else partial).append(block)
    complete.extend(
        _paragraph_block(c.token) for c in compositions if c.token not in imported
    )
    return (
        "\n\n".join(complete) + ("\n" if complete else ""),
        "\n\n".join(partial) + ("\n" if partial else ""),
    )


def write_review(
    path: Path,
    compositions: list[Composition],
    sentence_values: dict[str, tuple[str, ...]],
    slot_rows: list[dict[str, str]],
) -> None:
    fields = (
        "token", "kind", "qid", "ordinal", "parent_token", "function_token",
        "pages", *LANGUAGES,
    )
    paragraph_pages: dict[str, list[str]] = {}
    for row in slot_rows:
        paragraph_pages.setdefault(row["paragraph_token"], []).append(
            f'{row["page"]}:{row["tag"]}.{row["class"]}[{row["occurrence"]}]'
        )
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        for composition in compositions:
            writer.writerow(
                {
                    "token": composition.token,
                    "kind": "paragraph",
                    "qid": "",
                    "ordinal": "",
                    "parent_token": "",
                    "function_token": COMPOSE_FUNCTION_TOKEN,
                    "pages": ";".join(sorted(set(paragraph_pages.get(composition.token, [])))),
                    **dict(zip(LANGUAGES, composition.values)),
                }
            )
            for ordinal, (token, values) in enumerate(composition.sentences, 1):
                writer.writerow(
                    {
                        "token": token,
                        "kind": "sentence",
                        "qid": "",
                        "ordinal": str(ordinal),
                        "parent_token": composition.token,
                        "function_token": "",
                        "pages": "",
                        **dict(zip(LANGUAGES, values)),
                    }
                )


def read_review(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


IMPORT_LABEL = re.compile(r"(M[A-F0-9]{12}) abstract (?:sentence|paragraph)")
COMPOSE_FUNCTION_LABEL = "compose ordered paragraph"


def imported_tokens(data_dir: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Map each ``M…`` token to the QID Wikibase returned, plus any duplicates.

    Composition items are imported carrying their stable token as the English
    label, so reconciliation reads the returned QID straight from the pinned
    export rather than requiring the QID be pasted into the review CSV. A token
    that resolves to more than one QID is a duplicated Wikibase item: it is left
    out of the returned mapping and reported separately so the ambiguity is
    fixed (merged) rather than silently linked to an arbitrary copy.
    """
    path = data_dir / "labels-wikibase.csv"
    candidates: dict[str, list[str]] = {}
    if not path.exists():
        return {}, {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            qid = (row.get("identifier") or "").strip()
            match = IMPORT_LABEL.fullmatch((row.get("en") or "").strip())
            if match and re.fullmatch(r"Q[1-9][0-9]*", qid):
                candidates.setdefault(match.group(1), [])
                if qid not in candidates[match.group(1)]:
                    candidates[match.group(1)].append(qid)
    resolved = {token: qids[0] for token, qids in candidates.items() if len(qids) == 1}
    duplicates = {token: qids for token, qids in candidates.items() if len(qids) > 1}
    return resolved, duplicates


def compose_function_qid(data_dir: Path) -> str:
    path = data_dir / "labels-wikibase.csv"
    if not path.exists():
        return ""
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if (row.get("itemtype") or "").strip() == "Q3834" and (
                row.get("en") or ""
            ).strip() == COMPOSE_FUNCTION_LABEL:
                qid = (row.get("identifier") or "").strip()
                if re.fullmatch(r"Q[1-9][0-9]*", qid):
                    return qid
    return ""


def read_bindings(
    rows: list[dict[str, str]],
    function_qid: str,
    initial: dict[str, str] | None = None,
) -> dict[str, str]:
    bindings = dict(initial or {})
    bindings[COMPOSE_FUNCTION_TOKEN] = function_qid
    for row in rows:
        qid = (row.get("qid") or "").strip()
        if qid:
            if not re.fullmatch(r"Q[1-9][0-9]*", qid):
                raise ValueError(f"invalid QID {qid!r} for token {row['token']}")
            bindings[row["token"]] = qid
    return bindings


def resolved_paragraph_tokens(
    rows: list[dict[str, str]], bindings: dict[str, str]
) -> set[str]:
    """Paragraph tokens whose paragraph and every sentence have a QID.

    A paragraph whose sentences are still in the untranslated backlog cannot be
    linked yet; emitting a partial structure would leave dangling references.
    """
    sentences: dict[str, list[str]] = {}
    paragraphs: set[str] = set()
    for row in rows:
        if row["kind"] == "paragraph":
            paragraphs.add(row["token"])
        else:
            sentences.setdefault(row["parent_token"], []).append(row["token"])
    return {
        token
        for token in paragraphs
        if token in bindings
        and all(sentence in bindings for sentence in sentences.get(token, []))
    }


def structure_quickstatements(
    rows: list[dict[str, str]],
    slot_rows: list[dict[str, str]],
    bindings: dict[str, str],
    resolved: set[str],
) -> str:
    page_of = {row["paragraph_token"]: row["page"] for row in slot_rows}
    statements: list[str] = []
    function = bindings[COMPOSE_FUNCTION_TOKEN]
    for row in rows:
        if row["kind"] != "paragraph" or row["token"] not in resolved:
            continue
        paragraph = bindings[row["token"]]
        page = page_of.get(row["token"])
        if not page:
            continue
        statements.append(f"{paragraph}|{CONSTRUCTOR_FUNCTION_PROPERTY}|{function}")
        statements.append(f"{paragraph}|{PART_OF}|{page}")
    for row in rows:
        if row["kind"] != "sentence" or row["parent_token"] not in resolved:
            continue
        statements.append(
            f'{bindings[row["token"]]}|{PART_OF}|{bindings[row["parent_token"]]}'
            f'|{SEQUENCE_ORDINAL_PROPERTY}|"{row["ordinal"]}"'
        )
    return "\n".join(statements) + ("\n" if statements else "")


def markup_lines(
    slot: dict[str, str],
    composition_rows: list[dict[str, str]],
    bindings: dict[str, str],
) -> list[str]:
    paragraph = bindings[slot["paragraph_token"]]
    function = bindings[COMPOSE_FUNCTION_TOKEN]
    sentences = [
        bindings[row["token"]]
        for row in composition_rows
        if row["kind"] == "sentence" and row["parent_token"] == slot["paragraph_token"]
    ]
    tag = slot["tag"]
    class_attr = f' class="{html.escape(slot["class"])}"' if slot["class"] else ""
    lines = [
        f'<{tag}{class_attr} data-content="local:{paragraph}">',
        f'    <q-call data-function="local:{function}">',
        '        <q-arg data-name="parts">',
    ]
    lines.extend(
        f'            <span data-content="local:{sentence}">{sentence}</span>'
        for sentence in sentences
    )
    lines.extend(("        </q-arg>", "    </q-call>", f"</{tag}>"))
    return lines


def markup_for(
    slot: dict[str, str],
    composition_rows: list[dict[str, str]],
    bindings: dict[str, str],
) -> str:
    header = f'# {slot["page"]} {slot["tag"]}.{slot["class"]}[{slot["occurrence"]}]'
    return header + "\n" + "\n".join(markup_lines(slot, composition_rows, bindings))


class SlotSpans(HTMLParser):
    """Record the raw character span of each requested ``slots`` key.

    The key ``(tag, class, role, occurrence)`` is counted exactly as
    :class:`~abstract.prepare_travel_content.DirectTextSlots` counts it, so a
    binder can locate the very element a slot came from — including a bare
    ``<p>`` identified only by its occurrence — and replace it by offset rather
    than by a fragile text match.
    """

    def __init__(self, text: str, targets: set[tuple[str, str, str, int]]) -> None:
        super().__init__(convert_charrefs=True)
        self.text = text
        self.line_starts = [0]
        for index, character in enumerate(text):
            if character == "\n":
                self.line_starts.append(index + 1)
        self.targets = targets
        self.counts: Counter[tuple[str, str, str]] = Counter()
        self.stack: list[tuple[str, tuple[str, str, str, int], int]] = []
        self.spans: dict[tuple[str, str, str, int], tuple[int, int]] = {}

    def _offset(self) -> int:
        line, column = self.getpos()
        return self.line_starts[line - 1] + column

    def handle_starttag(self, tag, attrs) -> None:
        values = dict(attrs)
        base = (
            tag,
            ".".join(sorted((values.get("class") or "").split())),
            values.get("role") or "",
        )
        key = (*base, self.counts[base])
        self.counts[base] += 1
        self.stack.append((tag, key, self._offset()))

    def handle_endtag(self, tag) -> None:
        if tag not in [entry[0] for entry in self.stack]:
            return
        while self.stack:
            current_tag, key, start = self.stack.pop()
            if current_tag == tag:
                if key in self.targets:
                    close = self.text.index(">", self._offset()) + 1
                    self.spans[key] = (start, close)
                break


def bind(
    repo_root: Path,
    rows: list[dict[str, str]],
    slot_rows: list[dict[str, str]],
    bindings: dict[str, str],
    resolved: set[str],
    check: bool,
) -> tuple[list[str], list[str]]:
    by_page: dict[str, list[dict[str, str]]] = {}
    for slot in slot_rows:
        if slot["paragraph_token"] in resolved:
            by_page.setdefault(slot["path"], []).append(slot)
    changed: list[str] = []
    errors: list[str] = []
    for path, slots_ in sorted(by_page.items()):
        source = (repo_root / path).read_text(encoding="utf-8")
        targets = {
            (slot["tag"], slot["class"], slot["role"], int(slot["occurrence"]))
            for slot in slots_
        }
        locator = SlotSpans(source, targets)
        locator.feed(source)
        locator.close()
        replacements: list[tuple[int, int, str]] = []
        for slot in slots_:
            key = (slot["tag"], slot["class"], slot["role"], int(slot["occurrence"]))
            span = locator.spans.get(key)
            if span is None:
                errors.append(f"{path}: could not locate slot {key}")
                continue
            start, end = span
            line_start = source.rfind("\n", 0, start) + 1
            prefix = source[line_start:start]
            indent = prefix if not prefix.strip() else ""
            block = ("\n" + indent).join(markup_lines(slot, rows, bindings))
            replacements.append((start, end, block))
        updated = source
        for start, end, block in sorted(replacements, reverse=True):
            updated = updated[:start] + block + updated[end:]
        if updated != source:
            changed.append(path)
            if not check:
                (repo_root / path).write_text(updated, encoding="utf-8")
    return changed, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--page", default="", help="restrict to one abstract page QID")
    parser.add_argument("--quickstatements", type=Path, default=DEFAULT_QUICKSTATEMENTS)
    parser.add_argument(
        "--partial-quickstatements",
        type=Path,
        default=DEFAULT_PARTIAL_QUICKSTATEMENTS,
    )
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument(
        "--translations",
        type=Path,
        default=DEFAULT_TRANSLATIONS,
        help="reviewed token,language,text file filling missing languages",
    )
    parser.add_argument("--structure", action="store_true", help="emit phase-2 links + markup")
    parser.add_argument("--structure-output", type=Path, default=DEFAULT_STRUCTURE)
    parser.add_argument("--markup-output", type=Path, default=DEFAULT_MARKUP)
    parser.add_argument(
        "--bind",
        action="store_true",
        help="replace resolved prose slots in the abstract pages with q-call markup",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="with --bind, report which pages would change without writing",
    )
    parser.add_argument(
        "--function-qid",
        default="",
        help="QID of the imported 'compose ordered paragraph' function",
    )
    args = parser.parse_args()
    try:
        repo_root = args.repo_root.resolve()
        sources = page_sources(repo_root, args.page)
        translations = load_translations(args.translations)
        compositions, sentence_values, slot_rows = plan(
            repo_root, sources, translations
        )
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if not args.structure and not args.bind:
        try:
            imported, duplicates = imported_tokens(args.data_dir.resolve())
        except (OSError, ValueError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1
        already = set(imported) | set(duplicates)
        complete, partial = create_quickstatements(
            compositions, sentence_values, already
        )
        args.quickstatements.write_text(complete, encoding="utf-8")
        args.partial_quickstatements.write_text(partial, encoding="utf-8")
        write_review(args.review, compositions, sentence_values, slot_rows)
        multi = sum(1 for composition in compositions if len(composition.sentences) > 1)
        complete_count = sum(
            1
            for token, values in sentence_values.items()
            if all(values) and token not in already
        )
        skipped = sum(1 for token in sentence_values if token in already) + sum(
            1 for c in compositions if c.token in already
        )
        print(
            f"Planned {len(compositions)} paragraphs "
            f"({multi} multi-sentence) from {len(sentence_values)} unique sentences "
            f"across {len(slot_rows)} prose slots"
        )
        print(
            f"{complete_count} new complete sentences to import; "
            f"{skipped} item(s) already in the export were skipped"
        )
        return 0

    try:
        data_dir = args.data_dir.resolve()
        rows = read_review(args.review)
        function_qid = args.function_qid or compose_function_qid(data_dir)
        if not function_qid:
            raise ValueError(
                "no 'compose ordered paragraph' function in the export; "
                "import abstract-functions.quickstatements or pass --function-qid"
            )
        imported, duplicates = imported_tokens(data_dir)
        bindings = read_bindings(rows, function_qid, imported)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    referenced = {row["token"] for row in rows}
    for token, qids in sorted(duplicates.items()):
        if token not in referenced:
            continue
        print(
            f"WARNING: token {token} imported as duplicate items "
            f"{', '.join(qids)}; merge them in Wikibase",
            file=sys.stderr,
        )
    resolved = resolved_paragraph_tokens(rows, bindings)
    paragraph_total = sum(1 for row in rows if row["kind"] == "paragraph")

    if args.bind:
        changed, errors = bind(repo_root, rows, slot_rows, bindings, resolved, args.check)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        verb = "Would bind" if args.check else "Bound"
        print(
            f"{verb} {len(resolved)} resolved paragraph(s) across "
            f"{len(changed)} abstract page(s): {', '.join(sorted(changed)) or 'none'}"
        )
        return 1 if errors else 0

    args.structure_output.write_text(
        structure_quickstatements(rows, slot_rows, bindings, resolved),
        encoding="utf-8",
    )
    blocks = [
        markup_for(slot, rows, bindings)
        for slot in slot_rows
        if slot["paragraph_token"] in resolved
    ]
    args.markup_output.write_text(
        "\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8"
    )
    print(
        f"Resolved {len(resolved)}/{paragraph_total} paragraphs "
        f"(function {function_qid}); wrote links to {args.structure_output.name} "
        f"and {len(blocks)} markup block(s) to {args.markup_output.name}"
    )
    print(
        f"{paragraph_total - len(resolved)} paragraphs still await sentence "
        "imports (translation backlog)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
