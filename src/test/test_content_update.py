import unittest
import html as html_lib
import io
import re
import tempfile
from unittest import mock
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

import content_update

from content_update import (
    ABSTRACT_CONTENT_ITEM,
    ContentRow,
    ContentUpdateError,
    FAMILIES,
    INSTANCE_OF_PROPERTY,
    MONOLINGUAL_CONTENT_PROPERTY,
    UNBOUND_CONTENT_QIDS,
    bind_first_tag,
    build_q315_list_item_html,
    build_q315_museum_card_html,
    build_q315_quote_card_html,
    build_wikibase_content_item_data,
    build_wikibase_repair_data,
    backfill_q315_qids,
    csv_bound_qids,
    derived_q315_qids,
    diff_q315_family,
    canonical_wikidata_url,
    content_texts_for_wikibase,
    main,
    normalize_text,
    museum_entries_are_bindable,
    q315_content_qids,
    repair_q315_museum_block,
    repair_q315_quote_attribution,
    q315_creator_pairs,
    read_rows,
    render_content,
    render_family,
    render_cv_simple_text,
    render_cv_text,
    render_q315_family,
    render_q315_content,
    render_q315_cv_simple_text,
    render_q315_cv_text,
    render_photography_page,
    slugify,
    validate_rows,
    wikidata_qid,
)
from paths import REPO_ROOT


