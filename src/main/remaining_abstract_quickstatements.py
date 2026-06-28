#!/usr/bin/env python3
"""Prepare abstract items for complete eight-language non-travel pages."""

from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import unquote, urlsplit

from abstract_quickstatements import (
    LANGUAGES,
    clean_title,
    parse_page,
    quickstatements_quote,
)
from paths import REPO_ROOT
from wikibase_quickstatements import LANGUAGE_ITEMS


GROUPS = {
    "home": {
        "en": "en/index.html",
        "fr": "fr/index.html",
        "ml": "ml/index.html",
        "pa": "pa/index.html",
        "hi": "hi/index.html",
        "pt": "pt/index.html",
        "es": "es/index.html",
        "it": "it/index.html",
    },
    "about": {
        "en": "en/about.html",
        "fr": "fr/apropos.html",
        "ml": "ml/എന്നെക്കുറിച്ച്.html",
        "pa": "pa/ਮੇਰੇ-ਬਾਰੇ.html",
        "hi": "hi/मेरे-बारे-मेँ.html",
        "pt": "pt/sobre.html",
        "es": "es/sobre-mi.html",
        "it": "it/chi-sono.html",
    },
    "blog": {
        "en": "en/blog.html",
        "fr": "fr/blog.html",
        "ml": "ml/ബ്ലോഗ്.html",
        "pa": "pa/ਬਲਾਗ.html",
        "hi": "hi/ब्लॉग.html",
        "pt": "pt/blog.html",
        "es": "es/blog.html",
        "it": "it/blog.html",
    },
    "disclaimer": {
        "en": "en/disclaimer.html",
        "fr": "fr/avertissement.html",
        "ml": "ml/നിരാകരണം.html",
        "pa": "pa/ਬੇਦਾਅਵਾ.html",
        "hi": "hi/अस्वीकरण.html",
        "pt": "pt/aviso-legal.html",
        "es": "es/aviso-legal.html",
        "it": "it/disclaimer.html",
    },
    "research": {
        "en": "en/research/index.html",
        "fr": "fr/recherche/index.html",
        "ml": "ml/ഗവേഷണം/index.html",
        "pa": "pa/ਖੋਜ/index.html",
        "hi": "hi/अनुसंधान/index.html",
        "pt": "pt/pesquisa/index.html",
        "es": "es/investigación/index.html",
        "it": "it/ricerca/index.html",
    },
    "cv-detailed": {
        "en": "en/research/cv-detailed.html",
        "fr": "fr/recherche/cv-détaillé.html",
        "ml": "ml/ഗവേഷണം/വിശദമായ-സിവി.html",
        "pa": "pa/ਖੋਜ/ਵਿਸਤ੍ਰਿਤ-ਸੀਵੀ.html",
        "hi": "hi/अनुसंधान/विस्तृत-सीवी.html",
        "pt": "pt/pesquisa/cv-detalhado.html",
        "es": "es/investigación/cv-detallado.html",
        "it": "it/ricerca/cv-dettagliato.html",
    },
    "writings": {
        "en": "en/writings/index.html",
        "fr": "fr/ecrits/index.html",
        "ml": "ml/രചനകൾ/index.html",
        "pa": "pa/ਲਿਖਤਾਂ/index.html",
        "hi": "hi/रचनायें/index.html",
        "pt": "pt/escritos/index.html",
        "es": "es/escritos/index.html",
        "it": "it/scritti/index.html",
    },
    "quotes": {
        "en": "en/writings/quotes.html",
        "fr": "fr/ecrits/citations.html",
        "ml": "ml/രചനകൾ/ഉദ്ധരണികൾ.html",
        "pa": "pa/ਲਿਖਤਾਂ/ਹਵਾਲੇ.html",
        "hi": "hi/रचनायें/उद्धरण.html",
        "pt": "pt/escritos/citações.html",
        "es": "es/escritos/citas.html",
        "it": "it/scritti/citazioni.html",
    },
    "books": {
        "en": "en/writings/books-i-read.html",
        "fr": "fr/ecrits/livres-lus.html",
        "ml": "ml/രചനകൾ/വായിച്ച-പുസ്തകങ്ങൾ.html",
        "pa": "pa/ਲਿਖਤਾਂ/ਪੜ੍ਹੀਆਂ  ਕਿਤਾਬਾਂ.html",
        "hi": "hi/रचनायें/पढ़ी हुई पुस्तकें.html",
        "pt": "pt/escritos/livros-lidos.html",
        "es": "es/escritos/libros-leídos.html",
        "it": "it/scritti/libri-letti.html",
    },
    "films": {
        "en": "en/writings/films-series-documentaries.html",
        "fr": "fr/ecrits/films-séries-documentaires.html",
        "ml": "ml/രചനകൾ/സിനിമകൾ-പരമ്പരകൾ-ഡോക്യുമെന്ററികൾ.html",
        "pa": "pa/ਲਿਖਤਾਂ/ਫਿਲਮਾਂ-ਲੜੀਵਾਰ-ਦਸਤਾਵੇਜ਼ੀ ਫਿਲਮਾਂ.html",
        "hi": "hi/रचनायें/फिल्म-श्रृंखला-वृत्तचित्र.html",
        "pt": "pt/escritos/filmes-séries-documentários.html",
        "es": "es/escritos/películas-series-documentales.html",
        "it": "it/scritti/film-serie-documentari.html",
    },
    "music": {
        "en": "en/writings/music.html",
        "fr": "fr/ecrits/musique.html",
        "ml": "ml/രചനകൾ/സംഗീതം.html",
        "pa": "pa/ਲਿਖਤਾਂ/ਸੰਗੀਤ.html",
        "hi": "hi/रचनायें/संगीत.html",
        "pt": "pt/escritos/música.html",
        "es": "es/escritos/música.html",
        "it": "it/scritti/musica.html",
    },
    "museums": {
        "en": "en/writings/museums-galleries.html",
        "fr": "fr/ecrits/musées-galeries.html",
        "ml": "ml/രചനകൾ/മ്യൂസിയങ്ങൾ-ഗാലറികൾ.html",
        "pa": "pa/ਲਿਖਤਾਂ/ਅਜਾਇਬ-ਘਰ-ਗੈਲਰੀਆਂ.html",
        "hi": "hi/रचनायें/संग्रहालय-दीर्घाएँ.html",
        "pt": "pt/escritos/museus-galerias.html",
        "es": "es/escritos/museos-galerías.html",
        "it": "it/scritti/musei-gallerie.html",
    },
    "iohannes": {
        "en": "en/writings/Iohannes.html",
        "fr": "fr/ecrits/Iohannes.html",
        "ml": "ml/രചനകൾ/യോഹന്നെസ്.html",
        "pa": "pa/ਲਿਖਤਾਂ/ਯੋਹਾਨੇਸ.html",
        "hi": "hi/रचनायें/योहान्नेस.html",
        "pt": "pt/escritos/Iohannes.html",
        "es": "es/escritos/Iohannes.html",
        "it": "it/scritti/Iohannes.html",
    },
    "search": {
        "en": "en/search.html",
        "fr": "fr/recherche.html",
        "ml": "ml/തിരയൽ.html",
        "pa": "pa/ਖੋਜ.html",
        "hi": "hi/खोज.html",
        "pt": "pt/search.html",
        "es": "es/search.html",
        "it": "it/search.html",
    },
}

