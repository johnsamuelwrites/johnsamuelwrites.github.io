#!/usr/bin/env python3
"""Run every CI check, several at a time.

The checks read the repository and never write to it (the round-trip report
goes to a temporary directory), so they are independent and run in parallel,
one per CPU. Each check's output is printed whole, in a collapsible group on
GitHub Actions, followed by a summary; the run fails if any check fails.

Usage:
    python src/main/ci_checks.py                 # everything, as CI runs it
    python src/main/ci_checks.py --list          # the check names
    python src/main/ci_checks.py links footer    # only these
    python src/main/ci_checks.py --jobs 1        # one at a time
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir())
GITHUB = os.environ.get("GITHUB_ACTIONS") == "true"


@dataclass(frozen=True)
class Check:
    name: str
    title: str
    command: tuple[str, ...]


# Listed slowest first, so the long checks start before the short ones fill in
# around them.
CHECKS = (
    Check("unit", "Unit tests", ("-m", "unittest", "discover", "-s", "src/test", "-p", "test_*.py")),
    # Covers every HTML file, Q315 included, so a changed-files pass or a
    # separate Q315 pass would only repeat part of it.
    Check("links", "Internal broken links across the whole site",
          ("src/main/ci_internal_links.py", "--all", "--tracked")),
    # Ratchet: only ever lower this budget as page-language pairs are made
    # reproducible from their abstract bindings. It reaches 0 when every
    # rendered page round-trips. Lowered 214 -> 70 after Q3640 (books) was
    # aligned across all 8 languages; -> 68 after the es Teaching
    # ("Enseñanza") pages were reconciled; -> 60 after Q3646 (detailed CV)
    # labels were aligned to the published page text across all 8 languages;
    # -> 59 after the pt travel-index research breadcrumb ("Pesquisa") was
    # reconciled with its siblings; -> 0 after structurally divergent legacy
    # slots were unbound from Q315 ownership pending full page migration.
    Check("roundtrip", "Q315 round-trip has no regressions",
          ("src/main/abstract/verify_content_roundtrip.py", "--max-mismatches", "0",
           "--report", str(REPORT_DIR / "q315-content-roundtrip.json"))),
    Check("render", "Rendered Q315 labels are current", ("src/main/abstract/render_page.py", "--check")),
    Check("repair", "Q315 structural repairs are current", ("src/main/abstract/repair_structure.py", "--check")),
    # Every page rendered from Q315 must carry exactly one styled language
    # switcher (the travel "langlist" grid or the section "lang-selector"
    # buttons) linking all its languages including itself, current one
    # highlighted, with no duplicate or bare language-switcher nav. The budget
    # is a ratchet: only ever lower it as the remaining section pages are
    # fixed; it reaches 0 when every Q315 page conforms.
    Check("footer", "Every Q315 page has one language-switcher footer",
          ("src/main/abstract/verify_language_footer.py", "--max-failing-pages", "0")),
    Check("rendered", "Rendered Q315 prose and links", ("src/main/abstract/validate_rendered_pages.py",)),
    # Q315 templates are built from the English page, so derived language
    # pages inherit ../../en/ hrefs that render_page.py never rewrites. A
    # link into another language's tree is allowed only when no counterpart
    # exists, or when it is marked deliberate (hreflang/lang, a switcher).
    # Fix with: python src/main/abstract/localize_links.py
    Check("localize", "Translated pages link to their own language", ("src/main/abstract/localize_links.py", "--check")),
    Check("css", "Canonical abstract CSS references", ("src/main/abstract/css_assets.py", "check")),
    # A literal in an abstract page (English text in an element, or in an
    # attribute the page displays, such as a gallery caption shown with CSS
    # attr()) reaches every language page untranslated, and no other check
    # sees it. The budget is a ratchet: 783 literals when the check was
    # added; -> 734 after the 49 data-city gallery captions were bound;
    # -> 539 after the 195 teaching-archive course and intervention lines
    # were bound; -> 55 once paths, titles marked lang, names marked
    # translate="no", the registry titles and the license line were done;
    # -> 48 after labels with existing items (Cities, About me, regions);
    # -> 18 after more labels were bound and the research pages' official
    # names (address, degrees, job titles, co-authors) marked translate="no";
    # -> 16 after the footers' author name was marked as a name too;
    # -> 0 once the last labels, intros and paragraphs were bound. Keep it
    # at 0: any new literal on a Q315 page now fails CI.
    Check("literals", "Q315 pages carry QIDs, not natural-language literals",
          ("src/main/abstract/verify_abstract_literals.py", "--max-literals", "0")),
    Check("abstract", "Every canonical Q315 document", ("src/main/abstract/validate_abstract_html.py", "Q315")),
    # Validates every CSV in data/content-updates and asserts that applying it
    # to its Q315 abstract source would be a no-op. Not a ratchet: it starts at
    # zero drift and must stay there. A failure means a CSV row was added or
    # edited without running --mode q315-apply and re-rendering.
    Check("csv-sync", "Content-update CSVs are in sync with their Q315 sources",
          ("src/main/content_update.py", "--mode", "check")),
    # Both directions: a CSV row whose QID is on no source, and a QID bound
    # on a source that no CSV row claims. Catches entries added to a source
    # by hand and CSV columns that point at nothing -- neither of which
    # --mode check can see, because it only asks whether applying the CSV
    # would change the source.
    Check("csv-diff", "CSV and Q315 sources bind the same content items",
          ("src/main/content_update.py", "--mode", "diff")),
    # The list pages are legacy documents that render_page.py does not
    # regenerate, so nothing else notices when one language drifts. This
    # compares the languages against each other and against the CSV, and
    # catches the duplicate entries the retired apply path used to append.
    Check("parity", "Every language page of a family carries the same entries",
          ("src/main/content_update.py", "--mode", "parity")),
    # Each year's course introduction page in fr/enseignement/cours/ and its
    # English page in en/teaching/courses/, and every group listed in
    # src/main/abstract/data/language-groups.csv, must link to each other
    # (head alternates + a visible link). An English course page must not
    # keep pointing at last year's French material after the rollover.
    # Fix with: python src/main/link_language_pairs.py --apply
    Check("pairs", "Legacy pages link to their translations", ("src/main/link_language_pairs.py", "--check")),
)


@dataclass
class Result:
    check: Check
    returncode: int
    output: str
    seconds: float


def run(check: Check) -> Result:
    start = time.monotonic()
    completed = subprocess.run(
        [sys.executable, *check.command],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return Result(check, completed.returncode, completed.stdout, time.monotonic() - start)


def report(result: Result) -> None:
    status = "ok" if result.returncode == 0 else f"FAILED (exit {result.returncode})"
    heading = f"{result.check.title} [{result.check.name}] - {status} in {result.seconds:.1f}s"
    if GITHUB:
        print(f"::group::{heading}")
        print(result.output, end="" if result.output.endswith("\n") else "\n")
        print("::endgroup::")
        if result.returncode:
            print(f"::error title={result.check.title}::{result.check.name} failed; expand its group above")
    else:
        print(f"=== {heading}")
        if result.returncode:
            print(result.output, end="" if result.output.endswith("\n") else "\n")
    sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", help="run only these checks (see --list)")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1, help="checks run at once (default: CPUs)")
    parser.add_argument("--list", action="store_true", help="print the check names and exit")
    args = parser.parse_args()

    if args.list:
        for check in CHECKS:
            print(f"{check.name:10} {check.title}")
        return 0
    known = {check.name for check in CHECKS}
    unknown = sorted(set(args.names) - known)
    if unknown:
        parser.error(f"unknown check(s): {', '.join(unknown)}; see --list")
    selected = [check for check in CHECKS if not args.names or check.name in args.names]

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        results = list(pool.map(run, selected))
    for result in results:
        report(result)

    failed = [result for result in results if result.returncode]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed in {time.monotonic() - start:.1f}s")
    for result in sorted(results, key=lambda result: -result.seconds):
        mark = "FAIL" if result.returncode else "ok"
        print(f"  {mark:4} {result.seconds:5.1f}s  {result.check.name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