class ContentUpdateTests(unittest.TestCase):
    def test_books_accept_missing_wikidata(self):
        row = ContentRow(
            family="books",
            row_number=2,
            data={
                "id": "",
                "type": "Book",
                "name": "A Book Without Wikidata",
                "creator": "Example Author",
            },
        )

        validate_rows(FAMILIES["books"], [row], Path("books.csv"))
        self.assertEqual(row.stable_id, "a-book-without-wikidata")

    def test_films_accept_generated_qid_id(self):
        row = ContentRow(
            family="films",
            row_number=2,
            data={
                "id": "",
                "type": "film",
                "name": "Le son des souvenirs",
                "wikidata_url": "https://www.wikidata.org/wiki/Q118765520",
                "local_qid": "Q999",
            },
        )

        validate_rows(FAMILIES["films"], [row], Path("films.csv"))
        self.assertEqual(row.stable_id, "Q118765520")
        self.assertEqual(row.item_type, "Movie")

    def test_films_require_wikidata(self):
        row = ContentRow(
            family="films",
            row_number=2,
            data={
                "id": "film-test",
                "type": "Movie",
                "name": "A Film Without Wikidata",
            },
        )

        with self.assertRaises(ContentUpdateError):
            validate_rows(FAMILIES["films"], [row], Path("films.csv"))

    def test_id_helpers(self):
        self.assertEqual(wikidata_qid("https://www.wikidata.org/wiki/Q42"), "Q42")
        self.assertEqual(wikidata_qid("http://www.wikidata.org/entity/Q42"), "Q42")
        self.assertEqual(
            canonical_wikidata_url("http://www.wikidata.org/entity/Q42"),
            "https://www.wikidata.org/wiki/Q42",
        )
        self.assertEqual(slugify("Poussière d'homme"), "poussiere-d-homme")

    def test_wikibase_create_payload_uses_abstract_content_model(self):
        data = build_wikibase_content_item_data("The Odyssey", "Q131547207")
        self.assertEqual(
            data["claims"][INSTANCE_OF_PROPERTY][0]["mainsnak"]["datavalue"]["value"]["id"],
            ABSTRACT_CONTENT_ITEM,
        )
        self.assertEqual(len(data["claims"][MONOLINGUAL_CONTENT_PROPERTY]), 8)
        self.assertEqual(data["claims"]["P4"][0]["mainsnak"]["datavalue"]["value"], "Q131547207")
        self.assertEqual(data["labels"]["fr"]["value"], "The Odyssey")

    def test_wikibase_repair_payload_avoids_duplicate_existing_claims(self):
        existing_claims = {
            "P4": [
                {
                    "mainsnak": {
                        "datavalue": {
                            "value": "Q131547207",
                        }
                    }
                }
            ],
            "P40": [
                {
                    "mainsnak": {
                        "datavalue": {
                            "value": {"language": "en", "text": "The Odyssey"},
                        }
                    }
                }
            ],
        }
        data = build_wikibase_repair_data("The Odyssey", "Q131547207", existing_claims)
        self.assertNotIn("P4", data["claims"])
        self.assertIn(INSTANCE_OF_PROPERTY, data["claims"])
        self.assertEqual(len(data["claims"][MONOLINGUAL_CONTENT_PROPERTY]), 7)

    def test_ordered_list_render_is_idempotent_and_sorted(self):
        row = ContentRow(
            family="music",
            row_number=2,
            data={
                "id": "music-abba",
                "type": "MusicGroup",
                "name": "ABBA",
                "wikidata_url": "https://www.wikidata.org/wiki/Q18233",
                "local_qid": "Q100",
            },
        )
        html = """
        <html><body>
            <ol class="music-list">
                <li property="itemListElement" typeof="ListItem">
                    <span typeof="Person"><span property="name">Zaz</span>
                    <link property="sameAs" href="https://www.wikidata.org/wiki/Q3141268" /></span>
                </li>
            </ol>
        </body></html>
        """

        updated, added, skipped, repaired = render_content(FAMILIES["music"], [row], html, "en")
        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertLess(updated.index("ABBA"), updated.index("Zaz"))
        self.assertIn('data-q315-source="local:Q100"', updated)

        updated_again, added_again, skipped_again, repaired_again = render_content(
            FAMILIES["music"], [row], updated, "en"
        )
        self.assertEqual(added_again, 0)
        self.assertEqual(skipped_again, 1)
        self.assertEqual(repaired_again, 0)
        self.assertEqual(updated_again.count("ABBA"), 1)

    def test_existing_ordered_list_entry_gets_local_binding(self):
        row = ContentRow(
            family="music",
            row_number=2,
            data={
                "id": "music-zaz",
                "type": "Person",
                "name": "Zaz",
                "wikidata_url": "https://www.wikidata.org/wiki/Q3141268",
                "local_qid": "Q101",
            },
        )
        html = """
        <html><body>
            <ol class="music-list">
                <li property="itemListElement" typeof="ListItem">
                    <span typeof="Person"><span property="name">Zaz</span>
                    <link property="sameAs" href="https://www.wikidata.org/wiki/Q3141268" /></span>
                </li>
            </ol>
        </body></html>
        """

        updated, added, skipped, repaired = render_content(FAMILIES["music"], [row], html, "en")

        self.assertEqual(added, 0)
        self.assertEqual(skipped, 1)
        self.assertEqual(repaired, 1)
        self.assertIn('data-q315-source="local:Q101"', updated)
        self.assertIn('data-q315-function="local:Q4182"', updated)

    def test_museum_grid_uses_type_label_and_wikidata(self):
        row = ContentRow(
            family="museums",
            row_number=2,
            data={
                "id": "orsay",
                "type": "Museum",
                "name": "Musee d'Orsay",
                "wikidata_url": "https://www.wikidata.org/wiki/Q23402",
                "type_label": "Museum",
            },
        )
        html = '<html><body><div class="museums-grid"></div></body></html>'

        updated, added, skipped, repaired = render_content(FAMILIES["museums"], [row], html, "en")

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn('class="museum-card"', updated)
        self.assertIn("https://www.wikidata.org/wiki/Q23402", updated)

    def test_museum_ordered_list_fallback(self):
        row = ContentRow(
            family="museums",
            row_number=2,
            data={
                "id": "orsay",
                "type": "Museum",
                "name": "Musee d'Orsay",
                "wikidata_url": "https://www.wikidata.org/wiki/Q23402",
                "type_label": "Museum",
            },
        )
        html = """
        <html><body>
            <ol>
                <li property="itemListElement" typeof="ListItem">
                    <span typeof="Museum"><span property="name">Z Museum</span></span>
                    <span class="museum-type">Museum</span>
                </li>
            </ol>
        </body></html>
        """

        updated, added, skipped, repaired = render_content(FAMILIES["museums"], [row], html, "en")

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn("https://www.wikidata.org/wiki/Q23402", updated)
        decoded = html_lib.unescape(updated)
        self.assertLess(decoded.index("Musee d'Orsay"), decoded.index("Z Museum"))

    def test_quote_grid_finds_localized_category(self):
        row = ContentRow(
            family="quotes",
            row_number=2,
            data={
                "id": "quote-art",
                "type": "Quote",
                "category": "Art",
                "quote": "Have no fear of perfection.",
                "attribution": "Salvador Dali",
            },
        )
        html = """
        <html><body>
            <section class="quote-section">
                <h2 class="section-title">Art</h2>
                <div class="quotes-grid"></div>
            </section>
        </body></html>
        """

        updated, added, skipped, repaired = render_content(FAMILIES["quotes"], [row], html, "fr")

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn("Have no fear of perfection.", html_lib.unescape(updated))

    def test_quote_grid_adds_split_quote_bindings(self):
        row = ContentRow(
            family="quotes",
            row_number=2,
            data={
                "id": "quote-creativity",
                "type": "Quote",
                "category": "Creativity",
                "quote": "A long quote.",
                "attribution": "Isaac Asimov",
                "local_qid": "Q4304",
                "part_qids": "Q4634;Q4635",
                "attribution_qid": "Q6323",
            },
        )
        html = """
        <html><body>
            <section class="quote-section">
                <h2 class="section-title">Creativity</h2>
                <div class="quotes-grid"></div>
            </section>
        </body></html>
        """

        updated, added, skipped, repaired = render_content(FAMILIES["quotes"], [row], html, "en")

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn('data-q315-source="local:Q4304"', updated)
        self.assertIn('data-q315-parts="local:Q4634 local:Q4635"', updated)
        self.assertIn('data-q315-source="local:Q6323"', updated)

    def test_cv_render_formats_title_and_trailing_url(self):
        row = ContentRow(
            family="cv",
            row_number=2,
            data={
                "type": "CVEntry",
                "section": "journals",
                "year": "2026",
                "content": (
                    "Example Article, Alice Example, Journal Name, 2026, "
                    "https://doi.org/10.0000/example"
                ),
                "local_qid": "Q9000",
            },
        )
        html = '<section id="journals"><h3>Journals</h3></section>'

        updated, added, skipped, repaired = render_cv_text(html, [row], "en")

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn("<b>Example Article</b>, Alice Example", updated)
        self.assertIn(
            '2026 (<a href="https://doi.org/10.0000/example">Link</a>)',
            updated,
        )
        self.assertIn('data-q315-source="local:Q9000"', updated)

    def test_cv_render_localizes_link_text(self):
        row = ContentRow(
            family="cv",
            row_number=2,
            data={
                "type": "CVEntry",
                "section": "journals",
                "year": "2026",
                "content": "Example Article, Alice Example, 2026, https://example.org",
                "local_qid": "Q9000",
            },
        )
        html = '<section id="journals"><h3>Journals</h3></section>'

        updated, _added, _skipped, _repaired = render_cv_text(html, [row], "fr")

        self.assertIn('(<a href="https://example.org">Lien</a>)', updated)

    def test_cv_render_keeps_composed_part_rows_plain(self):
        row = ContentRow(
            family="cv",
            row_number=2,
            data={
                "type": "CVEntry",
                "section": "participation",
                "year": "2026",
                "content": "Wikimania 2026, July 2026, https://example.org/event",
                "local_qid": "Q8665",
                "part_qids": "Q8659 Q8661 Q8663 Q8664",
            },
        )
        html = '<section id="participation"><h3>Participation</h3></section>'

        updated, added, skipped, repaired = render_cv_text(html, [row], "en")

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn(
            'Wikimania 2026, July 2026 (<a href="https://example.org/event">Link</a>)',
            updated,
        )
        self.assertNotIn("<b>Wikimania 2026</b>", updated)

    def test_q315_cv_render_uses_part_qids(self):
        row = ContentRow(
            family="cv",
            row_number=2,
            data={
                "type": "CVEntry",
                "section": "participation",
                "year": "2026",
                "content": "Wikimania 2026, July 2026, https://example.org/event",
                "local_qid": "Q8665",
                "part_qids": "Q8659 Q8661 Q8663 Q8664",
            },
        )
        html = '<section id="participation"><h3>Participation</h3></section>'

        updated, added, skipped, repaired = render_q315_cv_text(html, [row])

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn('data-content="local:Q8665"', updated)
        self.assertIn('<q-call data-function="local:Q4182">', updated)
        self.assertIn('data-content="local:Q8659">Q8659</span>', updated)
        self.assertIn('data-content="local:Q8661">Q8661</span>', updated)

    def test_q315_cv_simple_render_uses_part_qids(self):
        row = ContentRow(
            family="cv",
            row_number=2,
            data={
                "type": "CVEntry",
                "section": "participation",
                "year": "2026",
                "local_qid": "Q8665",
                "simple_local_qid": "Q8665",
                "part_qids": "Q8659 Q8661 Q8663 Q8664",
            },
        )
        html = """
        <div class="section-header" id="participation"><h2>Participation</h2></div>
        <div class="bento-grid"></div>
        """

        updated, added, skipped, repaired = render_q315_cv_simple_text(html, [row])

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn('<div class="bento-card">', updated)
        self.assertIn('data-content="local:Q8665"', updated)
        self.assertIn('<q-call data-function="local:Q4182">', updated)

    def test_cv_simple_render_uses_q315_binding(self):
        row = ContentRow(
            family="cv",
            row_number=2,
            data={
                "type": "CVEntry",
                "target": "simple",
                "section": "participation",
                "year": "2026",
                "content": "Wikimania 2026, July 2026, https://example.org/event",
                "local_qid": "Q8665",
                "simple_local_qid": "Q8665",
                "part_qids": "Q8659 Q8661 Q8663 Q8664",
            },
        )
        html = """
        <div class="section-header" id="participation"><h2>Participation</h2></div>
        <div class="bento-grid">
            <div class="bento-card">
                <h3><span class="year-badge">2025</span></h3>
                <p>Older event</p>
            </div>
        </div>
        """

        updated, added, skipped, repaired = render_cv_simple_text(html, [row], "en")

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn('data-q315-source="local:Q8665"', updated)
        self.assertLess(updated.index("Wikimania 2026"), updated.index("Older event"))
        self.assertNotIn("<b>Wikimania 2026</b>", updated)

    def test_q315_ordered_list_appends_local_qid_entry(self):
        row = ContentRow(
            family="films",
            row_number=2,
            data={
                "type": "Movie",
                "name": "The Odyssey",
                "wikidata_url": "https://www.wikidata.org/wiki/Q131547207",
                "local_qid": "Q8649",
            },
        )
        html = """
        <html><body>
            <ol class="media-list">
                <li property="itemListElement" typeof="ListItem">
                    <span typeof="Movie">
                        <span property="name" data-content="local:Q7303">Q7303</span>
                        <link property="sameAs" href="https://www.wikidata.org/wiki/Q138299163" />
                    </span>
                </li>
            </ol>
        </body></html>
        """

        updated, added, skipped, repaired = render_q315_content(FAMILIES["films"], [row], html)

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn('data-content="local:Q8649">Q8649</span>', updated)
        self.assertIn("https://www.wikidata.org/wiki/Q131547207", updated)

    def test_q315_wikidata_matching_uses_exact_qid(self):
        row = ContentRow(
            family="music",
            row_number=2,
            data={
                "type": "Person",
                "name": "Frederic Chopin",
                "wikidata_url": "https://www.wikidata.org/wiki/Q1268",
                "local_qid": "Q7369",
            },
        )
        html = """
        <html><body>
            <ol class="music-list">
                <li property="itemListElement" typeof="ListItem">
                    <span typeof="MusicGroup">
                        <span property="name" data-content="local:Q7309">Q7309</span>
                        <link property="sameAs" href="https://www.wikidata.org/wiki/Q126826" />
                    </span>
                </li>
            </ol>
        </body></html>
        """

        updated, added, skipped, repaired = render_q315_content(FAMILIES["music"], [row], html)

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn('data-content="local:Q7309">Q7309</span>', updated)
        self.assertIn('data-content="local:Q7369">Q7369</span>', updated)

    def test_q315_quote_uses_existing_split_quote_function(self):
        row = ContentRow(
            family="quotes",
            row_number=2,
            data={
                "type": "Quote",
                "category": "Creativity",
                "quote": "A long quote.",
                "attribution": "Isaac Asimov",
                "local_qid": "Q4304",
                "part_qids": "Q4634|Q4635",
                "attribution_qid": "Q6323",
            },
        )
        html = """
        <html><body>
            <section class="quote-section">
                <h2 class="section-title">Creativity</h2>
                <div class="quotes-grid"></div>
            </section>
        </body></html>
        """

        updated, added, skipped, repaired = render_q315_content(FAMILIES["quotes"], [row], html)

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn('data-content="local:Q4304"', updated)
        self.assertIn('<q-call data-function="local:Q4182">', updated)
        self.assertIn('data-content="local:Q6323">Q6323</p>', updated)

    def test_photography_page_appends_to_section(self):
        row = ContentRow(
            family="photographies",
            row_number=2,
            data={
                "type": "Photograph",
                "page": "en/photography/bridges.html",
                "section": "France",
                "title": "A new bridge",
                "alt": "A new bridge",
                "src": "https://example.org/bridge.jpg",
                "location": "Lyon",
                "local_qid": "Q5000",
            },
        )
        html = """
        <html><body>
            <h3 class="country-title">France</h3>
            <div class="gallery-grid"></div>
        </body></html>
        """

        updated, added, skipped, repaired = render_photography_page(html, [row], "en")

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn('data-q315-source="local:Q5000"', updated)
        self.assertIn('src="https://example.org/bridge.jpg"', updated)
        self.assertIn("Lyon", updated)

    def test_photography_page_rejects_missing_section(self):
        row = ContentRow(
            family="photographies",
            row_number=2,
            data={
                "type": "Photograph",
                "page": "en/photography/bridges.html",
                "section": "Italy",
                "title": "A new bridge",
                "src": "https://example.org/bridge.jpg",
            },
        )
        html = """
        <html><body>
            <h3 class="country-title">France</h3>
            <div class="gallery-grid"></div>
        </body></html>
        """

        with self.assertRaises(ContentUpdateError):
            render_photography_page(html, [row], "en")

    def test_csv_rows_reject_extra_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "photographies.csv"
            csv_path.write_text(
                "id,type,page,section,title,alt,src,href,location,year,card_class,data_location,local_qid\n"
                ",Photograph,en/photography/example.html,France,Title,,https://example.org/a.jpg,,,,photo-card,,,Photograph\n",
                encoding="utf-8",
            )

            with self.assertRaises(ContentUpdateError):
                read_rows(FAMILIES["photographies"], csv_path)

    def test_photography_page_clones_q315_links_card(self):
        row = ContentRow(
            family="photographies",
            row_number=2,
            data={
                "type": "Photograph",
                "page": "Q315/Q3062/Q3025/Q3082/Q3154.html",
                "section": "Q3154",
                "title": "A new canal",
                "src": "https://example.org/canal.jpg",
                "href": "Q3154.html",
                "data_location": "Canal",
            },
        )
        html = """
        <html><body>
            <section class="city-section">
                <h4 class="city-name">Q3154</h4>
                <div class="links">
                    <ul>
                        <li>
                            <a data-location="Bridge" href="Q3154.html">
                                <div class="azure-scan"></div>
                                <img alt="" src="https://example.org/old.jpg" />
                            </a>
                        </li>
                    </ul>
                </div>
            </section>
        </body></html>
        """

        updated, added, skipped, repaired = render_photography_page(html, [row], "en")

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn('data-location="Canal"', updated)
        self.assertIn('src="https://example.org/canal.jpg"', updated)
        self.assertIn('alt=""', updated)
        self.assertIn("azure-scan", updated)

    def test_q315_photography_family_uses_travel_pipeline(self):
        row = ContentRow(
            family="photographies",
            row_number=2,
            data={
                "type": "Photograph",
                "page": "Q315/Q3062/Q3025/Q3082/Q3154.html",
                "section": "Q3154",
                "title": "A new canal",
                "src": "https://example.org/canal.jpg",
                "href": "Q3154.html",
                "data_location": "Canal",
            },
        )

        with self.assertRaisesRegex(ContentUpdateError, "abstract travel pipeline"):
            render_q315_family(FAMILIES["photographies"], [row], apply=False)

    def test_q315_cv_appends_under_existing_year(self):
        row = ContentRow(
            family="cv",
            row_number=2,
            data={
                "type": "CVEntry",
                "section": "journals",
                "year": "2026",
                "content": "A new journal article.",
                "local_qid": "Q9001",
            },
        )
        html = """
        <html><body>
            <section id="journals">
                <h3>Q3699</h3>
                <h4 class="year">Q3668</h4>
                <p class="conference" data-content="local:Q8401">Q8401</p>
                <h4 class="year">Q3669</h4>
                <p class="conference" data-content="local:Q8402">Q8402</p>
            </section>
        </body></html>
        """

        updated, added, skipped, repaired = render_q315_cv_text(html, [row])

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn('<p class="conference" data-content="local:Q9001">Q9001</p>', updated)
        self.assertLess(updated.index("Q9001"), updated.index("Q3669"))

    def test_q315_cv_creates_new_year_heading(self):
        row = ContentRow(
            family="cv",
            row_number=2,
            data={
                "type": "CVEntry",
                "section": "conferences",
                "year": "2026",
                "content": "A new conference paper.",
                "local_qid": "Q9002",
            },
        )
        html = """
        <html><body>
            <section id="conferences">
                <h3>Q3708</h3>
                <h4 class="year">Q3669</h4>
                <p class="conference" data-content="local:Q8402">Q8402</p>
            </section>
        </body></html>
        """

        updated, added, skipped, repaired = render_q315_cv_text(html, [row])

        self.assertEqual(added, 1)
        self.assertEqual(skipped, 0)
        self.assertEqual(repaired, 0)
        self.assertIn('<h4 class="year">Q3668</h4>', updated)
        self.assertLess(updated.index("Q3668"), updated.index("Q3669"))

    def test_cv_wikibase_payload_can_use_localized_content(self):
        row = ContentRow(
            family="cv",
            row_number=2,
            data={
                "type": "CVEntry",
                "section": "talks",
                "year": "2026",
                "content": "English entry",
                "content_fr": "Entrée française",
            },
        )

        data = build_wikibase_content_item_data(
            "English entry",
            "",
            content_texts_for_wikibase(row),
        )

        p40 = data["claims"][MONOLINGUAL_CONTENT_PROPERTY]
        self.assertTrue(any(claim["mainsnak"]["datavalue"]["value"]["language"] == "fr" and claim["mainsnak"]["datavalue"]["value"]["text"] == "Entrée française" for claim in p40))