DESCRIPTIONS = {
    "en": "language-independent page on John Samuel's website",
    "fr": "page indépendante de la langue du site de John Samuel",
    "ml": "ജോൺ സാമുവലിന്റെ വെബ്‌സൈറ്റിലെ ഭാഷാ-സ്വതന്ത്ര താൾ",
    "pa": "ਜੌਨ ਸੈਮੂਅਲ ਦੀ ਵੈੱਬਸਾਈਟ ਦਾ ਭਾਸ਼ਾ-ਸੁਤੰਤਰ ਸਫ਼ਾ",
    "hi": "जॉन सैमुअल की वेबसाइट का भाषा-स्वतंत्र पृष्ठ",
    "pt": "página independente do idioma no sítio de John Samuel",
    "es": "página independiente del idioma del sitio de John Samuel",
    "it": "pagina indipendente dalla lingua del sito di John Samuel",
}


def page_items() -> dict[str, str]:
    result: dict[str, str] = {}
    with (REPO_ROOT / "pages.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        for row in csv.DictReader(source):
            path = unquote(urlsplit(row["url"]).path).lstrip("/")
            result[path] = row["item"].rstrip("/").split("/")[-1]
    return result


def main() -> int:
    pages = page_items()
    blocks: list[str] = []
    links: list[str] = []
    manifest: list[tuple[str, str, str, str]] = []
    missing_pages: list[str] = []
    missing_page_blocks: list[str] = []
    missing_seen: set[str] = set()
    for number, (key, paths) in enumerate(GROUPS.items()):
        token = "Q315" if key == "home" else f"A{number:04d}"
        for language, relative in paths.items():
            if not (REPO_ROOT / relative).is_file():
                raise FileNotFoundError(relative)
            concrete = pages.get(relative)
            if concrete:
                links.append(f"{concrete}|P12|{token}")
            else:
                missing_pages.append(relative)
                if relative not in missing_seen:
                    missing_seen.add(relative)
                    path = REPO_ROOT / relative
                    title = clean_title(parse_page(path).title, language)
                    url = f"https://johnsamuel.info/{relative}"
                    missing_page_blocks.append(
                        "\n".join(
                            (
                                "CREATE",
                                'LAST|Den|"web page"',
                                'LAST|Dfr|"page web"',
                                f'LAST|L{language}|'
                                f'"{quickstatements_quote(title)}"',
                                f'LAST|P27|{language}:'
                                f'"{quickstatements_quote(title)}"',
                                f"LAST|P17|{LANGUAGE_ITEMS[language]}",
                                "LAST|P8|Q45",
                                f'LAST|P3|"{quickstatements_quote(url)}"',
                                "LAST|P13|Q1041",
                                "LAST|P15|Q42761025",
                            )
                        )
                    )
            manifest.append((token, key, language, relative))
        if key == "home":
            continue
        statements = ["CREATE"]
        for language in LANGUAGES:
            path = REPO_ROOT / paths[language]
            label = clean_title(parse_page(path).title, language)
            statements.append(
                f'LAST|L{language}|"{quickstatements_quote(label)}"'
            )
            statements.append(
                f'LAST|D{language}|'
                f'"{quickstatements_quote(DESCRIPTIONS[language])}"'
            )
        for language in LANGUAGES:
            path = Path(paths[language])
            segment = path.parent.name if path.name == "index.html" else path.stem
            statements.append(
                f'LAST|P38|{language}:"{quickstatements_quote(segment)}"'
            )
            statements.append(
                f'LAST|P39|{language}:'
                f'"{quickstatements_quote(path.relative_to(language).as_posix())}"'
            )
        statements.append("LAST|P8|Q3017")
        blocks.append("\n".join(statements))
    (REPO_ROOT / "quickstatements-remaining-abstract-items.txt").write_text(
        "\n\n".join(blocks) + "\n", encoding="utf-8"
    )
    (REPO_ROOT / "quickstatements-link-remaining-pages.template.txt").write_text(
        "\n".join(links) + "\n", encoding="utf-8"
    )
    with (REPO_ROOT / "remaining-abstract-pages.template.csv").open(
        "w", encoding="utf-8", newline=""
    ) as destination:
        writer = csv.writer(destination)
        writer.writerow(("abstract_item", "group", "language", "path"))
        writer.writerows(manifest)
    (REPO_ROOT / "remaining-abstract-missing-pages.txt").write_text(
        "\n".join(missing_pages) + ("\n" if missing_pages else ""),
        encoding="utf-8",
    )
    (REPO_ROOT / "quickstatements-missing-concrete-pages.txt").write_text(
        "\n\n".join(missing_page_blocks)
        + ("\n" if missing_page_blocks else ""),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(GROUPS) - 1} item blocks and {len(links)} page links; "
        f"{len(missing_pages)} concrete pages are absent from pages.csv"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
