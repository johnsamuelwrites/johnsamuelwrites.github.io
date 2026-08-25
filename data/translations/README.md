# Translations

CSV files here hold multilingual text that is genuinely *translated*, as opposed
to the names and titles in `data/content-updates/`, which keep their original
form in every language.

One column per language, using the codes from `src/main/languages.py`. Adding a
language is a new column, not an edit to every row.

## place-names.csv

Country and city names for the travel pages, read by
`src/main/refresh_travel_pages.py`. `kind` is `country` or `city`.

Countries carry a real exonym in every language -- Germany is *Allemagne*,
*Germania*, *Alemania*. Cities are filled in only for `ml`, `pa` and `hi`, which
transliterate into their own scripts; the Latin-script pages keep the city's own
name, so those cells are empty. **An empty cell means "use the English form"**,
which is how every loader here treats it.

Place names are translated, unlike the names in `data/content-updates/`. A city
or country has an established name in each language; a book title, an author or
a museum does not.

City exonyms live here too: French writes Antwerp as *Anvers* and Venice as
*Venise*, and those 15 names drive the French page filenames. They used to sit in
a French-only override table because `translated_city_name` consulted the
translation table for the Indic languages alone; it now consults it for every
language, so an exonym in any language is just a filled cell.

## page-slugs.csv

The per-language URL slug for each travel page, so `an-amateur` becomes
`un-amateur` in French. Values must not contain spaces or slashes.

## ui-labels.csv

Page chrome for the travel and country pages -- navigation, footer, tagline.
One row per label, one column per language, including `en`.

## image-descriptions.csv

Photo `alt` text and photo-location captions for the travel and photography
pages, read by `src/main/refresh_travel_pages.py`.

| column | meaning |
| --- | --- |
| `table` | `alt` for image alt text, `caption` for photo-location captions |
| `en` | the English text as it appears in the page, and the lookup key |
| `fr` … `it` | the translation shown on that language's page |

`translate_image_text` looks in the `alt` table first and then `caption`, so a
key present in both must carry the same values; a test enforces that.

These 296 rows used to be two dictionaries inside `refresh_travel_pages.py`. They
were moved out so a translator can work on them without touching Python and so
the diff for a translation change is one reviewable row.

Verify a change without writing anything:

```sh
python3 src/main/refresh_travel_pages.py --dry-run
```
