# Repository-wide Content Migration

This document defines the migration of the existing `en/` and `fr/` site into
canonical abstract pages under `Q315/`, followed by rendering into all
configured languages. It is the site-wide workflow. The residual-text utility
described in `missing-content.md` is only a cleanup tool for Q315 pages that
already exist.

## Scope and principles

The migration must handle thousands of articles incrementally. It must not
require the whole site, or all eight translations, to be complete before one
page can move.

During migration there are two different kinds of source:

- legacy `en/` and `fr/` pages are read-only migration inputs;
- after cutover, Q315 composition, Wikibase content, functions, and canonical
  CSS are the only rendering authorities.

English is not the permanent master language. English and French are evidence
used to identify structure and seed multilingual content. Once a page is
cut over, neither rendered page may be read back as an authoring source.

Every operation must be deterministic, resumable, scoped by collection, and
safe to rerun.

## Migration registry

A generated registry must contain one row per logical article, not one row per
physical language file. At minimum it records:

```text
page_qid
collection_qid
abstract_path
en_source
fr_source
target_en
target_fr
target_ml
target_pa
target_hi
target_pt
target_es
target_it
template_family
migration_state
source_hashes
```

`page_qid` is the stable identity. Paths are routing information and may
change. A missing source or target path is represented explicitly rather than
by shifting positional columns.

The registry is discovered from the repository and reconciled with Wikibase.
It must not be maintained as a hand-written list of thousands of pages.
Small committed configuration files may define collection roots, exclusions,
route transformations, and template families.

The first repository-wide discovery command is implemented:

```bash
python src/main/abstract/discover_content_migration.py
```

It writes the ignored `src/main/abstract/content-migration-registry.csv`.
Discovery currently pairs pages through reciprocal/reverse `hreflang` links
and connects them to Q315 through the abstract page's alternates. Unpaired
legacy pages remain explicit `unpaired` rows; later route rules or reviewed
identity mappings must resolve them. The command does not guess from titles or
translated directory names.

Discovery, verification, inventory and round-trip all key on the
`data-abstract-page="local:Q…"` declaration on a canonical page's `<html>`
element. A page authored without it is invisible to the whole pipeline even
when it already carries complete alternates and bindings, so its legacy
alternates stay `unpaired`. The page QID is the identity already encoded in the
page's own path under `Q315/`, so it is stamped rather than guessed:

```bash
python src/main/abstract/bind_abstract_page_qids.py --check   # report only
python src/main/abstract/bind_abstract_page_qids.py           # stamp
```

The tool derives `Q3027` from `Q315/Q3062/Q3027.html`, `Q3062` from
`Q315/Q3062/index.html`, and `Q315` from `Q315/index.html`. It refuses any
collision or a declaration that disagrees with the path, is idempotent, and
changes nothing else in the document. Run it before discovery whenever new
canonical pages are added.

Recommended migration states are:

```text
discovered
identity-reviewed
structure-aligned
content-inventoried
content-imported
abstract-authored
render-verified
generated-owner
```

State transitions are monotonic unless a source hash changes. A changed legacy
input invalidates downstream checks for that page without discarding reviewed
QID assignments.

## 1. Discover and pair legacy pages

Crawl configured `en/` and `fr/` roots and collect:

- canonical URL and relative path;
- existing QIDs and RDFa metadata;
- `hreflang` and internal links;
- title, headings, semantic regions, and template fingerprint;
- CSS, scripts, media, and accessibility text;
- a normalized content hash.

Pair English and French pages by stable identity in this order:

1. an existing local page QID;
2. reciprocal `hreflang` or canonical links;
3. an explicit reviewed route mapping;
4. a high-confidence structural and link match queued for human review.

Never pair pages only because their filenames or titles look similar. Report
unpaired English pages, unpaired French pages, duplicate identities, broken
alternates, and route collisions separately.

Discovery produces reports; it does not modify HTML.

## 2. Group pages into template families

Migration is performed by collection and template family rather than as
thousands of unrelated page conversions. A family describes stable semantic
slots such as:

```text
article title
lead paragraph
ordered article sections
figure and caption
related links
language navigation
collection footer
```

DOM position alone is not a stable identifier. English and French pages may
have missing links, reordered sections, or language-specific wrappers.
Alignment uses semantic IDs, QIDs, link targets, heading hierarchy, RDFa,
classes within a known template, and reviewed exceptions. Occurrence numbers
are a last-resort locator local to one template version.

Shared navigation, language names, licenses, and footer messages are imported
once and reused across every family.

## 3. Establish page and section identity

Each logical article receives or reuses a local page QID. Reusable sections,
entities, media, and links reuse existing QIDs when their semantic identity is
the same.

Identity review distinguishes:

