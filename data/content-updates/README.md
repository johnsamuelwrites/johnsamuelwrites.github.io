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

`photographies.csv` is retired. It is kept as an inventory of the 1,136 image
placements it recorded, but `content_update.py` no longer has a `photographies`
family and will not read it: photography is owned by the Q315 travel workflow,
which is the only pipeline that binds and renders it.

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
