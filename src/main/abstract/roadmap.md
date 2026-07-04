# Roadmap

## Implementation status

The travel CSS migration is complete. All 156 abstract pages beneath
`Q315/Q3062`, including nested country and city pages, own canonical
stylesheets under `Q315/assets/css/`. Their eight language renderings reference
those assets rather than embedding copies. Collection discovery and CI
validation automatically include future travel pages exposed through all eight
`hreflang` links.

The first abstract-content pilot targets the Q3062 hero description. The
versioned HTML contract, qualified-QID validator, typed monolingual-text value,
function registry, concatenate implementation, complete eight-language sentence
set, and QuickStatements preparation workflow are implemented. Q315 now contains
the production function call, and `render_abstract.py` deterministically renders
the composed paragraph from a pinned Wikibase snapshot into all eight concrete
language pages. Its `--check` mode detects stale generated output.

## Phase 0 — Record and measure

- Keep this architecture under version control.
- Inventory literal prose, embedded CSS, QIDs, and unresolved identifiers in
  Q315.
- Record which QIDs are local and which are external.
- Choose the four-page travel pilot and capture current screenshots.

Exit criterion: the pilot inputs and expected outputs are known.

Abstract pages are discovered from the repository rather than a committed batch
file. Their structural gate is `verify_content_migration.py`; `--release-ready`
is the stricter content and cutover gate.

## Phase 1 — Abstract HTML contract

- Add qualified QID metadata without sacrificing visible readability.
- Define and validate `q-call` and `q-arg`.
- Define typed function signatures and Wikibase snapshot format.
- Represent one long paragraph as an item composed from smaller content items.

Exit criterion: invalid abstract markup and unresolved references fail locally
and in CI.

## Phase 2 — CSS deduplication

- Extract the pilot's embedded style blocks.
- Introduce base, component, and travel collection styles.
- Link Q315 and all eight generated versions to the canonical files.
- Verify responsive and language-specific rendering.

Exit criterion: pilot pages contain no duplicated page CSS and remain visually
equivalent.

## Phase 3 — Minimal renderer

- Implement entity and monolingual-text resolution.
- Implement the QID-keyed function registry.
- Implement language-aware concatenation and explicit fallback reporting.
- Emit provenance and dependency manifests.

Exit criterion: the pilot is generated for all eight languages without reading
English HTML as an input.

## Phase 4 — Travel migration

- Convert country, city, topic, and gallery page families.
- Move reusable interface strings and name tables to Wikibase or locale packs.
- Replace direct language-to-language synchronization with Q315 generation.

Exit criterion: deleting generated travel pages and rebuilding produces a clean
repository diff.

## Phase 5 — Remaining Q315 collections

- Discover and pair the thousands of legacy English and French articles in a
  generated page registry.
- Migrate one template family within one collection at a time.
- Permit partial English/French content imports while tracking the other six
  languages in a QID-keyed translation matrix.
- Expand the small function set only when a real page requires it.
- Track page ownership, content, translation, and function coverage in
  generated reports.

Exit criterion: every logical article has a reviewed identity and migration
state; all generated-owned pages rebuild solely from Q315 and Wikibase.

## Phase 6 — Prove future-language support

- Add a ninth language through configuration and translations.
- Exercise a different writing direction or grammatical requirement when
  practical.
- Document the contributor workflow.

Exit criterion: no article HTML, CSS, or Python page table is copied to add the
language.

## Project-level completion criteria

Q315 is the source of truth when:

- semantic changes are authored once in Q315;
- translations are authored once in Wikibase or a language pack;
- function behaviour is versioned and tested once;
- CSS is canonical and shared by every rendering;
- every language page can be regenerated deterministically;
- English has no privileged role in generation;
- missing language data is measurable and never silently concealed.