- an entity label, such as a place or person;
- an interface message, such as "Skip to main content";
- an article-specific sentence or paragraph;
- a composed result produced by a function;
- a proper external service name, which may remain literal.

For this site, the migration adopts the stricter policy that recurring external
service names are local reusable entities too. Their outbound profile URLs
remain ordinary link attributes; the visible service label is resolved from
the local QID.

Text equality is evidence, not identity. Two identical phrases can have
different meanings, while differently worded translations can represent the
same content item.

A link has two independent identities: its destination and its visible
message. An action such as "Read more about me" is a content item; it must not
be replaced by the shorter label of the About-page entity merely because the
link targets that page.

## 4. Inventory and import content units

For each aligned semantic slot:

1. search the pinned Wikibase exports for an exact multilingual match;
2. search for candidate entities or content items and require review when
   ambiguous;
3. reuse a reviewed QID;
4. otherwise create a new content item with the translations currently known.

New items may initially contain only `en` and `fr` `P40` values. Missing
Malayalam, Punjabi, Hindi, Portuguese, Spanish, or Italian values are a
translation backlog, not a reason to block abstract authoring.

Split content at a semantic translation boundary:

- keep a sentence atomic when it is translated as a unit;
- keep an indivisible paragraph atomic when necessary;
- compose ordered sentences when reuse or language-specific order benefits;
- use function calls for language-aware lists, punctuation, dates, and
  grammatical variation.

Import files are deduplicated by normalized multilingual value and reviewed
semantic identity. Temporary tokens are reconciled with returned Wikibase
QIDs before Q315 is edited.

## 5. Author the Q315 page

Create the canonical page at its registered `abstract_path`. It contains:

- `lang="zxx"`;
- `data-abstract-page="local:Q…"` and the contract version;
- semantic article structure and ordering;
- qualified `data-entity` and `data-content` references;
- QID-keyed function calls where composition is required;
- canonical CSS and media references;
- target-language alternates derived from the registry.

Q315 contains no readable fallback prose. Diagnostic annotations, if needed,
must be explicitly marked and ignored by the renderer.

The authoring step writes only Q315 and migration manifests. It never updates
legacy language pages.

## 6. Build the translation backlog

Generate a matrix keyed by `(content_qid, language)` containing:

```text
content_qid
page_qids_using_it
source_context
language
status
current_value
reviewer
wikibase_revision
```

Suggested statuses are `missing`, `draft`, `reviewed`, and `published`.
Context is essential: translators need the article, semantic slot, neighboring
content, and media—not merely an isolated English string.

The matrix deduplicates shared content automatically. Translating a reused
footer message or section title once completes it for every dependent page.

## 7. Render without silent fallback

The renderer operates per page, collection, language, or changed dependency.
It reads only:

- the Q315 page;
- a pinned Wikibase snapshot;
- the function registry;
- locale data;
- canonical CSS and media metadata.

Two build policies are useful:

- preview builds may render a visibly marked fallback and emit diagnostics;
- release builds fail for any required translation that is not `published`.

An English/French-only migrated page can therefore be authored and previewed
immediately. It becomes releasable in another language when that page's
dependency closure is translated—not when the entire site is translated.

## 8. Verify and cut over one page

Before generated ownership:

1. validate the abstract contract and all QID dependencies;
2. render into a temporary output tree;
3. compare semantic DOM with the legacy English and French pages;
4. compare links, metadata, accessibility, media, and canonical CSS;
5. take visual snapshots at representative viewport sizes;
6. obtain language review for every output being released;
7. regenerate twice and require byte-identical output.

Only then replace the selected language outputs and mark the page
`generated-owner`. Other pages remain legacy-owned. Cutover is page-scoped and
reversible through version control.

After cutover, CI rejects manual edits or stale generated output for that page.

Generated ownership is machine-readable. Rendered pages carry:

```html
<meta name="generator" content="Q315 renderer">
```

The discovery registry then sets `render_ownership=abstract`, changes the
migration state to `generated-owner`, and leaves `en_source` and `fr_source`
empty. Their paths remain only in `target_en` and `target_fr`. This is the
enforced transition from temporary English/French migration input to direct
Q315-to-language rendering.

## 9. Operate at repository scale

Run the pipeline in bounded shards:

```text
collection → template family → page batch → language
```

Cache work by source hash, Q315 hash, Wikibase revision, function-registry
version, renderer version, and CSS dependency hash. Rebuild only pages whose
dependency closure changed.

Every run emits aggregate coverage:

- discovered, paired, and unpaired legacy pages;
- pages in each migration state;
- literal Q315 prose remaining;
- resolved and unresolved QIDs;
- translation coverage by language and collection;
- pages blocked from release and the exact dependencies responsible;
- generated pages that have drifted.

