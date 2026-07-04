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
- The content round-trip comparison reports 604 mismatching page/language
  combinations across all 170 canonical pages. This includes structural and
  wording differences in legacy language pages; it must not be interpreted as
  604 missing translations.

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

## Round-trip limitation

`verify_content_roundtrip.py` currently reports `mismatch` for 604
page/language checks. The largest concentrations are `Q3634`, `Q3646`, and
`Q3636`. Besides missing labels, this comparison detects differing wording,
ordering, and structure in legacy localized HTML. It should become a strict
completion gate only after those pages are regenerated from Q315 and the
Wikibase snapshot.
