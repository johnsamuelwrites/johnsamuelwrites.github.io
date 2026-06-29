# Roadmap

## Implementation status

The travel CSS migration is complete. All 156 abstract pages beneath
`Q315/Q3062`, including nested country and city pages, own canonical
stylesheets under `Q315/assets/css/`. Their eight language renderings reference
those assets rather than embedding copies. Collection discovery and CI
validation automatically include future travel pages exposed through all eight
`hreflang` links.

## Phase 0 — Record and measure

- Keep this architecture under version control.
- Inventory literal prose, embedded CSS, QIDs, and unresolved identifiers in
  Q315.
- Record which QIDs are local and which are external.
- Choose the four-page travel pilot and capture current screenshots.

Exit criterion: the pilot inputs and expected outputs are known.

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

- Migrate one structurally similar collection at a time.
- Expand the small function set only when a real page requires it.
- Track content and function coverage in a generated report.

Exit criterion: all current Q315 pages are canonical abstract inputs.

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
