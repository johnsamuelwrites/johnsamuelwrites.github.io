# Residual Text Cleanup for Existing Q315 Pages

This is a narrow remediation workflow, not the repository-wide migration
pipeline. For migration of the thousands of existing English and French
articles, see [`content-migration.md`](content-migration.md).

This workflow converts remaining human-readable text in canonical Q315 pages
into reviewed local Wikibase content references. It currently covers:

- `Q315/index.html`;
- `Q315/Q3062/index.html`, including its language footer.

The canonical pages use `lang="zxx"`. Natural-language text belongs in the
local Wikibase and should appear in Q315 as a qualified reference such as
`data-content="local:Q4043"` with `Q4043` as the visible token.

## Prerequisites

The sibling `Q42761025` repository must contain current Wikibase exports:

```text
../Q42761025/data/abstract-content-items.csv
../Q42761025/data/abstract-content-values.csv
../Q42761025/data/labels-wikibase.csv
```

Each canonical page must also declare all eight supported `hreflang`
alternates:

```text
en fr ml pa hi pt es it
```

The pages to check are discovered from the repository itself: every page under
`Q315/` that declares `data-abstract-page`. There is no hand-maintained page
list, and this is not a registry for all legacy articles. Scope the run to one
page with `--page Q3062` when needed.

## 1. Generate the inventory

Run:

```bash
python src/main/abstract/prepare_missing_content.py
```

This creates three ignored working files:

```text
src/main/abstract/missing-content-review.csv
src/main/abstract/missing-content.quickstatements
src/main/abstract/missing-content-partial.quickstatements
```

The generator:

1. reads each discovered canonical page;
2. discovers its localized pages from `hreflang`;
3. collects direct user-facing text;
4. skips existing `data-content` bindings and QID-only values;
5. keeps external service names out of prose extraction; they are handled
   separately as reusable local entities;
6. resolves links to local `Q….html` pages as entity references;
7. compares multilingual values with the offline Wikibase exports;
8. prepares separate deduplicated imports for complete items and for partial
   items that currently have at least English and French.

Complete items can move through the eight-language review immediately.
Partial items follow the site-wide migration rule: import known `en`/`fr`
values and track other languages as a translation backlog. Review partial
items especially carefully because structurally divergent legacy pages can
expose alignment errors.

Never edit `missing-content.quickstatements` as the source of truth. Correct
translations in the localized pages or review data, then regenerate it.

## 2. Review the inventory

`missing-content-review.csv` identifies a DOM slot with:

```text
page, path, tag, class, role, occurrence
```

It also contains `status`, `qid`, candidate QIDs, an import `token`, the
canonical text, and the eight localized values.

Interpret statuses as follows:

| Status | Required action |
| --- | --- |
| `existing-exact` | Verify the QID; no import is required. |
| `existing-link-entity` | Verify that the link target is the intended entity. |
| `existing-import-token` | The stable import token resolved to its returned QID. |
| `existing-english-review` | Compare all translations before accepting the proposed QID. |
| `ambiguous-review` | Select the intended QID from `candidates`; never choose by English label alone. |
| `missing-ready` | Review the eight values; the item is included in QuickStatements. |
| `missing-translations` | Supply or correct missing translations before importing. |

Review semantic identity, not merely spelling. Repeated phrases may require
different items when their meaning or translations differ. Conversely, rows
sharing the same `M…` token represent one deduplicated multilingual item and
must ultimately share one QID.

`M…` tokens are stable hashes used only by the local review manifest.
Refreshing Wikibase exports or resolving another row does not renumber
unrelated tokens. They must never be used as public Wikibase labels: imported
items receive their real localized text as labels.

## 3. Import missing items

Inspect every block in `missing-content.quickstatements`, then import it into
the local Wikibase instance.

`missing-content-partial.quickstatements` is a separate import batch. Import it
only after verifying each available value against its page context. Missing
languages are deliberately absent from `P40`; never insert an English fallback
as though it were a translation.

Machine-assisted values for languages such as Malayalam, Punjabi, and Hindi
must be held for human review before they are merged into an eight-language
import. Do not import a draft translation merely because the QuickStatements
syntax validates; linguistic review remains a separate requirement.

Each block:

- creates one item;
- gives it a temporary English token label;
- adds one `P40` monolingual content value per supported language;
- describes it as an abstract-page content component;
- assigns `P8|Q3185`, the configured content-item type.

Do not import rows with unresolved ambiguity or incomplete translations.

Record the QID returned for every `M…` token. In
`missing-content-review.csv`, place that QID in the `qid` column of every row
carrying the token. Also fill reviewed QIDs for ambiguous rows. A blank `qid`
means "do not bind".

## 4. Bind reviewed QIDs

Preview whether binding work remains:

```bash
python src/main/abstract/bind_reviewed_content.py --check
```

Apply the reviewed bindings:

```bash
python src/main/abstract/bind_reviewed_content.py
```

For each row with a QID, the binder adds the qualified `data-content`
reference and replaces visible prose with the QID. It leaves unreviewed rows
unchanged and refuses malformed QIDs.

Review the resulting Git diff before continuing.

## 5. Validate

Validate the abstract HTML contract:

```bash
python src/main/abstract/validate_abstract_html.py \
  Q315/index.html Q315/Q3062/index.html
```

Run the focused tests:

```bash
python -m pytest \
  src/test/test_missing_abstract_content.py \
  src/test/test_travel_manifest_binding.py \
  src/test/test_abstract_renderer.py
```

Then refresh the Wikibase exports and regenerate the inventory. Successfully
imported content should resolve as `existing-exact`; this round-trip is the
completion check.

## Safety and recovery

- Generated review and QuickStatements files are deliberately ignored by Git.
- The committed canonical HTML is changed only by the binding command.
- `--check` never writes HTML.
- Keep the review CSV until imported tokens have been reconciled with QIDs.
- If a binding is wrong, correct its QID in the review CSV and rerun the
  binder. It can update bindings that it owns.
- Do not manually replace translated pages during this process. They remain
  translation inputs and review material until renderer ownership is enabled.