class LegacyApplyGuardTests(unittest.TestCase):
    """--mode apply must not write pages that the Q315 renderer owns."""

    def test_apply_refuses_for_q315_owned_family(self):
        with self.assertRaises(ContentUpdateError) as raised:
            render_family(FAMILIES["museums"], [], apply=True)
        message = str(raised.exception)
        self.assertIn("Q315/Q3638/Q3643.html", message)
        self.assertIn("q315-apply", message)

    def test_every_q315_owned_family_is_guarded(self):
        for name, family in FAMILIES.items():
            if not family.q315_path:
                continue
            with self.subTest(family=name):
                with self.assertRaises(ContentUpdateError):
                    render_family(family, [], apply=True)

    def test_preview_stays_available_as_a_diagnostic(self):
        changes = render_family(FAMILIES["museums"], [], apply=False)
        self.assertTrue(changes)
        self.assertFalse(any(change.changed for change in changes))

    def test_photographies_keeps_the_legacy_apply_path(self):
        self.assertEqual(FAMILIES["photographies"].q315_path, "")
        self.assertEqual(render_family(FAMILIES["photographies"], [], apply=True), [])


class CheckModeTests(unittest.TestCase):
    """--mode check asserts each Q315 source is already in sync with its CSV."""

    BOOKS_HEADER = "id,type,name,creator,wikidata_url,local_qid\n"

    @staticmethod
    def run_check(*argv):
        """Run the CLI with its reporting captured, returning the exit code."""
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            exit_code = main(["--mode", "check", *argv])
        return exit_code, out.getvalue() + err.getvalue()

    def test_check_passes_when_the_source_is_in_sync(self):
        exit_code, report = self.run_check("--family", "books")
        self.assertEqual(exit_code, 0)
        self.assertIn("Check passed", report)

    def test_check_fails_when_a_csv_row_is_missing_from_the_source(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "books.csv").write_text(
                self.BOOKS_HEADER
                + ",Book,A Book That Is Not On The Abstract Page,Nobody,,Q999999\n",
                encoding="utf-8",
            )
            exit_code, report = self.run_check(
                "--family", "books", "--input-dir", directory
            )
        self.assertEqual(exit_code, 1)
        self.assertIn("out of sync", report)
        self.assertIn("added=1", report)

    def test_check_does_not_write_to_the_source_page(self):
        source = FAMILIES["books"].q315_target
        before = source.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "books.csv").write_text(
                self.BOOKS_HEADER
                + ",Book,A Book That Is Not On The Abstract Page,Nobody,,Q999999\n",
                encoding="utf-8",
            )
            self.run_check("--family", "books", "--input-dir", directory)
        self.assertEqual(source.read_text(encoding="utf-8"), before)

    def test_check_covers_every_family_with_a_q315_source(self):
        exit_code, report = self.run_check()
        self.assertEqual(exit_code, 0)
        for name, family in FAMILIES.items():
            with self.subTest(family=name):
                if family.q315_path:
                    self.assertIn(family.q315_path, report)


