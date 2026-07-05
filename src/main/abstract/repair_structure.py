#!/usr/bin/env python3
"""Insert template-defined bound elements that a language page is missing.

`render_page.py` rewrites the text of slots that already exist. Some legacy
language pages predate a component and omit a bound child entirely (e.g. the
`ml`/`pa`/`hi` travel pages carry every gallery-card but not its
`card-description` paragraph). Where the *parent container* still lines up one
for one with the template, the missing child can be inserted in its template
position and filled with the entity's Wikibase label — no page rebuild.

The repair is deliberately conservative. For a bound element type it acts only
when the parent-container count is identical in template and page (so container N
maps to container N unambiguously); pages whose containers diverge in number —
the large index pages that are missing whole entries — are left untouched and
reported, because those need regeneration, not insertion.
"""

from __future__ import annotations

import argparse
import csv
import html
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.discover_content_migration import discover
from abstract.prepare_travel_content import LANGUAGES, TEXT_TAGS

DEFAULT_DATA = DEFAULT_DATA_DIR
COMPOSED_ITEMTYPES = frozenset({"Q3835", "Q3836"})
VOID = frozenset({
    "img", "br", "hr", "meta", "link", "input", "source", "path", "circle",
    "rect", "line", "polygon", "use", "stop", "ellipse", "area", "col", "base",
})


class Node:
    __slots__ = ("tag", "cls", "cls_raw", "role", "content", "entity",
                 "children", "parent", "open_start", "open_end", "close_start")

    def __init__(self, tag, cls, cls_raw, role, content, entity):
        self.tag, self.cls, self.cls_raw, self.role = tag, cls, cls_raw, role
        self.content, self.entity = content, entity
        self.children: list["Node"] = []
        self.parent: "Node | None" = None
        self.open_start = self.open_end = self.close_start = None

    @property
    def sig(self):
        return (self.tag, self.cls, self.role)

    @property
    def qid(self):
        return self.content or self.entity


class Tree(HTMLParser):
    """Offset-tracking element tree; text nodes are not retained."""

    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.source = source
        self._starts = [0]
        for i, c in enumerate(source):
            if c == "\n":
                self._starts.append(i + 1)
        self.root = Node("#root", "", "", "", None, None)
        self.stack = [self.root]
        self.feed(source)
        self.close()

    def _abs(self, pos):
        return self._starts[pos[0] - 1] + pos[1]

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls_raw = d.get("class") or ""
        cls = ".".join(sorted(cls_raw.split()))
        content = d.get("data-content") or ""
        entity = d.get("data-entity") or ""
        node = Node(
            tag, cls, cls_raw, d.get("role") or "",
            content.removeprefix("local:") if content.startswith("local:") else "",
            entity.removeprefix("local:") if entity.startswith("local:") else "",
        )
        node.parent = self.stack[-1]
        node.open_start = self._abs(self.getpos())
        node.open_end = node.open_start + len(self.get_starttag_text() or "")
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if len(self.stack) > 1 and self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag not in (n.tag for n in self.stack):
            return
        end = self._abs(self.getpos())
        while len(self.stack) > 1:
            node = self.stack.pop()
            if node.close_start is None:
                node.close_start = end
            if node.tag == tag:
                break

    def line_indent(self, offset: int) -> str:
        line_start = self.source.rfind("\n", 0, offset) + 1
        return self.source[line_start:offset] if self.source[line_start:offset].isspace() else ""


def load_labels(data_dir: Path) -> dict[str, dict[str, str]]:
    with (data_dir / "labels-wikibase.csv").open(encoding="utf-8-sig", newline="") as source:
        return {row["identifier"]: row for row in csv.DictReader(source)}


def _walk(node: Node):
    for child in node.children:
        yield child
        yield from _walk(child)


def _instances(tree: Tree, sig) -> list[Node]:
    return [n for n in _walk(tree.root) if n.sig == sig]


def _anchor_index(container: Node, element: Node) -> int:
    """Position in ``container.children`` to insert after (-1 == container start)."""
    return container.children.index(element) - 1