Reports may be large generated artifacts. Commit compact configuration,
reviewed overrides, schemas, and tests; do not commit volatile full-site
inventories unless they are intentionally used as release manifests.

## 10. Collection rollout

For each collection:

1. select a representative pilot from its dominant template family;
2. define route and structure rules;
3. migrate and visually approve the pilot;
4. process a small batch and review every page;
5. automate high-confidence pages;
6. route exceptions to a review queue;
7. enable generated ownership page by page;
8. keep measuring untranslated dependencies until all target languages can be
   released.

Travel is the first collection, not a special architecture. The same registry,
content-item model, renderer contract, translation matrix, and cutover states
must apply to articles, teaching material, research pages, writings,
linguistics, blog entries, and future collections.

## Relationship to residual cleanup

`prepare_missing_content.py` inventories literal text in the abstract pages
discovered from the repository and requires each page's eight current
alternates. It is useful for fixing residual prose in already-authored pages
such as the home page and travel footer, but it is not the legacy-site
discovery or migration engine described here.

As the repository-wide tooling is implemented, it should provide separate
commands for:

```text
discover legacy pages
pair and review identities
inventory content
prepare Wikibase imports
reconcile imported QIDs
author or validate Q315
report translation coverage
render previews
verify and cut over
```

Keeping these stages separate prevents a footer-cleanup script from silently
becoming the migration authority for thousands of articles.

## Verifying migrated pages

The verifier operates on the discovered abstract pages themselves; there is no
committed page list. Every page under `Q315/` that declares
`data-abstract-page` is included automatically, so a newly authored page is
covered without editing a hand-written batch file. Once
`bind_abstract_page_qids.py` has stamped the identities, this is every
canonical page under `Q315/`, not a hand-picked pair.

Run the structural pipeline check for every abstract page with:

```bash
python src/main/abstract/verify_content_migration.py
```

Restrict it to a single page with `--page Q3062`. Generate the import material
for the same registry-derived pages with:

```bash
python src/main/abstract/prepare_missing_content.py
```

That writes the ignored `missing-content-review.csv`,
`missing-content.quickstatements`, and `missing-content-partial.quickstatements`.
The complete file contains items with all eight `P40` values; the partial file
contains items with at least English and French and deliberately omits missing
languages. The review CSV provides the token-to-page-slot reconciliation needed
after Wikibase returns real QIDs. Use `--page` to scope any of these to one page.

The check uses the repository-wide discovery registry, verifies one logical row
per abstract page, requires temporary English/French sources while legacy-owned,
requires all eight target paths, validates the abstract HTML contract, and runs
the multilingual content inventory. It writes the ignored
`content-migration-report.json`.

A structurally valid pipeline may still report unresolved content. This is the
expected import/review queue, not a hidden success. To use it as a cutover
gate, run:

```bash
python src/main/abstract/verify_content_migration.py --release-ready
```

That stricter command fails until every ambiguous, proposed, missing, or
import-ready content slot has been reconciled to Wikibase and the regenerated
inventory is exact. It also runs `verify_content_roundtrip.py`, which requires
every resolved label to occur in the corresponding existing language page.
QID coverage without round-trip equivalence is not release-ready. After
rendering is enabled for the complete pages, the same check must also observe
`generated-owner`, blank legacy source fields, and language paths retained
solely as targets.

## Correcting already-bound content

The round-trip verifier reports *that* a binding fails to reproduce a page. It
does not say what the page shows instead, and it cannot tell a genuinely wrong
translation apart from a language page that never had the slot. That
reconciliation is a separate command:

```bash
python src/main/abstract/prepare_content_corrections.py
```

It aligns every already-bound slot to its slot in each language page and
classifies the difference into `content-corrections-review.csv`:

| Status | Meaning | Action |
| --- | --- | --- |
| `match` | stored value equals the page value | none |
| `differs` | the page renders a different non-empty value | correct or review |
| `wikibase-missing` | the item has no value for a language the page shows | add from evidence |
| `page-absent` | the language page lacks the slot entirely | page-completeness backlog; never a Wikibase edit |
| `page-degraded` | the page value is a corrupted rendering (replacement character or `?` for an accent) | fix the page, not Wikibase |

Only a small, defensible subset reaches
`content-corrections.quickstatements`. Occurrence-based slot keys drift between
structurally divergent language pages, so a correction is emitted only when

- English confirms the alignment (the item's stored English equals the English
  page value at that slot), and
- the page value is the *same content up to typography* (case, accent, spacing,
  punctuation). A wholly different string is occurrence drift, not a
  translation fix, and stays review-only.

Additions are refused when the page merely echoes the English text, since that
is an untranslated page rather than a translation. Nothing overwrites a good
Wikibase value with an absent or damaged page value. As with every generator
here, the QuickStatements are reviewed material and are imported by hand.