class UnicodeIdentityTests(unittest.TestCase):
    """Names outside the Latin script must still produce ids and match reliably."""

    def test_slugify_falls_back_to_a_digest_for_non_latin_names(self):
        for name in ("സംഗീതം", "ਸੰਗੀਤ", "संगीत"):
            with self.subTest(name=name):
                self.assertTrue(slugify(name))

    def test_slugify_keeps_distinct_names_distinct(self):
        self.assertNotEqual(
            slugify("സംഗീതം"),
            slugify("ਸੰਗੀਤ"),
        )

    def test_slugify_is_unchanged_for_ascii_names(self):
        self.assertEqual(slugify("The Trial"), "the-trial")
        self.assertEqual(slugify(""), "")

    def test_non_latin_row_gets_a_stable_id(self):
        row = ContentRow(
            family="books",
            row_number=2,
            data={"type": "Book", "name": "സംഗീതം"},
        )
        self.assertTrue(row.stable_id)
        validate_rows(FAMILIES["books"], [row], Path("books.csv"))

    def test_normalize_text_matches_across_unicode_forms(self):
        import unicodedata

        composed = "Mus\u00e9e"
        decomposed = unicodedata.normalize("NFD", composed)
        self.assertNotEqual(composed, decomposed)
        self.assertEqual(normalize_text(composed), normalize_text(decomposed))


