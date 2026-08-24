import unittest
import html as html_lib
import tempfile
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from content_update import (
    ABSTRACT_CONTENT_ITEM,
    ContentRow,
    ContentUpdateError,
    FAMILIES,
    INSTANCE_OF_PROPERTY,
    MONOLINGUAL_CONTENT_PROPERTY,
    build_wikibase_content_item_data,
    build_wikibase_repair_data,
    canonical_wikidata_url,
    content_texts_for_wikibase,
    read_rows,
    render_content,
    render_q315_family,
    render_q315_content,
    render_q315_cv_text,
    render_photography_page,
    slugify,
    validate_rows,
    wikidata_qid,
)


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


if __name__ == "__main__":
    unittest.main()