def plan_page(
    tmpl: Tree,
    page: Tree,
    labels: dict[str, dict[str, str]],
    language: str,
) -> tuple[list[tuple[int, str]], list[str]]:
    """Return (insertions, skipped) for one language page.

    ``insertions`` are ``(offset, markup)`` splices; ``skipped`` describes bound
    element types whose container count differs from the template.
    """
    insertions: list[tuple[int, str]] = []
    skipped: list[str] = []
    handled: set[tuple[str, str, str]] = set()

    for tnode in _walk(tmpl.root):
        qid = tnode.qid
        if (
            not qid
            or qid not in labels
            or labels[qid].get("itemtype", "").strip() in COMPOSED_ITEMTYPES
            or tnode.tag not in TEXT_TAGS
            or tnode.parent is None
            or tnode.sig in handled
        ):
            continue
        handled.add(tnode.sig)
        csig = tnode.parent.sig
        tconts = _instances(tmpl, csig)
        pconts = _instances(page, csig)
        if not tconts or len(tconts) != len(pconts):
            present_t = sum(any(c.sig == tnode.sig for c in tc.children) for tc in tconts)
            if present_t:
                skipped.append(
                    f"{tnode.tag}.{tnode.cls}: container {csig[0]}.{csig[1]} "
                    f"count differs (template {len(tconts)} vs page {len(pconts)})"
                )
            continue
        for tcont, pcont in zip(tconts, pconts):
            telem = next((c for c in tcont.children if c.sig == tnode.sig), None)
            if telem is None or not telem.qid:
                continue
            if any(c.sig == tnode.sig for c in pcont.children):
                continue  # page already has this child
            value = labels.get(telem.qid, {}).get(language, "").strip()
            if not value:
                continue
            idx = _anchor_index(tcont, telem)
            if idx < 0:
                offset = pcont.open_end
                indent = page.line_indent(pcont.open_start) + "    "
            else:
                anchor_sig = tcont.children[idx].sig
                # occurrence of the anchor signature among tcont children before telem
                occ = sum(1 for c in tcont.children[:idx + 1] if c.sig == anchor_sig) - 1
                page_anchors = [c for c in pcont.children if c.sig == anchor_sig]
                if occ >= len(page_anchors):
                    continue
                anchor = page_anchors[occ]
                offset = anchor.close_start + len(anchor.tag) + 3 if anchor.close_start else anchor.open_end
                indent = page.line_indent(anchor.open_start)
            cls_attr = f' class="{telem.cls_raw}"' if telem.cls_raw else ""
            role_attr = f' role="{telem.role}"' if telem.role else ""
            markup = (
                f"\n{indent}<{telem.tag}{cls_attr}{role_attr}>"
                f"{html.escape(value, quote=False)}</{telem.tag}>"
            )
            insertions.append((offset, markup))
    return insertions, skipped


def apply_insertions(source: str, insertions: list[tuple[int, str]]) -> str:
    for offset, markup in sorted(insertions, reverse=True):
        source = source[:offset] + markup + source[offset:]
    return source


def repair(repo_root: Path, data_dir: Path, page: str, check: bool) -> int:
    labels = load_labels(data_dir)
    rows = [
        row for row in discover(repo_root)
        if row["abstract_path"] and (not page or row["page_qid"] == page)
    ]
    if page and not rows:
        raise ValueError(f"no abstract page declares QID {page}")

    changed: list[str] = []
    total_inserted = 0
    skipped_types: Counter[str] = Counter()
    for row in sorted(rows, key=lambda row: row["page_qid"]):
        tmpl = Tree((repo_root / row["abstract_path"]).read_text(encoding="utf-8"))
        for language in LANGUAGES:
            relative = row.get(f"target_{language}")
            if not relative or not (repo_root / relative).is_file():
                continue
            path = repo_root / relative
            source = path.read_text(encoding="utf-8")
            insertions, skipped = plan_page(tmpl, Tree(source), labels, language)
            for reason in skipped:
                skipped_types[f"{row['page_qid']} {reason}"] += 1
            if insertions:
                total_inserted += len(insertions)
                changed.append(relative)
                if not check:
                    path.write_text(apply_insertions(source, insertions), encoding="utf-8")

    if check:
        for relative in changed:
            print(f"WOULD REPAIR: {relative}")
    for reason, _ in sorted(skipped_types.items()):
        print(f"SKIP {reason}")
    action = "Would insert" if check else "Inserted"
    print(
        f"{action} {total_inserted} missing element(s) across {len(changed)} page(s); "
        f"{len(skipped_types)} container-mismatch type(s) skipped"
    )
    return 1 if (check and changed) else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--page", default="", help="restrict to a single abstract page QID")
    parser.add_argument("--check", action="store_true", help="report without writing")
    args = parser.parse_args(argv)
    try:
        return repair(args.repo_root.resolve(), args.data_dir.resolve(), args.page, args.check)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