class BindingDiffTests(unittest.TestCase):
    """--mode diff compares CSV QID columns against the Q315 source both ways."""

    BOOK_PAGE = """<html><body>
        <nav><ol class="breadcrumb">
            <li><span property="name" data-content="local:Q4050">Q4050</span></li>
        </ol></nav>
        <ol class="book-list">
            <li class="book-item">
                <span class="book-title" typeof="Book"><span property="name" data-content="local:Q10">Q10</span></span>
                <span class="book-author" data-content="local:Q11">Q11</span>
            </li>
            <li class="book-item">
                <span class="book-title" typeof="Book"><span property="name" data-content="local:Q20">Q20</span></span>
                <span class="book-author" data-content="local:Q21">Q21</span>
            </li>
        </ol>
    </body></html>"""

    @staticmethod
    def book_row(name, local_qid, creator_qid=""):
        return ContentRow(
            family="books",
            row_number=2,
            data={
                "type": "Book",
                "name": name,
                "creator": "Someone" if creator_qid else "",
                "creator_qid": creator_qid,
                "local_qid": local_qid,
            },
        )

    def test_csv_bound_qids_collects_every_qid_column(self):
        row = ContentRow(
            family="quotes",
            row_number=2,
            data={
                "type": "Quote",
                "quote": "A quote",
                "attribution": "Someone",
                "category": "Art",
                "local_qid": "Q1",
                "attribution_qid": "Q2",
                "part_qids": "Q3;Q4",
            },
        )
        self.assertEqual(csv_bound_qids(row), {"Q1", "Q2", "Q3", "Q4"})

    def test_csv_bound_qids_ignores_blank_and_malformed_values(self):
        row = ContentRow(
            family="books",
            row_number=2,
            data={"type": "Book", "name": "A", "local_qid": "Q1", "creator_qid": "not-a-qid"},
        )
        self.assertEqual(csv_bound_qids(row), {"Q1"})

    def test_content_qids_ignore_bindings_outside_the_entry_container(self):
        qids = q315_content_qids(FAMILIES["books"], self.BOOK_PAGE)
        self.assertEqual(qids, {"Q10", "Q11", "Q20", "Q21"})
        self.assertNotIn("Q4050", qids)

    def test_creator_pairs_map_name_qid_to_author_qid(self):
        self.assertEqual(q315_creator_pairs(self.BOOK_PAGE), {"Q10": "Q11", "Q20": "Q21"})

    def test_backfill_fills_only_empty_creator_qids(self):
        rows = [self.book_row("First", "Q10"), self.book_row("Second", "Q20", "Q999")]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Q3640.html"
            source.write_text(self.BOOK_PAGE, encoding="utf-8")
            family = replace(FAMILIES["books"], q315_path=str(source))
            filled = backfill_q315_qids(family, rows)
        self.assertEqual(filled, 1)
        self.assertEqual(rows[0].data["creator_qid"], "Q11")
        self.assertEqual(rows[1].data["creator_qid"], "Q999")

    def test_derived_qids_cover_museum_type_labels(self):
        museum = ContentRow(
            family="museums",
            row_number=2,
            data={"type": "Museum", "name": "A Museum", "local_qid": "Q1"},
        )
        gallery = ContentRow(
            family="museums",
            row_number=3,
            data={"type": "ArtGallery", "name": "A Gallery", "local_qid": "Q2"},
        )
        self.assertEqual(
            derived_q315_qids(FAMILIES["museums"], [museum, gallery]),
            {"Q3351", "Q7478"},
        )
        self.assertEqual(derived_q315_qids(FAMILIES["books"], []), set())

    def test_diff_reports_both_directions(self):
        rows = [self.book_row("First", "Q10", "Q11"), self.book_row("Ghost", "Q99", "Q98")]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Q3640.html"
            source.write_text(self.BOOK_PAGE, encoding="utf-8")
            family = replace(FAMILIES["books"], q315_path=str(source))
            diff = diff_q315_family(family, rows)
        self.assertEqual(diff.missing, ("Q98", "Q99"))
        self.assertEqual(diff.orphaned, ("Q20", "Q21"))
        self.assertFalse(diff.clean)

    def test_diff_is_clean_when_both_sides_agree(self):
        rows = [self.book_row("First", "Q10", "Q11"), self.book_row("Second", "Q20", "Q21")]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Q3640.html"
            source.write_text(self.BOOK_PAGE, encoding="utf-8")
            family = replace(FAMILIES["books"], q315_path=str(source))
            diff = diff_q315_family(family, rows)
        self.assertTrue(diff.clean)
        self.assertEqual(diff.checked, 4)

    def test_append_only_families_report_no_orphans(self):
        self.assertFalse(FAMILIES["cv"].mirrors_q315)
        for name in ("books", "films", "music", "museums", "quotes"):
            with self.subTest(family=name):
                self.assertTrue(FAMILIES[name].mirrors_q315)

    def test_books_csv_round_trips_its_author_bindings(self):
        """Regression guard: books.csv must express every binding on Q3640."""
        family = FAMILIES["books"]
        rows = read_rows(family, REPO_ROOT / "data/content-updates" / family.csv_name)
        diff = diff_q315_family(family, rows)
        self.assertEqual(diff.missing, ())
        self.assertEqual(diff.orphaned, ())

    def test_new_book_row_renders_a_bound_author(self):
        row = self.book_row("A New Book", "Q500", "Q501")
        markup = build_q315_list_item_html(FAMILIES["books"], row)
        self.assertIn('data-content="local:Q501"', markup)
        self.assertIn('data-content="local:Q500"', markup)

    def test_book_row_without_a_creator_qid_falls_back_to_plain_text(self):
        row = ContentRow(
            family="books",
            row_number=2,
            data={"type": "Book", "name": "A New Book", "creator": "Someone", "local_qid": "Q500"},
        )
        markup = build_q315_list_item_html(FAMILIES["books"], row)
        self.assertIn(">Someone<", markup)


