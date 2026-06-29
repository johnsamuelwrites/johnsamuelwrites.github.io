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

- [ARCHITECTURE.md](ARCHITECTURE.md) defines authority, abstract HTML, function
  calls, translation, and CSS ownership.
- [DEVELOPMENT.md](DEVELOPMENT.md) proposes repository layout, validation, and
  the first executable pilot.
- [ROADMAP.md](ROADMAP.md) gives staged milestones and acceptance criteria.
- [DECISIONS.md](DECISIONS.md) records the initial architectural decisions that
  should remain stable while the implementation evolves.
- [QUERYING.md](QUERYING.md) defines the queryable Wikibase graph and example
  SPARQL shapes for abstract content.

## Current status

The existing scripts are valuable bootstrap tools. In particular, they align
the eight current languages, assign QIDs, create QuickStatements, and construct
the first abstract travel tree. During migration they should be treated as
importers and analysers. The target state is a renderer whose only article
composition input is Q315.

No existing generated page is declared disposable merely by this plan. A
collection becomes generated-only after it passes the round-trip and visual
checks described in the roadmap.
