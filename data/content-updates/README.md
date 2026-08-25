# Content Updates

CSV files in this directory are the source for append-style updates handled by
`src/main/content_update.py`.

Run a dry preview:

```sh
python3 src/main/content_update.py --family books --mode q315-preview
```

Apply changes:

```sh
python3 src/main/content_update.py --family books --mode q315-apply
```

Assert every CSV is already in sync with its Q315 source (this is what CI runs):

```sh
python3 src/main/content_update.py --mode check
```

Compare QID bindings in both directions -- CSV rows whose QIDs are absent from the
Q315 source, and QIDs bound on the source that no CSV row claims:

```sh
python3 src/main/content_update.py --mode diff
```

`check` answers "would applying this CSV change the source?". `diff` answers
"do the two sides bind the same content items?", which catches entries added to a
source by hand and CSV columns that point at nothing. `diff` reports orphans only
for families whose CSV mirrors the whole source; `cv.csv` only appends, so its
source legitimately holds entries the CSV never mentions.

For Q315-driven pages, render the bound language-page slots after applying the
Q315 source change, then run the rendered-page guard and verify round-trip
equivalence. Example for the detailed CV:

```sh
python3 src/main/abstract/render_page.py --page Q3646
python3 src/main/abstract/validate_rendered_pages.py --page Q3646
python3 src/main/abstract/verify_content_roundtrip.py --page Q3646
```

Plan local Wikibase changes:

```sh
python3 src/main/content_update.py --family films --mode wikibase-plan
```

Bind or repair local Wikibase items and write the local QID to the CSV:

```sh
python3 src/main/content_update.py --family films --mode wikibase-apply
```

By default, Wikibase modes only search for existing local items, bind clear
matches, and repair missing `P8`/`P40`/`P4` claims on already matched items.
They do not create new local items unless `--allow-create` is passed explicitly.

Wikidata policy:

- `books.csv`: `wikidata_url` may be empty.
- `quotes.csv`: `wikidata_url` is not used.
- `photographies.csv`: `wikidata_url` is not used by this append helper.
  Photography Wikibase/content binding is owned by the Q315 abstract travel
  pipeline under `src/main/abstract/`.
- `cv.csv`: `wikidata_url` is optional and should be used only when the CV row
  itself has a linked publication or external Wikidata identity.
- `films-series-documentaries.csv`, `museums-galleries.csv`, and `music.csv` require
  `wikidata_url`.

These five families use canonical names/titles, not translated labels. Use
`name`, `creator`, `quote`, `attribution`, and `category` as monolingual fields;
the same values are rendered on every language page. Legacy language-specific
columns such as `name_en` are still accepted as a compatibility fallback.

`books.csv` also has a `creator_qid` column holding the author's content-item
QID. When it is set, the author is rendered as a bound content item and the Q315
renderer supplies the label for each language; when it is empty, the plain
`creator` text is written into the source and reads identically in all eight
languages. Leave it empty only for works with no author. `--mode extract`
backfills it from the Q315 source for rows that already have a binding there.

The `id` column is optional. When it is empty, the tool generates a stable local
identifier from the Wikidata QID when available, otherwise from the canonical
name/title/quote text.

The `type` column is rendered as schema.org markup. You may use canonical values
such as `Movie`, `TVSeries`, `PodcastSeries`, `Book`, `Museum`, `ArtGallery`,
`Person`, `MusicGroup`, and `Quote`. Common lowercase aliases such as `film`,
`movie`, `series`, `podcast`, `book`, `museum`, `gallery`, `artist`, `singer`,
and `band` are accepted and normalized automatically.

`wikibase-apply` adds a `local_qid` column when needed. Leave it empty; the tool
fills it by looking up an existing local item with `P4`, `P40`, or an exact
label match. Repaired local items follow the abstract content model used
elsewhere in the repository: `P8` points to `Q3185`, and `P40` stores the
canonical content as monolingual text for every supported language. `P4` stores
the Wikidata item identifier when available.

For quotes, `local_qid` is the quote text item or the wrapper item for a split
quote. Use `part_qids` for long quotes that are already split into multiple
content items because of Wikibase text limits, and `attribution_qid` for the
author/source line.

For photographies, each row represents one travel/gallery placement of one image.
The row is keyed by `page + src`, so the same image may appear on several pages.
Use `section` to choose the QID/literal gallery subsection heading, `src` for the
image URL, and optional `href`, `location`, `year`, `card_class`, and
`data_location` to match the local page style. Do not use `q315-preview` or
`q315-apply` for photography; Q315 abstract photography/travel pages are owned by
the manifest workflow below. `preview` is retained as a read-only diagnostic,
and photography is the only family for which `apply` still runs.

