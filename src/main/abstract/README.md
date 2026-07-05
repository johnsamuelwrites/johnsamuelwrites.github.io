# Q315 Abstract Site

This directory is the reference area for the gradual conversion of Q315 into
the language-independent source of the site.

The intended direction is:

```text
local Wikibase + canonical Q315 HTML + QID-keyed functions
                              |
                              v
                      language renderer
                              |
                              v
              en / fr / ml / pa / hi / pt / es / it / ...
```

Q315 remains human-readable HTML. Its QIDs are not placeholders to be replaced
by an English master page: they are references to entities, messages, content
units, and functions. Language HTML and CSS are build products.

## Documents

- [architecture.md](architecture.md) defines authority, abstract HTML, function
  calls, translation, and CSS ownership.
- [development.md](development.md) proposes repository layout, validation, and
  the first executable pilot.
- [roadmap.md](roadmap.md) gives staged milestones and acceptance criteria.
- [decisions.md](decisions.md) records the initial architectural decisions that
  should remain stable while the implementation evolves.
- [querying.md](querying.md) defines the queryable Wikibase graph and example
  SPARQL shapes for abstract content.
- [content-migration.md](content-migration.md) defines the incremental,
  repository-wide migration of legacy English and French articles.
- [missing-content.md](missing-content.md) is the narrower operator guide for
  binding residual prose in Q315 pages that already exist.

## Current status

The existing scripts are valuable bootstrap tools. In particular, they align
the eight current languages, assign QIDs, create QuickStatements, and construct
the first abstract travel tree. During migration they should be treated as
importers and analysers. The target state is a renderer whose only article
composition input is Q315.

No existing generated page is declared disposable merely by this plan. A
collection becomes generated-only after it passes the round-trip and visual
checks described in the roadmap.

Repository-wide discovery is available through
`discover_content_migration.py`. It builds a generated registry rather than a
hand-written list. Pairing rules, content extraction, abstract authoring, and
collection cutover remain incremental implementation stages; the registry
does not pretend that unpaired legacy pages have already been migrated.

## Rendering language pages from Q315

Three tools drive the content round-trip from Q315, reading the canonical label
store at `src/main/abstract/data/labels-wikibase.csv` (the default `--data-dir`).

1. `fetch_wikibase_labels.py` rebuilds that label store directly from the
   Wikibase `wbgetentities` API. This replaces the SPARQL export
   (`all-multilingual-labels.rq`), which times out on the endpoint and returns
   partial, value-misaligned rows — it dropped bound items and shuffled labels
   between entities. Re-run it whenever Wikibase labels change:

   ```bash
   python3 src/main/abstract/fetch_wikibase_labels.py
   ```

2. `render_page.py` rewrites each bound `data-content`/`data-entity` text slot in
   the language pages to the entity's label, in place, and adds a `Q315 renderer`
   generator meta so ownership becomes `abstract`. A slot is only rewritten when
   the page holds the same number of same-signature elements as the template.

