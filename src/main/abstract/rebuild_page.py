#!/usr/bin/env python3
"""Rebuild one rendered language page from its canonical Q315 abstract page."""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from abstract.css_assets import DEFAULT_DATA_DIR, DEFAULT_REPO_ROOT
from abstract.discover_content_migration import discover
from abstract.prepare_travel_content import LANGUAGES, TEXT_TAGS
from abstract.render_page import GENERATOR_META


def load_labels(data_dir: Path) -> dict[str, dict[str, str]]:
    with (data_dir / "labels-wikibase.csv").open(encoding="utf-8-sig", newline="") as source:
        return {row["identifier"]: row for row in csv.DictReader(source)}


def class_values(tag: Tag) -> list[str]:
    values = tag.get("class", [])
    if isinstance(values, str):
        return values.split()
    return [str(value) for value in values]


def set_classes(tag: Tag, values: list[str]) -> None:
    if values:
        tag["class"] = values
    elif tag.has_attr("class"):
        del tag["class"]


def qid_from_local(value: str) -> str:
    match = re.fullmatch(r"local:(Q[1-9][0-9]*)", value.strip())
    return match.group(1) if match else ""


def concrete_target_map(rows: list[dict[str, str]], language: str) -> dict[Path, Path]:
    result: dict[Path, Path] = {}
    for row in rows:
        abstract = row.get("abstract_path", "")
        target = row.get(f"target_{language}", "")
        if abstract and target:
            result[Path(abstract)] = Path(target)
    return result


def rebase_link(
    href: str,
    *,
    repo_root: Path,
    abstract_path: Path,
    target_path: Path,
    abstract_targets: dict[Path, Path],
) -> str:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or href.startswith("#") or not parsed.path:
        return href
    resolved = (repo_root / abstract_path).parent / unquote(parsed.path)
    try:
        relative = resolved.resolve().relative_to(repo_root)
    except ValueError:
        return href
    destination = abstract_targets.get(relative, relative)
    rebased = os.path.relpath(repo_root / destination, (repo_root / target_path).parent)
    rebased = Path(rebased).as_posix()
    if parsed.query:
        rebased += f"?{parsed.query}"
    if parsed.fragment:
        rebased += f"#{parsed.fragment}"
    return rebased


def rebase_links(
    soup: BeautifulSoup,
    *,
    repo_root: Path,
    abstract_path: Path,
    target_path: Path,
    abstract_targets: dict[Path, Path],
) -> None:
    for tag_name, attr in (("a", "href"), ("link", "href"), ("script", "src"), ("img", "src")):
        for tag in soup.find_all(tag_name):
            if not isinstance(tag, Tag) or not tag.get(attr):
                continue
            tag[attr] = rebase_link(
                str(tag[attr]),
                repo_root=repo_root,
                abstract_path=abstract_path,
                target_path=target_path,
                abstract_targets=abstract_targets,
            )


def render_content_slots(
    soup: BeautifulSoup,
    labels: dict[str, dict[str, str]],
    language: str,
) -> None:
    for tag in soup.find_all(attrs={"data-content": True}):
        if not isinstance(tag, Tag):
            continue
        qid = qid_from_local(str(tag.get("data-content", "")))
        label = labels.get(qid, {}).get(language, "").strip()
        if not qid or not label:
            continue
        if tag.find(True):
            continue
        if tag.name in TEXT_TAGS:
            tag.string = label
        del tag["data-content"]


def render_bare_qids(
    soup: BeautifulSoup,
    labels: dict[str, dict[str, str]],
    language: str,
) -> None:
    pattern = re.compile(r"\bQ[1-9][0-9]*\b")
    for node in soup.find_all(string=pattern):
        if not isinstance(node, NavigableString):
            continue
        parent = node.parent
        if not isinstance(parent, Tag) or parent.name in {"script", "style"}:
            continue
        text = str(node)
        stripped = text.strip()
        if not re.fullmatch(r"Q[1-9][0-9]*", stripped):
            continue
        label = known_bare_qid_label(stripped, language)
        if not label:
            label = labels.get(stripped, {}).get(language, "").strip()
        if label:
            node.replace_with(text.replace(stripped, label))


def known_bare_qid_label(qid: str, language: str) -> str:
    if qid == "Q42761025":
        return "John Samuel"
    if qid == "Q315":
        return {
            "fr": "Accueil",
            "ml": "മുഖ്യ താൾ",
            "pa": "ਮੁੱਖ ਪੰਨਾ",
            "hi": "मुख्य पृष्ठ",
            "pt": "Início",
            "es": "Inicio",
            "it": "Home",
        }.get(language, "Home")
    return ""