Entries on a Q315 source must carry a `data-content="local:Q…"` binding, not the
bare QID as text: the renderer substitutes a per-language label into a bound slot,
and an unbound one reaches the page as the literal QID. `q315-apply` repairs
older entries that were authored unbound.

Items that cannot be bound yet are listed in `UNBOUND_CONTENT_QIDS` in
`content_update.py` with the reason. Binding an item makes the round-trip
verifier require its stored label to appear on every language page, so an item
whose Wikibase label disagrees with the published pages has to be corrected in
Wikibase first.

Binding is all-or-nothing per container. `render_page.py` places labels by slot
position, so a container with one unbound entry among bound ones renders the
bound labels into shifted positions and leaves the unbound slot showing stale
text, dropping one name from the page and duplicating another. A container
holding any listed QID is therefore left entirely unbound until it can be bound
completely. Once the correction is imported, remove the QID from the set and
run `q315-apply` to bind the whole container in one pass.

`UNBOUND_CONTENT_QIDS` is currently empty: every entry on every Q315 source is
bound.

Museum names are proper nouns and must read identically in every language, so a
translated museum name is a Wikibase error, not a translation. Translations are
Wikibase-driven and reach the pages through `labels-wikibase.csv`, so correcting
one means editing Wikibase and refreshing that snapshot -- editing the snapshot
alone only creates drift. The flow is:

```sh
python3 src/main/wikibase_write.py <corrections>.quickstatements --apply
python3 src/main/abstract/fetch_wikibase_labels.py
python3 src/main/content_update.py --family museums --mode q315-apply
python3 src/main/abstract/render_page.py --page Q3643
```

QuickStatements files under `src/main/abstract/` are generated review material
and are gitignored; write one, apply it, then commit the refreshed snapshot and
the pages it changed. `Q3808` ("MO Museum") was corrected this way: its ml/pa/hi
label and `P40` values were transliterations, and every other museum already
carried the Latin name in all eight languages.

`--mode apply` writes rendered language pages directly and therefore bypasses
Q315. It is refused for every family that has a Q315 source, because the Q315
renderer rewrites bound markup -- dropping `property="name"` and the `sameAs`
link -- until the entry matching used by that path no longer recognises an entry
that is already on the page, and appends a duplicate. Use `q315-apply` followed
by `src/main/abstract/render_page.py` instead. `--mode preview` stays available
as a read-only diagnostic and is the easiest way to see which rendered pages have
drifted from their CSV.

Do not use `content_update.py --family photographies --mode wikibase-*`.
The canonical multilingual photography/travel workflow is:

```sh
python3 src/main/abstract/prepare_travel_content.py
python3 src/main/abstract/bind_travel_manifest.py
python3 src/main/abstract/render_page.py --check
python3 src/main/abstract/validate_rendered_pages.py
python3 src/main/abstract/verify_content_roundtrip.py
```

## Detailed CV

`cv.csv` appends entries to the Q315 CV sources. Use `target=detailed` for only
the detailed CV, `target=simple` for only the research index summary, or
`target=both` for both. Use `section` for the HTML section id, such as
`journals`, `conferences`, `preprints`, `postersdemo`, `talks`, `panels`, or
`participation`. The `participation` section is for conferences, seminars, and
workshops attended. Use either `year` or `year_qid`; if `year` already exists in
the abstract labels, the tool finds the local year QID automatically. Use
`content` for the CV line and leave `local_qid` empty until `wikibase-apply`
fills it.

Example row for an attended conference or workshop:

```csv
id,type,target,section,year,year_qid,content,simple_content,part_qids,wikidata_url,local_qid,simple_local_qid
,CVEntry,both,participation,2026,,"Example Conference, City, Country, Jun 2026, https://example.org",,,,,
```

The common flow is:

```sh
python3 src/main/content_update.py --family cv --mode wikibase-plan
python3 src/main/content_update.py --family cv --mode wikibase-apply --allow-create
python3 src/main/content_update.py --family cv --mode q315-apply
python3 src/main/abstract/render_page.py --page Q3646
python3 src/main/abstract/validate_rendered_pages.py --page Q3646
python3 src/main/abstract/verify_content_roundtrip.py --page Q3646
```

Optional columns `content_fr`, `content_ml`, `content_pa`, `content_hi`,
`content_pt`, `content_es`, and `content_it` may be used for localized CV text.
When they are empty, the English/canonical `content` value is used for every
language.

When only part of an entry needs translation, such as a month name or visible
link text, prefer the existing Q315 composition model over duplicating the whole
CV line in every `content_<language>` column. Create or reuse fragment content
items for the translatable parts, bind the composed paragraph item with
`<q-call data-function="local:Q4182">`, and let the Q315 renderer combine those
fragments for each language.