3. `repair_structure.py` inserts template-defined bound children a language page
   omits (e.g. a gallery-card's `card-description`), mapped positionally, only
   where the parent container count matches. Container-divergent pages (large
   index pages missing whole entries) are skipped for regeneration.

```bash
python3 src/main/abstract/render_page.py --check      # dry run
python3 src/main/abstract/render_page.py
python3 src/main/abstract/repair_structure.py
python3 src/main/abstract/verify_content_roundtrip.py
```

Both renderers take `--page QID` to scope to a single page. `verify_content_roundtrip.py`
is the completion gate; residual mismatches are structural and must be placed
inside their corresponding canonical containers, not appended elsewhere.
CI runs both renderers in `--check` mode and rejects any increase over the
documented 214-pair structural round-trip baseline. It also validates every
HTML document below `Q315/`; passing a directory to `validate_abstract_html.py`
discovers its HTML files recursively.

## Migrating pages linked by the Q315 home page

Home-page destinations must point to canonical Q315 documents once migrated;
do not leave an `../en/` link as the canonical destination. A migration creates
one abstract page item, links every concrete page through `P12`, adds all eight
`hreflang` alternates, and registers the canonical document in
`css-assets.json`. Inline CSS is extracted once to
`Q315/assets/css/pages/<QID>.css`; the Q315 document and all language renderings
reference that shared asset.

Machine-translated pages are drafts. Preserve native labels for curated
collections by adding their English source path to
`prepare_missing_content.NATIVE_LABEL_SOURCES`. This includes the Blogs I Read
collection: page chrome and explanatory prose are translated, while official
blog titles remain verbatim in every language.

Personal names are also invariant content. In particular, always preserve
`John Samuel` literally in every language: do not transliterate it or replace
it with localized forms such as `Juan Samuel`, `João Samuel`, or
`Giovanni Samuele`. Apply this rule to labels and full `P40` values, including
names embedded in titles, credits, speaker lists, and copyright sentences.

Official names can have a different authoritative source language from the
page being migrated. The teaching pages are the reference example: French is
authoritative for course names, while the English names are translations.
Inventory those names from the original French page before machine
translation, store the official French value in `P40` and the French label,
and bind every repeated occurrence to that item. Do not merge two course items
only because their English translations happen to match: “Chimie et
Numérique” and “Chimie et Informatique” intentionally remain distinct.

Generated HTML must retain a doctype, comments as comment nodes, and structural
indentation. Translation code must explicitly skip `Comment` and `Doctype`
nodes; treating them as ordinary text turns comments into visible page
content. Run the abstract HTML validator after formatting because formatting
must not alter bound slot signatures.

Reuse established localized routes before creating a filename. `index.html`
remains stable for collection roots; article filenames are localized (for
example `fr/recherche/recherche.html` and
`hi/भाषाविज्ञान/भाषा सीखना.html`). Record the localized path segment in `P38`
and the language-root-relative path in `P39`. Every concrete page and its Q315
document must expose the same eight routes in both `hreflang` metadata and a
visible footer language switcher.

Teaching links follow source ownership. English teaching pages retain their
original course links, which may lead onward to French slides. French teaching
pages retain the original official `cours/...` links. Course links in the
other six generated languages point to the corresponding English course page;
do not synthesize localized course directories that do not exist.

Run composed prose before atomic content preparation. Multi-sentence prose and
any single sentence whose monolingual value exceeds the Wikibase limit are
split into ordered parts and rendered with `compose_ordered_paragraph`.
`prepare_abstract_composition.py` keeps each generated part below 240
characters, leaving safety margin beneath both the 250-character label limit
used by atomic rendering and Wikibase's 400-character P40 limit.
Only residual atomic slots should then pass through
`prepare_missing_content.py` and `bind_reviewed_content.py`.

## Direct Wikibase bot

The generated QuickStatements can be validated and written directly through
the MediaWiki API. Validation is the default and does not require credentials:

```bash
python3 src/main/wikibase_write.py \
  /path/to/generated-batch.quickstatements
```

Create a dedicated bot password in the Wikibase user preferences, copy
`.env.example` to the ignored `.env`, fill in the two values, and explicitly
enable writes:

```bash
python3 src/main/wikibase_write.py \
  /path/to/generated-batch.quickstatements --apply
```

The writer supports the commands generated in this repository: `CREATE`,
`LAST`, labels, descriptions, aliases, item-valued claims, strings, URLs,
external IDs, Commons media, and monolingual text. It discovers property
datatypes before writing. A sibling `.state.json` file makes a stopped import
resumable; do not delete it until the batch has been checked. Use `--limit 1`
for a first live test. `.env` is ignored by Git and should have mode `0600`.
Environment values supplied by a secret manager or CI override `.env`. Avoid
putting passwords on command lines, in committed files, or in the normal
account password field; rotate the bot password if it is ever exposed.

Fetch selected entities or a complete item/property backup:

```bash
python3 src/main/wikibase_fetch.py --entity Q315 --entity Q3190 \
  --output /tmp/entities.json
python3 src/main/wikibase_fetch.py --all --output /tmp/wikibase.json
```

Both commands default to the repository's Wikibase Cloud instance. Use
`--api https://example.org/w/api.php` for another Wikibase.
