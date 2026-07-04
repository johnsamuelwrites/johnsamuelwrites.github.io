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
