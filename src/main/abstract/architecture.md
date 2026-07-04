# Architecture

## 1. Sources of authority

There is one source of truth for each kind of information:

| Information | Authority |
| --- | --- |
| QID identity, labels, descriptions, aliases, and statements | local Wikibase |
| Article composition, order, semantic HTML, and function calls | canonical HTML in `Q315/` |
| Function implementation | versioned function registry in `src/main/abstract/` |
| Presentation | canonical CSS referenced by Q315 and all language renderings |
| Images and other media | existing media store plus QID-based metadata |
| Rendered language pages | generated output; never an upstream source |

During conversion, existing `en/` and `fr/` pages are read-only migration
inputs used to establish identity, structure, and initial translations. This
temporary role does not make either language authoritative. Once a page is
marked generated-owned, rendered language HTML is no longer accepted as an
input for that page. The incremental process and ownership states are defined
in `content-migration.md`.

The renderer must use a versioned Wikibase export or snapshot. A build must not
change merely because a live service changed between two invocations.

Local IDs and external IDs must be explicit. `Q3062` means a local Wikibase
item. The current `Q42761025` is a Wikidata item and should be represented in
metadata as `wikidata:Q42761025`, even if the visible link remains readable.

## 2. Human-readable abstract HTML

Q315 HTML is the canonical authoring format. Ordinary semantic HTML remains
visible so a contributor can understand the document without running a build.
QIDs are written in the elements they govern.

A simple concept needs no function:

```html
<section id="Q3216" data-abstract-kind="section">
  <h2><a data-entity="local:Q3216" href="/entity/Q3216">Q3216</a></h2>
</section>
```

A long paragraph can be one abstract item composed from smaller content items:

```html
<p id="Q1000" data-abstract-kind="paragraph">
  <q-call data-function="local:Q1001">
    <q-arg data-name="parts">
      <a data-content="local:Q800" href="/entity/Q800">Q800</a>
      <a data-content="local:Q801" href="/entity/Q801">Q801</a>
      <a data-content="local:Q802" href="/entity/Q802">Q802</a>
    </q-arg>
  </q-call>
</p>
```

Custom elements contain a hyphen and are valid extensible HTML. They make the
call readable without hiding it in a JSON blob. The initial renderer may parse
them as normal DOM elements; no browser-side custom-element implementation is
required.

`Q1000` identifies the resulting paragraph. `Q800` through `Q802` identify its
parts. `Q1001` identifies the constructor. These numbers are illustrative and
must be replaced by items allocated by the local Wikibase.

The abstract page should also carry machine-readable provenance:

```html
<html lang="zxx"
      data-abstract-page="local:Q3062"
      data-abstract-version="1">
```

`zxx` is retained because the page deliberately contains no natural language.

## 3. Content values and functions

### Monolingual text

Wikibase monolingual text is appropriate for:

- an atomic sentence translated as a unit;
- a caption or accessibility description;
- a paragraph translation when it intentionally cannot be decomposed;
- a human-readable function specification.

It is not appropriate for executable implementation. Text cannot reliably
express escaping, punctuation, fallback, argument validation, or deterministic
behaviour.

### Function entities

A function item in Wikibase should contain:

- multilingual label and description;
- function kind;
- ordered argument definitions;
- input and output types;
- a natural-language specification;
- an implementation key and version.

Executable implementations live in a registry keyed by the qualified QID:

```python
FUNCTIONS = {
    "local:Q1001": concatenate_monolingual_text,
}
```

The initial set should remain deliberately small:

- concatenate content units;
- select a label or monolingual text in a requested language;
- render a list with locale-aware conjunctions;
- render links and media;
- format dates, numbers, and counts;
- choose grammatical variants when a language requires them.

Functions must be deterministic, side-effect free, typed, and safe by default.
HTML escaping belongs to the renderer. A function may return a typed fragment,
but arbitrary HTML stored in Wikibase must not be executed.

### Concatenation is language-aware

Raw string concatenation is insufficient. Languages differ in punctuation,
spacing, word order, and agreement. `Q1001` should therefore accept typed parts
and a language context:

```text
concatenate(parts, language, separator_policy) -> monolingual text
```

For a paragraph whose translated meaning requires different ordering, the
Wikibase statement or language rule may provide an ordered argument variant.
The abstract article still declares the semantic parts once.

### Implemented functions