def set_language_state(soup: BeautifulSoup, language: str) -> None:
    html = soup.find("html")
    if isinstance(html, Tag):
        html["lang"] = language
        for attr in ("data-abstract-page", "data-abstract-version"):
            if html.has_attr(attr):
                del html[attr]
    meta = soup.find("meta", attrs={"http-equiv": re.compile("^Content-Language$", re.I)})
    if isinstance(meta, Tag):
        meta["content"] = language
    for tag in soup.select(".highlight, .active"):
        if not isinstance(tag, Tag):
            continue
        classes = [value for value in class_values(tag) if value not in {"highlight", "active"}]
        set_classes(tag, classes)
    for tag in soup.find_all(["li", "a"]):
        if not isinstance(tag, Tag):
            continue
        classes = class_values(tag)
        if str(tag.get("id", "")) == f"{language}page":
            classes.append("highlight")
        if str(tag.get("hreflang", "") or tag.get("lang", "")) == language:
            classes.append("active")
        set_classes(tag, list(dict.fromkeys(classes)))


def inject_generator(soup: BeautifulSoup) -> None:
    head = soup.find("head")
    if not isinstance(head, Tag):
        return
    existing = soup.find("meta", attrs={"name": "generator", "content": "Q315 renderer"})
    if isinstance(existing, Tag):
        return
    generator = BeautifulSoup(GENERATOR_META, features="html.parser").find("meta")
    if generator:
        head.insert(0, generator)


def rebuild_html(
    abstract_html: str,
    *,
    page_qid: str,
    language: str,
    labels: dict[str, dict[str, str]],
    repo_root: Path,
    abstract_path: Path,
    target_path: Path,
    abstract_targets: dict[Path, Path],
) -> str:
    soup = BeautifulSoup(abstract_html, features="html.parser")
    set_language_state(soup, language)
    inject_generator(soup)
    title = soup.find("title")
    page_label = labels.get(page_qid, {}).get(language, "").strip() or page_qid
    author = labels.get("Q42761025", {}).get(language, "").strip() or "John Samuel"
    if isinstance(title, Tag):
        title.string = f"{page_label}: {author}"
    rebase_links(
        soup,
        repo_root=repo_root,
        abstract_path=abstract_path,
        target_path=target_path,
        abstract_targets=abstract_targets,
    )
    render_content_slots(soup, labels, language)
    render_bare_qids(soup, labels, language)
    return restore_svg_case(str(soup))


def restore_svg_case(source: str) -> str:
    replacements = {
        "lineargradient": "linearGradient",
        "radialgradient": "radialGradient",
        "clippath": "clipPath",
        "fegaussianblur": "feGaussianBlur",
        "fedropshadow": "feDropShadow",
        "femerge": "feMerge",
        "femergenode": "feMergeNode",
        "viewbox": "viewBox",
        "preserveaspectratio": "preserveAspectRatio",
        "stddeviation": "stdDeviation",
        "gradientunits": "gradientUnits",
        "gradienttransform": "gradientTransform",
    }
    for old, new in replacements.items():
        source = re.sub(rf"(?<=<){old}\b", new, source)
        source = re.sub(rf"(?<=</){old}\b", new, source)
        source = re.sub(rf"\b{old}=", f"{new}=", source)
    return source


def rebuild(repo_root: Path, data_dir: Path, page: str, language: str, check: bool) -> int:
    if language not in LANGUAGES:
        raise ValueError(f"unsupported language: {language}")
    rows = discover(repo_root)
    matches = [row for row in rows if row["page_qid"] == page and row["abstract_path"]]
    if len(matches) != 1:
        raise ValueError(f"expected one abstract page for {page}, found {len(matches)}")
    row = matches[0]
    target = row.get(f"target_{language}", "")
    if not target:
        raise ValueError(f"{page} has no target for {language}")
    abstract_path = Path(row["abstract_path"])
    target_path = Path(target)
    labels = load_labels(data_dir)
    output = rebuild_html(
        (repo_root / abstract_path).read_text(encoding="utf-8"),
        page_qid=page,
        language=language,
        labels=labels,
        repo_root=repo_root,
        abstract_path=abstract_path,
        target_path=target_path,
        abstract_targets=concrete_target_map(rows, language),
    )
    current = (repo_root / target_path).read_text(encoding="utf-8")
    if output == current:
        print(f"unchanged: {target}")
        return 0
    if check:
        print(f"STALE: {target}")
        return 1
    (repo_root / target_path).write_text(output, encoding="utf-8")
    print(f"rebuilt: {target}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--page", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        return rebuild(
            args.repo_root.resolve(),
            args.data_dir.resolve(),
            args.page,
            args.language,
            args.check,
        )
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