class SourceBindingRepairTests(unittest.TestCase):
    """Q315 sources must bind every entry, not carry a bare QID as text."""

    @staticmethod
    def museum_row(local_qid, item_type="Museum"):
        return ContentRow(
            family="museums",
            row_number=2,
            data={
                "type": item_type,
                "name": "A Museum",
                "wikidata_url": "https://www.wikidata.org/wiki/Q1",
                "local_qid": local_qid,
            },
        )

    def test_bind_first_tag_adds_the_binding_once(self):
        block = '<h2 class="museum-name" typeof="Museum">Q10</h2>'
        bound = bind_first_tag(block, r"h2", r"museum-name", "Q10")
        self.assertEqual(
            bound, '<h2 class="museum-name" typeof="Museum" data-content="local:Q10">Q10</h2>'
        )
        self.assertEqual(bind_first_tag(bound, r"h2", r"museum-name", "Q10"), bound)

    def test_bind_first_tag_ignores_a_tag_that_is_already_bound(self):
        block = '<h2 class="museum-name" data-content="local:Q99">Q99</h2>'
        self.assertEqual(bind_first_tag(block, r"h2", r"museum-name", "Q10"), block)

    def test_museum_repair_binds_a_bare_qid_heading(self):
        block = (
            '<article class="museum-card">'
            '<h2 class="museum-name" typeof="Museum">Q10</h2>'
            '<span class="museum-type" data-content="local:Q3351">Q3351</span>'
            "</article>"
        )
        repaired = repair_q315_museum_block(block, self.museum_row("Q10"))
        self.assertIn('data-content="local:Q10"', repaired)

    def test_museum_repair_is_idempotent(self):
        block = '<article class="museum-card"><h2 class="museum-name">Q10</h2></article>'
        row = self.museum_row("Q10")
        once = repair_q315_museum_block(block, row)
        self.assertEqual(repair_q315_museum_block(once, row), once)

    def test_new_museum_card_is_born_bound(self):
        markup = build_q315_museum_card_html(self.museum_row("Q10"))
        self.assertIn('data-content="local:Q10"', markup)

    def test_blocked_items_are_left_unbound(self):
        qid = "Q4242"
        with mock.patch.object(content_update, "UNBOUND_CONTENT_QIDS", frozenset({qid})):
            block = f'<article class="museum-card"><h2 class="museum-name">{qid}</h2></article>'
            self.assertEqual(repair_q315_museum_block(block, self.museum_row(qid)), block)
            markup = build_q315_museum_card_html(self.museum_row(qid))
            # The type-label binding is unrelated and must stay; only the name is unbound.
            self.assertIn(f'<h2 class="museum-name" typeof="Museum">{qid}</h2>', markup)
            self.assertIn('class="museum-type" data-content=', markup)

    def test_nothing_is_currently_blocked(self):
        self.assertEqual(UNBOUND_CONTENT_QIDS, frozenset())

    def test_quote_attribution_repair_binds_the_author_line(self):
        row = ContentRow(
            family="quotes",
            row_number=2,
            data={
                "type": "Quote",
                "category": "Art",
                "quote": "A quote",
                "attribution": "Someone",
                "local_qid": "Q10",
                "attribution_qid": "Q11",
            },
        )
        html = (
            '<div class="quotes-grid">'
            '<div class="quote-card">'
            '<p class="quote-text" data-content="local:Q10">Q10</p>'
            '<p class="quote-author">Q11</p>'
            "</div></div>"
        )
        repaired = repair_q315_quote_attribution(html, row)
        self.assertIn('<p class="quote-author" data-content="local:Q11">Q11</p>', repaired)
        self.assertEqual(repair_q315_quote_attribution(repaired, row), repaired)

    def test_quote_attribution_repair_skips_rows_without_a_qid(self):
        row = ContentRow(
            family="quotes",
            row_number=2,
            data={
                "type": "Quote",
                "category": "Art",
                "quote": "A quote",
                "attribution": "Someone",
                "local_qid": "Q10",
            },
        )
        html = '<div class="quote-card"><p class="quote-text" data-content="local:Q10">Q10</p><p class="quote-author">Someone</p></div>'
        self.assertEqual(repair_q315_quote_attribution(html, row), html)

    def test_quote_attribution_repair_targets_the_matching_card(self):
        row = ContentRow(
            family="quotes",
            row_number=2,
            data={
                "type": "Quote",
                "category": "Art",
                "quote": "A quote",
                "attribution": "Someone",
                "local_qid": "Q20",
                "attribution_qid": "Q21",
            },
        )
        html = (
            '<div class="quote-card"><p class="quote-text" data-content="local:Q10">Q10</p>'
            '<p class="quote-author">Q11</p></div>'
            '<div class="quote-card"><p class="quote-text" data-content="local:Q20">Q20</p>'
            '<p class="quote-author">Q21</p></div>'
        )
        repaired = repair_q315_quote_attribution(html, row)
        self.assertIn('<p class="quote-author">Q11</p>', repaired)
        self.assertIn('<p class="quote-author" data-content="local:Q21">Q21</p>', repaired)

    def test_quote_builder_already_binds_a_known_attribution(self):
        row = ContentRow(
            family="quotes",
            row_number=2,
            data={
                "type": "Quote",
                "category": "Art",
                "quote": "A quote",
                "attribution": "Someone",
                "local_qid": "Q10",
                "attribution_qid": "Q11",
            },
        )
        self.assertIn('data-content="local:Q11"', build_q315_quote_card_html(row))

    def test_quote_source_has_no_unbound_entries(self):
        """Regression guard: every quote entry on the source carries its binding."""
        family = FAMILIES["quotes"]
        rows = read_rows(family, REPO_ROOT / "data/content-updates" / family.csv_name)
        self.assertEqual(diff_q315_family(family, rows).missing, ())

    def test_a_container_with_a_blocked_entry_stays_wholly_unbound(self):
        """Positional rendering makes partial binding unsafe, so bind all or none."""
        blocked = "Q4242"
        with mock.patch.object(content_update, "UNBOUND_CONTENT_QIDS", frozenset({blocked})):
            self.assertFalse(
                museum_entries_are_bindable([self.museum_row("Q10"), self.museum_row(blocked)])
            )
            self.assertTrue(
                museum_entries_are_bindable([self.museum_row("Q10"), self.museum_row("Q20")])
            )

    def test_a_blocked_entry_leaves_the_whole_museum_source_untouched(self):
        family = FAMILIES["museums"]
        rows = read_rows(family, REPO_ROOT / "data/content-updates" / family.csv_name)
        source = family.q315_target.read_text(encoding="utf-8")
        with mock.patch.object(
            content_update, "UNBOUND_CONTENT_QIDS", frozenset({rows[0].local_qid})
        ):
            self.assertFalse(museum_entries_are_bindable(rows))
            unbound_source = re.sub(r' data-content="local:Q\d+"(?=>Q)', "", source)
            updated, added, _skipped, repaired = render_q315_content(
                family, rows, unbound_source
            )
        self.assertEqual((added, repaired), (0, 0))
        self.assertEqual(updated, unbound_source)

    def test_museums_source_binds_every_entry(self):
        """Regression guard: all 31 museum names carry their binding."""
        family = FAMILIES["museums"]
        rows = read_rows(family, REPO_ROOT / "data/content-updates" / family.csv_name)
        self.assertTrue(museum_entries_are_bindable(rows))
        diff = diff_q315_family(family, rows)
        self.assertEqual(diff.missing, ())
        self.assertEqual(diff.orphaned, ())


if __name__ == "__main__":
    unittest.main()
