# Q315 Translation Status

Status checked: 4 July 2026, using the refreshed
`../Q42761025/data/labels-wikibase.csv`.

Supported languages are `en`, `fr`, `ml`, `pa`, `hi`, `pt`, `es`, and `it`.
This report is diagnostic only. It does not import Wikibase statements or
change translations.

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
  in-place rendering") is the fix for the wording bucket. The Q3045 pilot has
  been rendered; the global count is now 600.

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

- 157 of 170 pages have every bound QID labelled in all eight languages and are
  renderable now; 13 (`Q3646, Q315, Q3634, Q3636, Q3633, Q3638, Q3635, Q3640,
  Q3641, Q3642, Q3643, Q3644, Q3647`) are blocked by the still-missing labels and
  are skipped with a message until those labels land.
- **Pilot (`Q3045`, "seas"):** rendered into all eight language pages. `en`, `fr`,
  `pt`, `es`, `it` now round-trip clean; the `ml`/`pa`/`hi` legacy pages lack the
  `hero-subtitle` paragraph entirely, so `Q4079` cannot be placed and is reported
  as an unplaced slot (a structural page fix, not a translation gap). The pilot
  also upgraded several `ml`/`pa`/`hi` slots that still carried English text to
  proper localized labels.
- The renderer is faithful to the label store: where a canonical label is less
  localized than the legacy text (e.g. `it` "Marsiglia" replaced by "Marseille"),
  the render surfaces it. Those are label-quality fixes to make in
  `labels-wikibase.csv`, not renderer defects.

## Round-trip limitation

Before the in-place rollout completes, `verify_content_roundtrip.py` still reports
`mismatch` (600 after the Q3045 pilot). The largest concentrations remain `Q3634`,
`Q3646`, and `Q3636`. It becomes a strict completion gate once the 157 renderable
pages are rendered and the residual structural gaps (unplaced slots) and the 13
label-blocked pages are reconciled.
