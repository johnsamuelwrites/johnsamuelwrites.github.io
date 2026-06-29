# Development Plan

## Proposed layout

The documentation is committed first. Implementation can then grow beside it:

```text
src/main/abstract/
  README.md
  ARCHITECTURE.md
  DEVELOPMENT.md
  ROADMAP.md
  DECISIONS.md
  schema/
    abstract-html.schema.json
    function-signature.schema.json
  functions/
    registry.py
    text.py
  renderer/
    parser.py
    resolver.py
    render.py
  validators/
    abstract_html.py
    generated_output.py
  tests/
    fixtures/
```

The implementation should reuse existing path, HTML validation, link checking,
and Wikibase import helpers where their responsibilities are already clear.
Imports from the old scripts into the new renderer should be avoided when they
implicitly make English HTML authoritative.

## Canonical CSS manager

The first implementation is `css_assets.py`, configured by
`css-assets.json`. Each manifest group declares one canonical stylesheet and
all abstract and rendered pages that consume it.

```bash
# Extract identical inline CSS and rewrite the declared pages.
python src/main/abstract/css_assets.py migrate --group Q3062

# Verify that the asset exists and every page has exactly one correct link.
python src/main/abstract/css_assets.py check --group Q3062
```

Migration fails before writing when CSS differs between pages. Re-running it is
safe and produces no changes. Future page families should be added to the
manifest only after their styles have been compared and their intended sharing
boundary—component, collection, or page—has been chosen.

A collection entry discovers every abstract HTML file recursively and obtains
its rendered pages from `hreflang` links. The abstract page is authoritative:
when an older translation has CSS drift, migration deliberately replaces that
copy with a reference to the abstract page's stylesheet. Missing or unexpected
languages, duplicate QIDs, paths outside the repository, and missing pages are
errors. This lets a newly added travel page enter the same process without
adding nine paths by hand.

## First pilot

Use a small vertical slice from travel:

1. `Q315/Q3062/index.html`;
2. one country page;
3. one city page;
4. one topic or gallery page;
5. all eight current languages.

The pilot should include:

- a direct entity label;
- an interface message;
- a multi-sentence paragraph;
- a `concatenate` function call;
- an image with translated accessible text;
- navigation and language alternates;
- one shared collection stylesheet.

## Initial implementation order

1. Define qualified ID parsing: `local:Q…` and `wikidata:Q…`.
2. Define the canonical custom elements and their validation rules.
3. Export the required Wikibase items to a pinned test fixture.
4. Implement typed values and the function registry.
5. Implement label resolution and `concatenate`.
6. Extract the travel style block into canonical CSS.
7. render the four pilot pages into all eight languages;
8. compare structure, links, accessibility, and screenshots;
9. add deterministic regeneration to CI.

## Validation rules

An abstract document is invalid when:

- natural-language prose occurs outside an approved diagnostic annotation;
- a QID lacks an explicit authority;
- a function or content item cannot be resolved;
- a function receives an unknown, missing, or incorrectly typed argument;
- two elements claim the same page-level identity incorrectly;
- executable code or arbitrary rendered HTML comes from Wikibase text;
- a linked stylesheet is located in a translated language tree.

A generated page is invalid when:

- unresolved QIDs remain in user-facing content;
- an unmarked fallback is used;
- its semantic article structure differs from the abstract source;
- it embeds CSS that belongs to the abstract page or collection;
- its manifest does not match its inputs;
- internal links or language alternates are broken.

## Build interface

The eventual command should be collection-aware:

```bash
python -m src.main.abstract.renderer.render \
  --source Q315/Q3062/index.html \
  --languages en fr ml pa hi pt es it \
  --wikibase-snapshot path/to/snapshot.json
```

Useful companion commands:

```bash
# Validate abstract documents without rendering.
python -m src.main.abstract.validators.abstract_html Q315

# Confirm committed output is reproducible.
python -m src.main.abstract.renderer.render --collection Q3062 --check
```

The exact CLI can change when implementation begins; deterministic input and
`--check` behaviour are part of the contract.

## Migration safety

Existing language pages remain review material until a pilot is proven. For
each migrated page:

1. import reusable concepts and translations;
2. author the Q315 call structure;
3. render into a temporary output tree;
4. compare semantic DOM and screenshots;
5. obtain human review for all eight languages;
6. switch the committed pages to generated ownership.

The current `build_abstract_travel_tree.py`,
`bind_abstract_content.py`, and `refresh_travel_pages.py` remain useful for
inventory and import. Once Q315 is authoritative, they must not overwrite
canonical abstract documents from English pages.
