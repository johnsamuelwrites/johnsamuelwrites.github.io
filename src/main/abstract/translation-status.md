# Q315 Translation Status

Status checked: 4 July 2026, using the refreshed
`../Q42761025/data/labels-wikibase.csv`.

Supported languages are `en`, `fr`, `ml`, `pa`, `hi`, `pt`, `es`, and `it`.

## Update — 5 July 2026: rendering, structural repair, and a corrupt export

The round-trip is now driven from Q315 by three tools, and the label source has
been replaced because the SPARQL export was found to be corrupt.

- **`render_page.py`** rewrites the atomic bound slots of each language page to
  the entity's Wikibase label, in place, and flips migration ownership to
  `abstract`. **`repair_structure.py`** inserts template-defined bound children
  that a language page omits (e.g. a gallery-card's `card-description`) where the
  parent container still lines up one-for-one; container-divergent pages (the big
  index pages missing whole entries) are skipped for regeneration.
- **The export was corrupt, not just stale.** `all-multilingual-labels.rq` times
  out on the endpoint and returns partial, **value-misaligned** rows — e.g. the
  CSV listed Christina Perri's French label as "Bruno Mars", Dan Brown's as "Dan
  Brun". Wikibase itself was correct. **`fetch_wikibase_labels.py`** now rebuilds
  the labels CSV from the reliable `wbgetentities` API into
  `src/main/abstract/data/labels-wikibase.csv`, which is the **canonical label
  store** for this repository and the default `--data-dir` for every abstract
  tool (`css_assets.DEFAULT_DATA_DIR`). The broken SPARQL export is no longer
  read.
- **Native-label normalization.** Seven genuine native-rule deviations (five
  translated film titles, "Giuseppe Verdi", "MO Museum") were set to English
  verbatim in Wikibase via `wikibase_write.py`. Legitimately translated chrome
  (the "Writings" nav, "Museum" type, locations) was deliberately left alone.
- **Result.** From a clean baseline of 607 (correct labels, nothing rendered),
  render + repair reach **438** round-trip mismatches with **231 checks improved
  and 0 regressions**. Only 6 remain label-driven (three still-temporary items,
  `Q7792`/`Q7852`/`Q7853`); the other 432 are structural — the large index pages
  (`Q3634`/`Q3636`/`Q3646`, whose language versions list ~170 entries where the
  template has ~800) that need regeneration, not insertion.

## Update — 5 July 2026 (later): composed long paragraphs, fixed a clobber bug

- **Composed types now win in the label store.** A composed paragraph/sentence
  carries both `Q3185` and `Q3835`/`Q3836`; `fetch_wikibase_labels.py` now records
  the composed type as `itemtype`. Previously it recorded `Q3185`, so `render_page`
  did not recognise 80 bound composed paragraphs as composed and, once
  `render_abstract` had collapsed their `<q-call>` to text, overwrote them with
  their descriptive label (e.g. the Q3062 hero read "Q3062 hero description").
  With the fix, the renderers skip composed items and `render_abstract` restores
  the real text; a whole-repo check now reports **0 clobbered composed slots**.
- **Long prose is composed, not truncated.** Wikibase labels cap at 250
  characters, so three long paragraphs (`Q7792` food, `Q7852`/`Q7853` Pope
  Francis) had been stored as flat `Q3185` items with truncated labels, blocking
  `Q3063`/`Q3644`. They are now `Q3835` composed paragraphs built from ordered
  `Q3836` sentences (`compose_ordered_paragraph`), split only where all languages
  agree on the sentence count. Both pages render with their full text preserved.
- **`wikibase_write.py` now writes qualifiers** (`Q|P|v|Pq|"vq"`), needed for the
  sentences' `P42` ordinals; this also unblocks the already-generated 391-op
  `abstract-composition-structure.quickstatements`.
- Round-trip is **432**. The remaining mismatches are the large index pages.

Everything below predates the 5 July updates and is kept for history; several
counts in it were computed against the corrupt export.

## Summary

- Q315 contains 3,799 distinct bound local QIDs.
- 437 bound QIDs are missing at least one supported-language label.
- 60 bound content items still have an `M… abstract content` English label.
- The union of those problems is 442 QIDs across 18 canonical files.
- One human-readable content slot is still unbound.
- The content round-trip comparison originally reported 604 mismatching
  page/language combinations across all 170 canonical pages. Of these, only 8
  failed purely on a genuinely missing label (57 more mixed missing labels with
  wording drift); the remaining 539 failed purely because a legacy language page
  phrases the correct canonical content differently. It must not be interpreted
  as 604 missing translations.
- Rendering canonical labels into the bound slots (see "Content round-trip via
  in-place rendering") is the fix for the wording bucket. All 157 renderable
  pages have now been rendered; the global count is 587 and every rendered page
  is `render_ownership: abstract`.

## Conservative page-gated batch

`prepare_missing_labels.py` now produces:

- `missing-label-page-status.csv`: the ready/deferred decision and reason for
  every affected canonical page;
- `missing-label-translations.csv`: translations from ready pages only;
- `missing-label-updates.quickstatements`: import statements from ready pages
  only.

A page is ready only when every affected atomic content item (`Q3185`) has an
exact English match, all eight structurally corresponding localized slots are
present, and no occurrence conflicts with another occurrence. Temporary items
and composed paragraphs/sentences (`Q3835`/`Q3836`) are deferred to their
dedicated reconciliation pipelines. This batch performs no machine
translation.

The current batch contains two items:

- Q3190 (`Photography`) from `Q315/Q3647.html`;
- Q3210 (`Netherlands`) from `Q315/Q3062/Q3045.html`.

All other affected pages are deferred. In particular, the earlier
all-at-once 442-item proposal was discarded because occurrence alignment and
existing P40 values could preserve unrelated legacy text.

## Problems by canonical file

The “missing” column counts distinct bound QIDs lacking one or more target
language labels. “Temporary” counts bound items whose English label is still
an import token. A QID can appear in both columns.

| Canonical file | Missing | Temporary | Main problem |
| --- | ---: | ---: | --- |
| `Q315/Q3638/index.html` | 111 | 0 | Large collection index has English-only entity labels. |
| `Q315/Q3062/Q3018.html` | 108 | 0 | Travel content is missing all seven non-English labels. |
| `Q315/Q3634.html` | 71 | 53 | Failed pipe-containing label updates plus older English-only entities. |
| `Q315/Q3062/Q3063.html` | 64 | 0 | Travel content is predominantly English-only; Q7792 also lacks Spanish and Italian labels. |
| `Q315/Q3638/Q3639.html` | 20 | 0 | Bound entities are missing all seven non-English labels. |
| `Q315/Q3638/Q3644.html` | 18 | 3 | English-only entities and temporary items Q7482, Q7852, and Q7853. |
| `Q315/Q3636/Q3646.html` | 12 | 2 | Year/entity labels are untranslated; Q7609 and Q7921 are temporary; one bibliography slot is unbound. |
| `Q315/Q3633.html` | 12 | 0 | Bound entities are missing all seven non-English labels. |
| `Q315/Q3638/Q3641.html` | 6 | 1 | English-only entities and temporary item Q7266. |
| `Q315/Q3638/Q3640.html` | 4 | 0 | Four bound entities lack non-English labels. |
| `Q315/Q3062/Q3026.html` | 3 | 0 | Three bound entities lack non-English labels. |
| `Q315/Q3062/Q3061.html` | 3 | 0 | Q3262, Q3263, and Q4045 lack non-English labels. |
| `Q315/Q3635.html` | 3 | 0 | Three bound entities lack non-English labels. |
| `Q315/Q3062/Q3025.html` | 1 | 0 | Q3210 lacks non-English labels. |
| `Q315/Q3062/Q3045.html` | 1 | 0 | Q3210 lacks non-English labels. |
| `Q315/Q3062/index.html` | 1 | 0 | Q3838 lacks non-English labels. |
| `Q315/Q3638/Q3642.html` | 0 | 1 | Q7434 still has a temporary English label. |
| `Q315/Q3647.html` | 1 | 0 | Q3190 lacks non-English labels. |

## Failed label-finalization group

Q7860–Q7911 and Q7921 remain temporary. Their desired labels contain the
literal vertical-bar character (`|`); the attempted QuickStatements update
did not finalize them. These items primarily affect `Q315/Q3634.html`, with
Q7921 affecting `Q315/Q3636/Q3646.html`.

Q7434 is a separate semantic collision. Its content is the translated common
word “Queen”, while Q6939 is a native title whose label is also “Queen”.
Q7434 therefore needs a distinct administrative English label while retaining
`Queen` as its English P40 content value.

Other temporary items already bound in Q315 are Q5709, Q7266, Q7482, Q7609,
Q7852, and Q7853.

## Unbound content

`Q315/Q3636/Q3646.html` still contains one unbound paragraph text slot,
identified as token `M67F96434DBE6`. It is the long Jonathan Tennant/SocArXiv
bibliography entry. The Malayalam and Punjabi drafts are visibly corrupted
and must be reviewed before the item is imported and bound.

## Content round-trip via in-place rendering

`render_page.py` makes Q315 authoritative without rewriting whole pages or
breaking navigation. It substitutes only the bound `data-content`/`data-entity`
text nodes in each legacy language page with that entity's Wikibase label for the
language, addressed by the shared `(tag, class, role, occurrence)` slot
signature, and injects a `Q315 renderer` generator meta so the page's migration
ownership flips from `legacy` to `abstract`. Chrome, links and unbound content
are left untouched; composed `<q-call>` paragraphs remain `render_abstract.py`'s
responsibility. Use `--check` for a dry run and `--page QID` to scope to one page.

A slot is rewritten only when the legacy page holds the **same number** of
same-signature elements as the template. Where the counts differ — for example a
language switcher that omits the current language, so the template has eight
`inLanguage` spans and the page has seven — occurrence `N` addresses different
content, so the whole signature group is left alone and reported as unplaced
rather than shifted. This is the guard `prepare_missing_content.py` already uses.

- 157 of 170 pages rendered against the current export; 13 (`Q3646, Q315, Q3634,
  Q3636, Q3633, Q3638, Q3635, Q3640, Q3641, Q3642, Q3643, Q3644, Q3647`) were
  skipped because 34 bound QIDs have empty labels **in the export**. Those 34 items
  (9 page/section entities of type `Q3017`/`Q26`, 25 `Q3185` content items) were
  checked against the live Wikibase and **all 34 carry complete labels in all
  eight languages** — the blocker is an incomplete `labels-wikibase.csv`, not
  missing translation. A demo with the 34 rows filled renders all 170 pages and
  drops the round-trip to 560 with the entire missing-label bucket (104 checks)
  eliminated, leaving only structural gaps.
- **Root cause of the incomplete export.** `queries/all-multilingual-labels.rq`
  times out on the wikibase.cloud SPARQL endpoint (HTTP 504) and returns a
  partial result, so items are silently dropped; a re-export refreshed only 4 of
  the 34. The query has a redundant mandatory `?item rdfs:label ?anyLabel` triple
  that cross-joins every item against all its labels, and eight `OPTIONAL`
  `FILTER(LANG())` label joins under a `GROUP BY` over the whole item set — too
  heavy for the endpoint's timeout. Scoped `VALUES` queries return every dropped
  item (e.g. `Q3650` "Linguistics") with all eight labels, confirming the data is
  present and only the full query truncates. Fix in the exporter (not this repo):
  drop the `?anyLabel` cross-join and either paginate (`LIMIT`/`OFFSET` or split
  by `itemtype`) so each chunk completes under the timeout, or fetch labels via
  the `wbgetentities` API instead of SPARQL.
- The batch produced 100 slot-text rewrites (every other page change is only the
  generator meta) and flipped all 157 pages to `abstract` ownership. The
  round-trip fell from 600 to 587 with **no regressions**; residual mismatches
  are the 458 unplaced slots plus the 13 skipped pages.
- **Unplaced slots** are bound entities whose template signature is absent from a
  legacy page (e.g. `Q3045`'s `hero-subtitle` paragraph is missing from the
  `ml`/`pa`/`hi` pages). These need a structural page fix, not a translation, and
  are what stop the round-trip from reaching `equivalent`.
- Rendering also upgraded slots that still carried English text on non-English
  pages to proper localized labels. It is faithful to the label store: where a
  canonical label is *less* localized than the legacy text (e.g. `it` "Marsiglia"
  replaced by "Marseille"), the render surfaces it — a label-quality fix to make
  in `labels-wikibase.csv`, not a renderer defect.

## Structural gaps and the repair pilot

Every remaining round-trip failure is now **structural**: the language page lacks
an element the template binds, so its label has nowhere to land. The 458 unplaced
slots are concentrated — 47 pages, 110 QIDs — and dominated by a few repeating
components: `p.card-description` (132), `p.hero-subtitle` (141) and unclassed
`span` (152, largely the hero blurb, nav and language switcher). Most affect the
`ml`/`pa`/`hi` travel/gallery pages, which were built before those components
existed; the translated content already lives in Wikibase.

**Pilot (`Q3062`, travel index):** the `ml`/`pa`/`hi` pages carry all 44
gallery-cards in the *same order* as the template but omit the `card-description`
paragraph, and omit the `hero-subtitle`. A positional insertion — map card N to
template card N (order verified identical), add the missing `<p>` filled with the
entity's Wikibase label — took the page from three fully-broken languages (45 gaps
each) to **7 of 8 clean** (`en fr ml pa hi es it`; only `pt` retains one unrelated
search-nav `span`). Global round-trip fell 587 → 583. This confirms the fix is a
small, reliable **element insertion**, not a page rebuild.

`card-description` + `hero-subtitle` (and the close cousins `city-description`,
`quote-author`) account for roughly 300 of the 458 unplaced slots, so generalizing
this insertion across the ~40 affected pages should close most structural gaps.
The residual unclassed-`span` bucket (hero blurb / nav / search, plus language-
switcher metadata that arguably should not be round-trip content) is a smaller,
separate pattern.

## Round-trip limitation and the remaining index-page work

`verify_content_roundtrip.py` reports `mismatch` (432). The remaining mismatches
are concentrated in a few large pages and are **not** simple missing translations:

- `Q3634` (blog) — **resolved by exclusion.** The blog index is not a translated
  Q315 template: `blog.py` generates one page per language listing only that
  language's own articles (hence the different counts — `en` 806, `fr` 1138,
  `ml` 177). It cannot be translated to eight languages because most articles do
  not exist in most languages. `render_page` had wrongly treated it as a template
  (injecting the generator meta and turning article-title `|` into `—`); those
  blog pages were reverted to their `blog.py` output. Abstract pages whose English
  target is a `blog.py` output are now skipped by render, repair and round-trip
  (`discover_content_migration.EXTERNALLY_GENERATED_INDEXES`), removing 10,066
  false misses. The blog is regenerated by `blog.py` (needs `bs4`/`pandas`).
- `Q3646` (detailed CV) and `Q3636` (research index) — long academic **citations**
  with embedded author-link structure, plus more 250-char-truncated items
  (`Q7845`, `Q6284`, `Q7602`, `Q7846`, `Q7855`, `Q7856`, `Q7858`, `Q7486`). These
  need the composition treatment applied per item, and citations may warrant a
  dedicated concatenation function rather than a single-sentence paragraph.
- Assorted residue: `Q4045` still carries a `T0204 travel content` token label
  (never finalised), and several pages have finer sub-element misalignments.

This is a distinct, larger effort than the render/repair/compose work above; it is
the outstanding item, tracked here rather than pretended complete.
