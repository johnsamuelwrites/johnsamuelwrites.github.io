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

For Q315-driven pages, render the bound language-page slots after applying the
Q315 source change, then verify round-trip equivalence. Example for the detailed
CV:

```sh
python3 src/main/abstract/render_page.py --page Q3646
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
the manifest workflow below. Plain `preview`/`apply` is retained only for legacy
rendered-page repair workflows.

Do not use `content_update.py --family photographies --mode wikibase-*`.
The canonical multilingual photography/travel workflow is:

```sh
python3 src/main/abstract/prepare_travel_content.py
python3 src/main/abstract/bind_travel_manifest.py
python3 src/main/abstract/render_page.py --check
python3 src/main/abstract/verify_content_roundtrip.py
```

## Detailed CV

`cv.csv` appends entries to `Q315/Q3636/Q3646.html`, the Q315 source for the
detailed CV. Use `section` for the HTML section id, such as `journals`,
`conferences`, `preprints`, `postersdemo`, `talks`, or `panels`. Use either
`year` or `year_qid`; if `year` already exists in the abstract labels, the tool
finds the local year QID automatically. Use `content` for the CV line and leave
`local_qid` empty until `wikibase-apply` fills it.

The common flow is:

```sh
python3 src/main/content_update.py --family cv --mode wikibase-plan
python3 src/main/content_update.py --family cv --mode wikibase-apply --allow-create
python3 src/main/content_update.py --family cv --mode q315-apply
python3 src/main/abstract/render_page.py --page Q3646
python3 src/main/abstract/verify_content_roundtrip.py --page Q3646
```

Optional columns `content_fr`, `content_ml`, `content_pa`, `content_hi`,
`content_pt`, `content_es`, and `content_it` may be used for localized CV text.
When they are empty, the English/canonical `content` value is used for every
language.