The registry (`functions/text.py`, keyed by QID in `render_abstract.py`)
currently holds two deterministic constructors:

- `concatenate monolingual text` (`Q3837`) — a generic language-checked join
  whose separator is a caller argument;
- `compose ordered paragraph` — joins ordered sentences into a paragraph using
  the *language's* inter-sentence spacing rather than a caller-supplied
  separator, so one abstract paragraph spaces correctly in every language.

The second is proposed for import by
`abstract-functions.quickstatements` (one `CREATE … P8|Q3834` block). After
import, map its returned QID to `compose_ordered_paragraph` in
`function-implementations.json`, exactly as `Q3837` is mapped today.

### Composing prose instead of storing it flat

`prepare_missing_content.py` proposes a flat `Q3185` item per text slot, which
is correct for an atomic label but stores prose as one opaque string per
language. `prepare_abstract_composition.py` is the prose path: for every
unbound slot whose text carries sentence-terminal punctuation it segments each
language into sentences and proposes an abstract paragraph (`Q3835`) built from
ordered abstract sentences (`Q3836`) by the compose function. Because a
paragraph shares one ordered set of sentence items across all languages, a
multi-sentence split is used only when the present languages agree on the
sentence count; a single-sentence slot is not composed at all — it is an atomic
content item left to `prepare_missing_content.py`, since wrapping it would give
the paragraph and its one sentence the same identity.

Work is two-phase, because plain QuickStatements cannot link two items created
in one batch:

1. the default run writes the create batches
   (`abstract-composition.quickstatements` for sentences complete in all eight
   languages plus the paragraph items, `-partial` for the translation backlog)
   and the reconciliation manifest `abstract-composition-review.csv`;
2. after import, `--structure` reads each returned QID straight from the export
   — the items carry their `M…` token as their label — resolves the function
   automatically, and emits the `P21`/`P41`/`P42` links plus the `<q-call>`
   markup for every paragraph whose sentences are all imported. A token that
   resolves to two QIDs is a duplicated item and is reported for merging rather
   than linked to an arbitrary copy.

`--bind` then replaces each resolved prose slot in its abstract page with that
`<q-call>` markup, locating the element by its exact `(tag, class, role,
occurrence)` key so a bare `<p>` is matched by position, not by fragile text.
`--bind --check` reports the pages that would change without writing.

## 4. Rendering and fallback

For each target language, the renderer:

1. loads and validates the Q315 document;
2. resolves qualified QIDs from the pinned Wikibase snapshot;
3. evaluates function calls;
4. applies language-specific grammar and formatting;
5. writes semantic HTML with the same article structure;
6. links the canonical CSS;
7. emits provenance and a dependency manifest.

Fallback must be explicit. A missing translation is reported as missing rather
than silently accepted as English. Preview builds may show a marked fallback;
release builds can choose a stricter policy per collection.

Adding a language should require a locale definition, interface messages,
translated Wikibase values, and only those grammar functions that differ from
the defaults. It must not require copying an existing language tree.

## 5. CSS ownership

CSS must not be copied into each translated HTML document. The current travel
pages demonstrate why: a large embedded style block is repeated in Q315 and
across language renderings.

The abstract document or its template owns presentation. All renderings link to
the same canonical file:

```html
<link rel="stylesheet" href="/Q315/assets/css/Q3062.css">
```

One CSS file per abstract HTML is permitted when a page is genuinely unique.
Prefer collection and component styles when pages share a design:

```text
Q315/assets/css/base.css
Q315/assets/css/components/gallery.css
Q315/assets/css/collections/Q3062.css
Q315/assets/css/pages/Q3126.css
```

The cascade order is base, components, collection, then optional page CSS.
Language-neutral CSS should use logical properties such as
`margin-inline-start`. Necessary language or direction adjustments belong in
the same canonical stylesheet using `:lang(...)` and `[dir="rtl"]`; they are not
copied into language folders.

SVG presentation attributes may remain in SVG when intrinsic to the artwork.
Repeated visual styling should move to the canonical stylesheet.

## 6. Generated-page contract

Every rendered page should declare:

```html
<meta name="generator" content="Q315 renderer">
<meta name="q315-source" content="local:Q3062">
```

A sidecar build manifest records the source document hash, Wikibase snapshot
hash, function-registry version, renderer version, language, and CSS
dependencies. This makes drift detectable and generation reproducible.
