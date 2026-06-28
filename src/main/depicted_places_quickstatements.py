#!/usr/bin/env python3
"""Generate abstract items for depicted places without local Wikibase IDs."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from abstract_quickstatements import LANGUAGES, groups, quickstatements_quote
from paths import REPO_ROOT


DEPICTED_PLACE_CLASS = "Q3176"
TARGETS = {
    "Suomenlinna": "Q3101",
    "Pont-en-Royans": "Q3073",
    "Erfurt": "Q3074",
    "Rothenburg": "Q3074",
    "Porto Bridge": "Q3157",
    "Oude Kerk": "Q3171",
    "Nieuwe Kerk": "Q3171",
}
PROPER_NAME_LABELS = {
    "Oude Kerk": {language: "Oude Kerk" for language in LANGUAGES},
    "Nieuwe Kerk": {language: "Nieuwe Kerk" for language in LANGUAGES},
}
DESCRIPTIONS = {
    "en": "language-independent place depicted on the architecture page",
    "fr": "lieu indépendant de la langue représenté sur la page d’architecture",
    "ml": "വാസ്തുവിദ്യാ താളിൽ ചിത്രീകരിച്ച ഭാഷാ-സ്വതന്ത്ര സ്ഥലം",
    "pa": "ਵਾਸਤੂਕਲਾ ਸਫ਼ੇ ਉੱਤੇ ਦਰਸਾਇਆ ਭਾਸ਼ਾ-ਸੁਤੰਤਰ ਸਥਾਨ",
    "hi": "वास्तुकला पृष्ठ पर चित्रित भाषा-स्वतंत्र स्थान",
    "pt": "lugar independente do idioma representado na página de arquitetura",
    "es": "lugar independiente del idioma representado en la página de arquitectura",
    "it": "luogo indipendente dalla lingua raffigurato nella pagina di architettura",
}


class LocationParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_location = False
        self.locations: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "h4" and values.get("class") == "building-location":
            self.in_location = True
            self.parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "h4" and self.in_location:
            self.locations.append(" ".join("".join(self.parts).split()))
            self.in_location = False

    def handle_data(self, data: str) -> None:
        if self.in_location:
            self.parts.append(data)


def locations(path: Path) -> list[str]:
    parser = LocationParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.locations


def architecture_pages() -> dict[str, Path]:
    return next(group for group in groups() if group["en"].stem == "architecture")


def render_items() -> str:
    pages = architecture_pages()
    localized = {language: locations(path) for language, path in pages.items()}
    expected = len(localized["en"])
    if any(len(values) != expected for values in localized.values()):
        raise ValueError("Architecture galleries do not have aligned location counts")
    indexes = {label: localized["en"].index(label) for label in TARGETS}
    blocks: list[str] = []
    for english_label, parent in TARGETS.items():
        index = indexes[english_label]
        statements = ["CREATE"]
        for language in LANGUAGES:
            label = PROPER_NAME_LABELS.get(english_label, {}).get(
                language,
                localized[language][index],
            )
            statements.append(
                f'LAST|L{language}|"{quickstatements_quote(label)}"'
            )
            statements.append(
                f'LAST|D{language}|'
                f'"{quickstatements_quote(DESCRIPTIONS[language])}"'
            )
        statements.extend(
            (f"LAST|P8|{DEPICTED_PLACE_CLASS}", f"LAST|P21|{parent}")
        )
        blocks.append("\n".join(statements))
    return "\n\n".join(blocks) + "\n"


def main() -> int:
    output = REPO_ROOT / "quickstatements-abstract-depicted-places.txt"
    output.write_text(render_items(), encoding="utf-8")
    print(f"Wrote {len(TARGETS)} depicted-place items to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
