# Initial Decisions

These decisions capture the current planning baseline. They may be amended by a
later dated decision, but implementation should not silently contradict them.

## D001 — Canonical authoring remains HTML

Q315 uses human-readable semantic HTML as its public abstract representation.
Machine-readable attributes and custom elements supplement the HTML rather than
replacing it with an opaque data file.

## D002 — QIDs may identify content at multiple scales

A QID may identify an entity, heading, sentence, multi-line paragraph,
interface message, function, or other reusable semantic unit. Items should be
created where independent identity, translation, reuse, provenance, or
composition is valuable—not mechanically for every DOM element.

## D003 — Functions are QID-addressed but code is versioned

Wikibase describes a function and its signature. A local, tested registry
implements it. Monolingual text may document a function but is not executable
code.

## D004 — QID authorities are explicit

Local Wikibase IDs and Wikidata IDs occupy different namespaces. Resolution,
validation, and manifests retain that distinction.

## D005 — CSS belongs to the abstract design

Translated pages reference canonical Q315 CSS. Collection and component CSS is
preferred over one file per page when styles are shared; page-specific CSS is
allowed when it is genuinely unique.

## D006 — Language pages are generated incrementally

A page family becomes generated-only after deterministic output, semantic
comparison, visual comparison, and language review succeed. Existing language
pages remain migration evidence until that point.

## D007 — English is a target language

English can supply bootstrap material during migration, but the final renderer
does not consume English HTML. It renders English from the same Q315 source and
the same class of language resources as every other language.
