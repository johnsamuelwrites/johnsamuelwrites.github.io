#!/usr/bin/env python3
"""Refresh translated travel pages from the modern English HTML shell.

This script is deliberately file-based: it uses the existing translated travel
pages as the source of translated labels, captions, and page mappings, then
copies the modern English page structure/CSS into selected target languages.
It also rebuilds the travel language selector so Spanish, Italian, and
Portuguese pages link to themselves and to each other.
"""

from __future__ import annotations

import argparse
import html
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from paths import REPO_ROOT


LANGUAGE_NAMES = {
    "en": "English",
    "fr": "Français",
    "ml": "മലയാളം",
    "pa": "ਪੰਜਾਬੀ",
    "hi": "हिन्दी",
    "pt": "Português",
    "es": "Español",
    "it": "Italiano",
}

LANGUAGE_ORDER = ("en", "fr", "ml", "pa", "hi", "pt", "es", "it")

TRAVEL_DIRS = {
    "en": Path("en/photography"),
    "fr": Path("fr/voyages"),
    "ml": Path("ml/യാത്രകൾ"),
    "pa": Path("pa/ਯਾਤਰਾ"),
    "hi": Path("hi/यात्रा"),
    "pt": Path("pt/viagens"),
    "es": Path("es/viajes"),
    "it": Path("it/viaggi"),
}

TRAVEL_INDEX_DIRS = {
    "en": Path("en/travel"),
    "fr": Path("fr/voyages"),
    "ml": Path("ml/യാത്രകൾ"),
    "pa": Path("pa/ਯਾਤਰਾ"),
    "hi": Path("hi/यात्रा"),
    "pt": Path("pt/viagens"),
    "es": Path("es/viajes"),
    "it": Path("it/viaggi"),
}

INDIC_LANGS = ("ml", "pa", "hi")
LATIN_TARGET_LANGS = ("it", "pt", "es")
REFRESH_SELECTOR_LANGS = LANGUAGE_ORDER

SITE_TAGLINES = {
    "ml": "ഛായാഗ്രഹണവും യാത്രകളും",
    "pa": "ਫੋਟੋਗ੍ਰਾਫੀ ਅਤੇ ਯਾਤਰਾ",
    "hi": "छायाचित्र और यात्रा",
}

FOOTER_TITLES = {
    "ml": "ഭാഷ തിരഞ്ഞെടുക്കുക",
    "pa": "ਭਾਸ਼ਾ ਚੁਣੋ",
    "hi": "भाषा चुनें",
}

COUNTRY_PAGE_LABELS = {
    "en": {
        "photography": "Photography",
        "site_tagline": "Photography &amp; Travel",
        "home": "Home",
        "travel": "Travel",
        "hero_subtitle": "Timeless Landscapes • Cultural Rhythms • Artistic Glimpses",
        "footer": "Travel in {country}",
        "credits": "Photography &amp; Travel",
    },
    "fr": {
        "photography": "Photographie",
        "site_tagline": "Photographie et Voyages",
        "home": "Accueil",
        "travel": "Voyages",
        "hero_subtitle": "Paysages intemporels • Rythmes culturels • Regards artistiques",
        "footer": "Voyages en {country}",
        "credits": "Photographie et Voyages",
    },
    "ml": {
        "photography": "ഛായാഗ്രഹണം",
        "site_tagline": "ഛായാഗ്രഹണവും യാത്രകളും",
        "home": "ഹോം",
        "travel": "യാത്രകൾ",
        "hero_subtitle": "കാലാതീതമായ ഭൂപ്രകൃതികൾ • സാംസ്കാരിക താളങ്ങൾ • കലാപരമായ ദൃശ്യങ്ങൾ",
        "footer": "{country} യാത്രകൾ",
        "credits": "ഛായാഗ്രഹണവും യാത്രകളും",
    },
    "pa": {
        "photography": "ਫੋਟੋਗ੍ਰਾਫੀ",
        "site_tagline": "ਫੋਟੋਗ੍ਰਾਫੀ ਅਤੇ ਯਾਤਰਾ",
        "home": "ਘਰ",
        "travel": "ਯਾਤਰਾ",
        "hero_subtitle": "ਸਦੀਵੀ ਦ੍ਰਿਸ਼ • ਸੱਭਿਆਚਾਰਕ ਲਯ • ਕਲਾਤਮਕ ਝਲਕਾਂ",
        "footer": "{country} ਵਿੱਚ ਯਾਤਰਾ",
        "credits": "ਫੋਟੋਗ੍ਰਾਫੀ ਅਤੇ ਯਾਤਰਾ",
    },
    "hi": {
        "photography": "छायाचित्र",
        "site_tagline": "छायाचित्र और यात्रा",
        "home": "मुखपृष्ठ",
        "travel": "यात्रा",
        "hero_subtitle": "कालातीत परिदृश्य • सांस्कृतिक लय • कलात्मक झलकियाँ",
        "footer": "{country} में यात्रा",
        "credits": "छायाचित्र और यात्रा",
    },
    "pt": {
        "photography": "Fotografia",
        "site_tagline": "Fotografia e Viagens",
        "home": "Início",
        "travel": "Viagens",
        "hero_subtitle": "Paisagens intemporais • Ritmos culturais • Olhares artísticos",
        "footer": "Viagens em {country}",
        "credits": "Fotografia e Viagens",
    },
    "es": {
        "photography": "Fotografía",
        "site_tagline": "Fotografía y Viajes",
        "home": "Inicio",
        "travel": "Viajes",
        "hero_subtitle": "Paisajes atemporales • Ritmos culturales • Miradas artísticas",
        "footer": "Viajes en {country}",
        "credits": "Fotografía y Viajes",
    },
    "it": {
        "photography": "Fotografia",
        "site_tagline": "Fotografia e Viaggi",
        "home": "Home",
        "travel": "Viaggi",
        "hero_subtitle": "Paesaggi senza tempo • Ritmi culturali • Sguardi artistici",
        "footer": "Viaggi in {country}",
        "credits": "Fotografia e Viaggi",
    },
}

CITY_PAGE_LABELS = {
    lang: {
        "photography": labels["photography"],
        "site_tagline": labels["site_tagline"],
        "home": labels["home"],
        "travel": labels["travel"],
        "credits": labels["credits"],
        "footer": "{city} - {country}",
    }
    for lang, labels in COUNTRY_PAGE_LABELS.items()
}

FRENCH_CITY_FILENAME_OVERRIDES = {
    ("Greece", "Athens.html"): "fr/voyages/villes/Grèce/Athènes.html",
    ("Greece", "Hersonissos.html"): "fr/voyages/villes/Grèce/Chersónissos.html",
    ("Italy", "Bologna.html"): "fr/voyages/villes/Italie/Bologne.html",
    ("Italy", "Genoa.html"): "fr/voyages/villes/Italie/Gênes.html",
    ("Spain", "Barcelona.html"): "fr/voyages/villes/Espagne/Barcelone.html",
    ("Spain", "Granada.html"): "fr/voyages/villes/Espagne/Grenade.html",
    ("Switzerland", "Geneva.html"): "fr/voyages/villes/Suisse/Genève.html",
}

CITY_NAME_TRANSLATIONS = {
    "Adršpach": {"ml": "അദർശ്പാഖ്", "hi": "अदर्शपाख", "pa": "ਅਦਰਸ਼ਪਾਖ"},
    "Alhambra": {"ml": "അൽഹാംബ്ര", "hi": "अलहाम्ब्रा", "pa": "ਅਲਹਾਮਬਰਾ"},
    "Amsterdam": {"ml": "ആംസ്റ്റർഡാം", "hi": "एम्स्टर्डम", "pa": "ਐਮਸਟਰਡਮ"},
    "Annecy": {"ml": "ആനസി", "hi": "एनेसी", "pa": "ਐਨੇਸੀ"},
    "Antwerp": {"ml": "ആന്റ്വർപ്", "hi": "एंटवर्प", "pa": "ਐਂਟਵਰਪ"},
    "Arles": {"ml": "ആർൽ", "hi": "आर्ल", "pa": "ਆਰਲ"},
    "Athens": {"ml": "ഏഥൻസ്", "hi": "एथेंस", "pa": "ਏਥਨਜ਼"},
    "Aveiro": {"ml": "അവെയ്‌റോ", "hi": "अवेइरो", "pa": "ਅਵੇਇਰੋ"},
    "Barcelona": {"ml": "ബാഴ്സലോണ", "hi": "बार्सिलोना", "pa": "ਬਾਰਸਿਲੋਨਾ"},
    "Berlin": {"ml": "ബർലിൻ", "hi": "बर्लिन", "pa": "ਬਰਲਿਨ"},
    "Bilbao": {"ml": "ബിൽബാവോ", "hi": "बिलबाओ", "pa": "ਬਿਲਬਾਓ"},
    "Bologna": {"ml": "ബൊലോഞ്ഞ", "hi": "बोलोन्या", "pa": "ਬੋਲੋਨਿਆ"},
    "Bordeaux": {"ml": "ബോർഡോ", "hi": "बोर्डो", "pa": "ਬੋਰਡੋ"},
    "Braga": {"ml": "ബ്രാഗ", "hi": "ब्रागा", "pa": "ਬ੍ਰਾਗਾ"},
    "Bratislava": {"ml": "ബ്രാറ്റിസ്ലാവ", "hi": "ब्रातिस्लावा", "pa": "ਬ੍ਰਾਤਿਸਲਾਵਾ"},
    "Brno": {"ml": "ബ്ര്നോ", "hi": "ब्रनो", "pa": "ਬਰਨੋ"},
    "Bruges": {"ml": "ബ്രൂജ്", "hi": "ब्रूज", "pa": "ਬਰੂਜ"},
    "Brussels": {"ml": "ബ്രസ്സൽസ്", "hi": "ब्रसेल्स", "pa": "ਬ੍ਰੱਸਲਜ਼"},
    "Budapest": {"ml": "ബുഡാപെസ്റ്റ്", "hi": "बुडापेस्ट", "pa": "ਬੁਡਾਪੇਸਟ"},
    "Carcassonne": {"ml": "കാർകസോൺ", "hi": "कारकासोन", "pa": "ਕਾਰਕਾਸੋਨ"},
    "Clermont-Ferrand": {"ml": "ക്ലെർമോൺ-ഫെറാൻ", "hi": "क्लेरमों-फेरां", "pa": "ਕਲੇਰਮੋਂ-ਫੇਰਾਂ"},
    "Copenhagen": {"ml": "കോപ്പൻഹേഗൻ", "hi": "कोपेनहेगन", "pa": "ਕੋਪਨਹੇਗਨ"},
    "Delft": {"ml": "ഡെൽഫ്റ്റ്", "hi": "डेल्फ्ट", "pa": "ਡੈਲਫਟ"},
    "Devín": {"ml": "ദെവിൻ", "hi": "देवीन", "pa": "ਦੇਵੀਨ"},
    "Florence": {"ml": "ഫ്ലോറൻസ്", "hi": "फ्लोरेंस", "pa": "ਫਲੋਰੈਂਸ"},
    "Gdansk": {"ml": "ഗ്ദാൻസ്ക്", "hi": "ग्दांस्क", "pa": "ਗਦਾਂਸਕ"},
    "Geneva": {"ml": "ജിനീവ", "hi": "जिनेवा", "pa": "ਜਨੀਵਾ"},
    "Genoa": {"ml": "ജെനോവ", "hi": "जेनोआ", "pa": "ਜੇਨੋਆ"},
    "Ghent": {"ml": "ഘെന്റ്", "hi": "गेंट", "pa": "ਗੈਂਟ"},
    "Granada": {"ml": "ഗ്രനാഡ", "hi": "ग्रानादा", "pa": "ਗ੍ਰਾਨਾਦਾ"},
    "Grenoble": {"ml": "ഗ്രെനോബ്ല്", "hi": "ग्रेनोबल", "pa": "ਗ੍ਰੇਨੋਬਲ"},
    "Guimarães": {"ml": "ഗിമറൈൻസ്", "hi": "गिमाराइश", "pa": "ਗਿਮਾਰਾਇਸ਼"},
    "Helsinki": {"ml": "ഹെൽസിങ്കി", "hi": "हेलसिंकी", "pa": "ਹੇਲਸਿੰਕੀ"},
    "Heraklion": {"ml": "ഹെറാക്ലിയോൺ", "hi": "हेराक्लिओन", "pa": "ਹੇਰਾਕਲਿਓਨ"},
    "Hersonissos": {"ml": "ഹെർസോണിസോസ്", "hi": "हेर्सोनिसोस", "pa": "ਹੇਰਸੋਨਿਸੋਸ"},
    "Issoire": {"ml": "ഇസ്വാർ", "hi": "इस्वार", "pa": "ਇਸਵਾਰ"},
    "Katowice": {"ml": "കാറ്റോവിസ്", "hi": "कातोवित्से", "pa": "ਕਾਤੋਵੀਤਸੇ"},
    "Kinderdijk": {"ml": "കിൻഡർഡൈക്", "hi": "किंडरडाइक", "pa": "ਕਿੰਡਰਡਾਇਕ"},
    "Koper": {"ml": "കോപ്പർ", "hi": "कोपर", "pa": "ਕੋਪਰ"},
    "Lempdes": {"ml": "ലെംപ്‌ദ്", "hi": "लांप्द", "pa": "ਲਾਂਪਦ"},
    "Liège": {"ml": "ലിയേജ്", "hi": "लीएज", "pa": "ਲੀਏਜ"},
    "Ljubljana": {"ml": "ല്യൂബ്ലിയാന", "hi": "ल्युब्लियाना", "pa": "ਲਿਊਬਲਿਆਨਾ"},
    "Lourdes": {"ml": "ലൂർദ്", "hi": "लूर्द", "pa": "ਲੂਰਦ"},
    "Loupian": {"ml": "ലൂപ്പിയാൻ", "hi": "लूपियां", "pa": "ਲੂਪਿਆਂ"},
    "Lugano": {"ml": "ലുഗാനോ", "hi": "लुगानो", "pa": "ਲੁਗਾਨੋ"},
    "Luxembourg City": {"ml": "ലക്സംബർഗ്-സിറ്റി", "hi": "लक्ज़मबर्ग-सिटी", "pa": "ਲਕਜ਼ਮਬਰਗ-ਸਿਟੀ"},
    "Lyon": {"ml": "ലിയോൺ", "hi": "ल्यों", "pa": "ਲਿਓਂ"},
    "Lège-Cap-Ferret": {"ml": "ലേജ്-കാപ്-ഫെറെ", "hi": "लेज-काप-फेरे", "pa": "ਲੇਜ-ਕਾਪ-ਫੇਰੇ"},
    "Marseille": {"ml": "മാർസെയ്", "hi": "मार्सेय", "pa": "ਮਾਰਸੇ"},
    "Martigues": {"ml": "മാർട്ടിഗ്", "hi": "मार्तिग", "pa": "ਮਾਰਤੀਗ"},
    "Moissat": {"ml": "മോയ്സ", "hi": "मोइस्सा", "pa": "ਮੋਇਸਾ"},
    "Mons": {"ml": "മോൺസ്", "hi": "मॉन्स", "pa": "ਮੋਂਸ"},
    "Mont Saint-Michel": {"ml": "മോൺ-സാൻ-മിഷേൽ", "hi": "मों-सां-मिशेल", "pa": "ਮੋਂ-ਸਾਂ-ਮੀਸ਼ੇਲ"},
    "Montpellier": {"ml": "മോംപെലിയേ", "hi": "मोंपेलिये", "pa": "ਮੋਂਪੇਲੀਏ"},
    "Nantes": {"ml": "നാന്ത്", "hi": "नांत", "pa": "ਨਾਂਤ"},
    "Narbonne": {"ml": "നാർബോൺ", "hi": "नारबोन", "pa": "ਨਾਰਬੋਨ"},
    "Nowy Sącz": {"ml": "നോവി-സോഞ്ച്", "hi": "नोवी-सॉन्च", "pa": "ਨੋਵੀ-ਸੋਂਚ"},
    "Padua": {"ml": "പാദുവ", "hi": "पादुआ", "pa": "ਪਾਦੂਆ"},
    "Paris": {"ml": "പാരിസ്", "hi": "पेरिस", "pa": "ਪੈਰਿਸ"},
    "Pisa": {"ml": "പിസ", "hi": "पीसा", "pa": "ਪੀਸਾ"},
    "Porto": {"ml": "പോർട്ടോ", "hi": "पोर्तो", "pa": "ਪੋਰਟੋ"},
    "Prague": {"ml": "പ്രാഗ്", "hi": "प्राग", "pa": "ਪ੍ਰਾਗ"},
    "Pérouges": {"ml": "പേരൂജ്", "hi": "पेरूज", "pa": "ਪੇਰੂਜ"},
    "Rennes": {"ml": "റെന്ന", "hi": "रेन", "pa": "ਰੇਨ"},
    "Riga": {"ml": "റിഗ", "hi": "रीगा", "pa": "ਰੀਗਾ"},
    "Rotterdam": {"ml": "റോട്ടർഡാം", "hi": "रॉटरडैम", "pa": "ਰਾਟਰਡੈਮ"},
    "Saint-Malo": {"ml": "സാൻ-മാലോ", "hi": "सैं-मालो", "pa": "ਸੈਂ-ਮਾਲੋ"},
    "Saint-Nazaire-en-Royans": {"ml": "സാൻ-നസേർ-ആൻ-റോയാൻ", "hi": "सैं-नजेर-आं-रॉयां", "pa": "ਸੈਂ-ਨਜ਼ੇਰ-ਆਂ-ਰੋਯਾਂ"},
    "Stary Sącz": {"ml": "സ്റ്റാരി-സോഞ്ച്", "hi": "स्तारी-सॉन्च", "pa": "ਸਟਾਰੀ-ਸੋਂਚ"},
    "Stockholm": {"ml": "സ്റ്റോക്ക്ഹോം", "hi": "स्टॉकहोम", "pa": "ਸਟਾਕਹੋਮ"},
    "Strasbourg": {"ml": "സ്ട്രാസ്ബൂർഗ്", "hi": "स्ट्रासबुर्ग", "pa": "ਸਟ੍ਰਾਸਬੁਰਗ"},
    "Tallinn": {"ml": "ടാലിൻ", "hi": "ताल्लिन", "pa": "ਟਾਲਿਨ"},
    "The Hague": {"ml": "ഹേഗ്", "hi": "हेग", "pa": "ਹੇਗ"},
    "Tibidabo": {"ml": "തിബിദാബോ", "hi": "तिबिदाबो", "pa": "ਤਿਬਿਦਾਬੋ"},
    "Toulouse": {"ml": "തുലൂസ്", "hi": "तुलूज", "pa": "ਤੁਲੂਜ਼"},
    "Turin": {"ml": "ടൂറിൻ", "hi": "तूरिन", "pa": "ਟੂਰਿਨ"},
    "Vaise": {"ml": "വെയ്‌സ്", "hi": "वेज़", "pa": "ਵੇਜ਼"},
    "Valflaunès": {"ml": "വാൽഫ്ലോനസ്", "hi": "वाल्फ्लोनेस", "pa": "ਵਾਲਫਲੋਨੇਸ"},
    "Vatican City": {"ml": "വത്തിക്കാൻ-സിറ്റി", "hi": "वेटिकन-सिटी", "pa": "ਵੈਟੀਕਨ-ਸਿਟੀ"},
    "Venice": {"ml": "വെനീസ്", "hi": "वेनिस", "pa": "ਵੇਨਿਸ"},
    "Vianden": {"ml": "വിയാൻഡൻ", "hi": "वियांडेन", "pa": "ਵਿਆਂਡਨ"},
    "Vienna": {"ml": "വിയന്ന", "hi": "वियना", "pa": "ਵੀਅਨਾ"},
    "Vilnius": {"ml": "വില്നിയസ്", "hi": "विल्नियस", "pa": "ਵਿਲਨਿਯਸ"},
    "Volvic": {"ml": "വോൾവിക്", "hi": "वोल्विक", "pa": "ਵੋਲਵਿਕ"},
    "Wartburg": {"ml": "വാർട്ട്‌ബർഗ്", "hi": "वार्टबुर्ग", "pa": "ਵਾਰਟਬਰਗ"},
    "Wrocław": {"ml": "വ്രോത്സ്വാവ്", "hi": "व्रॉत्सवाफ", "pa": "ਵ੍ਰੋਤਸਵਾਫ"},
}

HIGHLIGHTS = {
    "ml": "പ്രധാനപ്പെട്ടവ",
    "pa": "ਮੁੱਖ ਝਲਕੀਆਂ",
    "hi": "मुख्य आकर्षण",
}

EN_TRAVEL_PAGES = {"drawings", "index", "miles-to-go", "pilgrimage"}

PAGE_SLUG_TRANSLATIONS = {
    "an-amateur": {
        "fr": "un-amateur",
        "ml": "അമച്വർ-ഫോട്ടോഗ്രാഫർ",
        "pa": "ਇੱਕ-ਸ਼ੁਕੀਨ",
        "hi": "एक-शौकिया-फोटोग्राफर",
        "pt": "um-amador",
        "es": "un-aficionado",
        "it": "un-dilettante",
    },
    "architecture": {
        "fr": "architecture",
        "ml": "വാസ്തുവിദ്യ",
        "pa": "ਵਾਸਤੂਕਲਾ",
        "hi": "वास्तुकला",
        "pt": "arquitetura",
        "es": "arquitectura",
        "it": "architettura",
    },
    "beaches": {
        "fr": "plages",
        "ml": "കടൽത്തീരങ്ങൾ",
        "pa": "ਬੀਚ",
        "hi": "समुद्र-तट",
        "pt": "praias",
        "es": "playas",
        "it": "spiagge",
    },
    "boats": {
        "fr": "bateaux",
        "ml": "വള്ളങ്ങൾ",
        "pa": "ਕਿਸ਼ਤੀਆਂ",
        "hi": "नाव",
        "pt": "barcos",
        "es": "barcos",
        "it": "barche",
    },
    "bridges": {
        "fr": "ponts",
        "ml": "പാലങ്ങൾ",
        "pa": "ਪੁਲ",
        "hi": "पुल",
        "pt": "pontes",
        "es": "puentes",
        "it": "ponti",
    },
    "ceilings": {
        "fr": "toits",
        "ml": "മേൽക്കൂരകൾ",
        "pa": "ਛੱਤ",
        "hi": "छत",
        "pt": "tetos",
        "es": "techos",
        "it": "soffitti",
    },
    "celebrations": {
        "fr": "festivités",
        "ml": "ആഘോഷങ്ങൾ",
        "pa": "ਜਸ਼ਨ",
        "hi": "समारोह",
        "pt": "celebrações",
        "es": "celebraciones",
        "it": "celebrazioni",
    },
    "cities": {
        "fr": "villes",
        "ml": "നഗരങ്ങൾ",
        "pa": "ਸ਼ਹਿਰ",
        "hi": "नगर",
        "pt": "cidades",
        "es": "ciudades",
        "it": "città",
    },
    "countries": {
        "fr": "pays",
        "ml": "രാജ്യങ്ങൾ",
        "pa": "ਦੇਸ਼",
        "hi": "देश",
        "pt": "países",
        "es": "países",
        "it": "paesi",
    },
    "cycles": {
        "fr": "vélos",
        "ml": "സൈക്കിളുകൾ",
        "pa": "ਸਾਈਕਲ",
        "hi": "साइकिलें",
        "pt": "ciclos",
        "es": "ciclos",
        "it": "biciclette",
    },
    "doors": {
        "fr": "portes",
        "ml": "വാതിലുകൾ",
        "pa": "ਦਰਵਾਜ਼ੇ",
        "hi": "दरवाजे",
        "pt": "portas",
        "es": "puertas",
        "it": "porte",
    },
    "drawings": {
        "fr": "dessins",
        "ml": "ചിത്രങ്ങൾ",
        "pa": "ਚਿੱਤਰਕਾਰੀ",
        "hi": "चित्र",
        "pt": "desenhos",
        "es": "dibujos",
        "it": "disegni",
    },
    "flowers": {
        "fr": "fleurs",
        "ml": "പൂക്കൾ",
        "pa": "ਫੁੱਲ",
        "hi": "पुष्प",
        "pt": "flores",
        "es": "flores",
        "it": "fiori",
    },
    "food": {
        "fr": "nourriture",
        "ml": "ആഹാരം",
        "pa": "ਭੋਜਨ",
        "hi": "भोजन",
        "pt": "comida",
        "es": "comida",
        "it": "cibo",
    },
    "fractals": {
        "fr": "fractales",
        "ml": "ഫ്രാക്റ്റലുകൾ",
        "pa": "ਫ੍ਰੈਕਟਲ",
        "hi": "भग्न",
        "pt": "fractais",
        "es": "fractales",
        "it": "frattali",
    },
    "heritage-sites": {
        "fr": "sites-patrimoniaux",
        "ml": "പൈതൃക-സൈറ്റുകൾ",
        "pa": "ਵਿਰਾਸਤੀ-ਸਥਾਨ",
        "hi": "विरासत-स्थल",
        "pt": "sítios-do-património",
        "es": "sitios-del-patrimonio",
        "it": "siti-del-patrimonio",
    },
    "historical-monuments": {
        "fr": "monuments-patrimoniaux",
        "ml": "ചരിത്ര-സ്മാരകങ്ങൾ",
        "pa": "ਵਿਰਾਸਤੀ-ਸਮਾਰਕ",
        "hi": "ऐतिहासिक-स्मारक",
        "pt": "monumentos-históricos",
        "es": "monumentos-históricos",
        "it": "monumenti-storici",
    },
    "index": {"fr": "index", "ml": "index", "pa": "index", "hi": "index", "pt": "index", "es": "index", "it": "index"},
    "installations": {
        "fr": "installations",
        "ml": "ഇൻസ്റ്റലേഷനുകൾ",
        "pa": "ਸਥਾਪਨਾਵਾਂ",
        "hi": "अधिष्ठापन",
        "pt": "instalações",
        "es": "instalaciones",
        "it": "installazioni",
    },
    "lakes": {
        "fr": "lacs",
        "ml": "തടാകങ്ങൾ",
        "pa": "ਝੀਲਾਂ",
        "hi": "झील",
        "pt": "lagos",
        "es": "lagos",
        "it": "laghi",
    },
    "lonely-tree": {
        "fr": "arbre-solitaire",
        "ml": "ഏകാന്ത-വൃക്ഷം",
        "pa": "ਇਕੱਲਾ-ਰੁੱਖ",
        "hi": "एकान्त-वृक्ष",
        "pt": "árvore-solitária",
        "es": "árbol-solitario",
        "it": "albero-solitario",
    },
    "miles-to-go": {
        "fr": "kilomètres-à-parcourir",
        "ml": "മൈലുകൾ-പോകണം",
        "pa": "ਸਫ਼ਰ-ਕਰਨ-ਲਈ-ਕਿਲੋਮੀਟਰ-ਹਨ",
        "hi": "कई-किलोमीटर-की-यात्रा-करनी-है",
        "pt": "milhas-por-percorrer",
        "es": "millas-por-recorrer",
        "it": "miglia-da-percorrere",
    },
    "nature": {
        "fr": "nature",
        "ml": "പ്രകൃതി",
        "pa": "ਕੁਦਰਤ",
        "hi": "प्रकृति",
        "pt": "natureza",
        "es": "naturaleza",
        "it": "natura",
    },
    "nightlife": {
        "fr": "vie-nocturne",
        "ml": "രാത്രി-ജീവിതം",
        "pa": "ਰਾਤ-ਦਾ-ਜੀਵਨ",
        "hi": "रात-का-जीवन",
        "pt": "vida-noturna",
        "es": "vida-nocturna",
        "it": "vita-notturna",
    },
    "pilgrimage": {
        "fr": "pèlerinage",
        "ml": "തീർത്ഥാടനം",
        "pa": "ਤੀਰਥ-ਯਾਤਰਾ",
        "hi": "तीर्थयात्रा",
        "pt": "peregrinação",
        "es": "peregrinación",
        "it": "pellegrinaggio",
    },
    "plants": {
        "fr": "plantes",
        "ml": "സസ്യങ്ങൾ",
        "pa": "ਪੌਦੇ",
        "hi": "पौधे",
        "pt": "plantas",
        "es": "plantas",
        "it": "piante",
    },
    "pride": {
        "fr": "fierté",
        "ml": "അഭിമാനങ്ങൾ",
        "pa": "ਮਾਣ",
        "hi": "अभिमान",
        "pt": "orgulho",
        "es": "orgullo",
        "it": "orgoglio",
    },
    "reflection": {
        "fr": "reflet",
        "ml": "പ്രതിഫലനം",
        "pa": "ਪ੍ਰਤੀਬਿੰਬ",
        "hi": "प्रतिबिंब",
        "pt": "reflexo",
        "es": "reflejo",
        "it": "riflessi",
    },
    "repetition": {
        "fr": "répétition",
        "ml": "ആവർത്തനം",
        "pa": "ਦੁਹਰਾਉਣ",
        "hi": "दुहराव",
        "pt": "repetição",
        "es": "repetición",
        "it": "ripetizione",
    },
    "rivers": {
        "fr": "fleuves",
        "ml": "നദികൾ",
        "pa": "ਨਦੀਆਂ",
        "hi": "नदियाँ",
        "pt": "rios",
        "es": "ríos",
        "it": "fiumi",
    },
    "rocks": {
        "fr": "rochers",
        "ml": "പാറകൾ",
        "pa": "ਚੱਟਾਨਾਂ",
        "hi": "चट्टानें",
        "pt": "rochas",
        "es": "rocas",
        "it": "rocce",
    },
    "seas": {
        "fr": "mers",
        "ml": "കടലുകൾ",
        "pa": "ਸਮੁੰਦਰ",
        "hi": "समुद्र",
        "pt": "mares",
        "es": "mares",
        "it": "mari",
    },
    "software": {
        "fr": "logiciel",
        "ml": "സോഫ്‌റ്റ്‌വെയർ",
        "pa": "ਸਾਫਟਵੇਅਰ",
        "hi": "सॉफ़्टवेयर",
        "pt": "software",
        "es": "software",
        "it": "software",
    },
    "stations": {
        "fr": "stations",
        "ml": "സ്റ്റേഷനുകൾ",
        "pa": "ਸਟੇਸ਼ਨ",
        "hi": "स्टेशन",
        "pt": "estações",
        "es": "estaciones",
        "it": "stazioni",
    },
    "statues": {
        "fr": "statues",
        "ml": "പ്രതിമകൾ",
        "pa": "ਮੂਰਤੀਆਂ",
        "hi": "प्रतिमाएं",
        "pt": "estátuas",
        "es": "estatuas",
        "it": "statue",
    },
    "street-art": {
        "fr": "art-de-rue",
        "ml": "തെരുവ്-കല",
        "pa": "ਗਲੀ-ਕਲਾ",
        "hi": "सड़क-कला",
        "pt": "arte-de-rua",
        "es": "arte-callejero",
        "it": "arte-di-strada",
    },
    "street-lights": {
        "fr": "éclairage-public",
        "ml": "തെരുവ്-വിളക്ക്",
        "pa": "ਗਲੀ-ਰੋਸ਼ਨੀ",
        "hi": "सड़क-की-रोशनी",
        "pt": "candeeiros-de-rua",
        "es": "farolas",
        "it": "lampioni",
    },
    "sunset": {
        "fr": "coucher-du-soleil",
        "ml": "സൂര്യാസ്തമയം",
        "pa": "ਸੂਰਜ-ਡੁੱਬਣ",
        "hi": "सूर्यास्त",
        "pt": "pôr-do-sol",
        "es": "atardecer",
        "it": "tramonto",
    },
    "symmetry": {
        "fr": "symétrie",
        "ml": "സമമിതി",
        "pa": "ਸਮਰੂਪਤਾ",
        "hi": "समरूपता",
        "pt": "simetria",
        "es": "simetría",
        "it": "simmetria",
    },
    "tessellation": {
        "fr": "pavage",
        "ml": "ടെസ്സലേഷൻ",
        "pa": "ਟਾਇਲਾਂ",
        "hi": "चौकोर",
        "pt": "tesselação",
        "es": "teselación",
        "it": "tassellazione",
    },
    "trains": {
        "fr": "trains",
        "ml": "ട്രെയിനുകൾ",
        "pa": "ਰੇਲਗੱਡੀਆਂ",
        "hi": "रेलगाड़ी",
        "pt": "comboios",
        "es": "trenes",
        "it": "treni",
    },
    "trams": {
        "fr": "trams",
        "ml": "ട്രാമുകൾ",
        "pa": "ਟਰਾਮ",
        "hi": "ट्राम",
        "pt": "elétricos",
        "es": "tranvías",
        "it": "tram",
    },
    "trees": {
        "fr": "arbres",
        "ml": "വൃക്ഷങ്ങൾ",
        "pa": "ਰੁੱਖ",
        "hi": "वृक्ष",
        "pt": "árvores",
        "es": "árboles",
        "it": "alberi",
    },
    "villages": {
        "fr": "villages",
        "ml": "ഗ്രാമങ്ങൾ",
        "pa": "ਪਿੰਡਾਂ",
        "hi": "गाँव",
        "pt": "aldeias",
        "es": "pueblos",
        "it": "villaggi",
    },
    "walls": {
        "fr": "murs",
        "ml": "ചുവരുകൾ",
        "pa": "ਕੰਧਾਂ",
        "hi": "दीवारें",
        "pt": "muros",
        "es": "muros",
        "it": "muri",
    },
    "waves": {
        "fr": "vagues",
        "ml": "തിരമാലകൾ",
        "pa": "ਲਹਿਰਾਂ",
        "hi": "लहरें",
        "pt": "ondas",
        "es": "olas",
        "it": "onde",
    },
    "windows": {
        "fr": "fenêtres",
        "ml": "ജനാലകൾ",
        "pa": "ਖਿੜਕੀਆਂ",
        "hi": "खिड़कियाँ",
        "pt": "janelas",
        "es": "ventanas",
        "it": "finestre",
    },
}

COUNTRY_NAME_TRANSLATIONS = {
    "Austria": {"fr": "Autriche", "pt": "Áustria", "es": "Austria", "it": "Austria", "ml": "ഓസ്ട്രിയ", "pa": "ਆਸਟਰੀਆ", "hi": "ऑस्ट्रिया"},
    "Belgium": {"fr": "Belgique", "pt": "Bélgica", "es": "Bélgica", "it": "Belgio", "ml": "ബെൽജിയം", "pa": "ਬੈਲਜੀਅਮ", "hi": "बेल्जियम"},
    "Czech Republic": {"fr": "Tchéquie", "pt": "Chéquia", "es": "Chequia", "it": "Cechia", "ml": "ചെക്കിയ", "pa": "ਚੈਕੀਆ", "hi": "चेकिया"},
    "Denmark": {"fr": "Danemark", "pt": "Dinamarca", "es": "Dinamarca", "it": "Danimarca", "ml": "ഡെൻമാർക്ക്", "pa": "ਡੈਨਮਾਰਕ", "hi": "डेनमार्क"},
    "Estonia": {"fr": "Estonie", "pt": "Estónia", "es": "Estonia", "it": "Estonia", "ml": "എസ്റ്റോണിയ", "pa": "ਐਸਟੋਨੀਆ", "hi": "एस्टोनिया"},
    "Finland": {"fr": "Finlande", "pt": "Finlândia", "es": "Finlandia", "it": "Finlandia", "ml": "ഫിൻലാൻഡ്", "pa": "ਫਿਨਲੈਂਡ", "hi": "फ़िनलैंड"},
    "France": {"fr": "France", "pt": "França", "es": "Francia", "it": "Francia", "ml": "ഫ്രാൻസ്", "pa": "ਫਰਾਂਸ", "hi": "फ्रांस"},
    "Germany": {"fr": "Allemagne", "pt": "Alemanha", "es": "Alemania", "it": "Germania", "ml": "ജർമ്മനി", "pa": "ਜਰਮਨੀ", "hi": "जर्मनी"},
    "Greece": {"fr": "Grèce", "pt": "Grécia", "es": "Grecia", "it": "Grecia", "ml": "ഗ്രീസ്", "pa": "ਯੂਨਾਨ", "hi": "यूनान"},
    "Hungary": {"fr": "Hongrie", "pt": "Hungria", "es": "Hungría", "it": "Ungheria", "ml": "ഹംഗറി", "pa": "ਹੰਗਰੀ", "hi": "हंगरी"},
    "Italy": {"fr": "Italie", "pt": "Itália", "es": "Italia", "it": "Italia", "ml": "ഇറ്റലി", "pa": "ਇਟਲੀ", "hi": "इटली"},
    "Latvia": {"fr": "Lettonie", "pt": "Letónia", "es": "Letonia", "it": "Lettonia", "ml": "ലാത്വിയ", "pa": "ਲਾਤਵੀਆ", "hi": "लातविया"},
    "Lithuania": {"fr": "Lituanie", "pt": "Lituânia", "es": "Lituania", "it": "Lituania", "ml": "ലിത്വാനിയ", "pa": "ਲਿਥੁਆਨੀਆ", "hi": "लिथुआनिया"},
    "Luxembourg": {"fr": "Luxembourg", "pt": "Luxemburgo", "es": "Luxemburgo", "it": "Lussemburgo", "ml": "ലക്സംബർഗ്", "pa": "ਲਕਜ਼ਮਬਰਗ", "hi": "लक्ज़मबर्ग"},
    "Poland": {"fr": "Pologne", "pt": "Polónia", "es": "Polonia", "it": "Polonia", "ml": "പോളണ്ട്", "pa": "ਪੋਲੈਂਡ", "hi": "पोलैंड"},
    "Portugal": {"fr": "Portugal", "pt": "Portugal", "es": "Portugal", "it": "Portogallo", "ml": "പോർച്ചുഗൽ", "pa": "ਪੁਰਤਗਾਲ", "hi": "पुर्तगाल"},
    "Slovakia": {"fr": "Slovaquie", "pt": "Eslováquia", "es": "Eslovaquia", "it": "Slovacchia", "ml": "സ്ലോവാക്യ", "pa": "ਸਲੋਵਾਕੀਆ", "hi": "स्लोवाकिया"},
    "Slovenia": {"fr": "Slovénie", "pt": "Eslovénia", "es": "Eslovenia", "it": "Slovenia", "ml": "സ്ലോവേനിയ", "pa": "ਸਲੋਵੇਨੀਆ", "hi": "स्लोवेनिया"},
    "Spain": {"fr": "Espagne", "pt": "Espanha", "es": "España", "it": "Spagna", "ml": "സ്പെയിൻ", "pa": "ਸਪੇਨ", "hi": "स्पेन"},
    "Sweden": {"fr": "Suède", "pt": "Suécia", "es": "Suecia", "it": "Svezia", "ml": "സ്വീഡൻ", "pa": "ਸਵੀਡਨ", "hi": "स्वीडन"},
    "Switzerland": {"fr": "Suisse", "pt": "Suíça", "es": "Suiza", "it": "Svizzera", "ml": "സ്വിറ്റ്സർലാൻഡ്", "pa": "ਸਵਿਟਜ਼ਰਲੈਂਡ", "hi": "स्विट्ज़रलैंड"},
    "The Netherlands": {"fr": "Pays-Bas", "pt": "Países Baixos", "es": "Países Bajos", "it": "Paesi Bassi", "ml": "നെതർലാൻഡ്സ്", "pa": "ਨੀਦਰਲੈਂਡ", "hi": "नीदरलैंड"},
    "Vatican": {"fr": "Vatican", "pt": "Vaticano", "es": "Vaticano", "it": "Vaticano", "ml": "വത്തിക്കാൻ", "pa": "ਵੈਟੀਕਨ", "hi": "वेटिकन"},
}

PHOTO_CAPTION_TRANSLATIONS = {
    "Abbey": {"fr": "Abbaye", "ml": "ആശ്രമം", "pa": "ਮੱਠ", "hi": "मठ", "pt": "Abadia", "es": "Abadía", "it": "Abbazia"},
    "Alhambra": {"fr": "Alhambra", "ml": "അൽഹാംബ്ര", "pa": "ਅਲਹਾਮਬਰਾ", "hi": "अलहाम्ब्रा", "pt": "Alhambra", "es": "Alhambra", "it": "Alhambra"},
    "Altar": {"fr": "Autel", "ml": "അൾത്താര", "pa": "ਵੇਦੀ", "hi": "वेदी", "pt": "Altar", "es": "Altar", "it": "Altare"},
    "Annecy": {"fr": "Annecy", "ml": "ആനസി", "pa": "ਐਨੇਸੀ", "hi": "एनेसी", "pt": "Annecy", "es": "Annecy", "it": "Annecy"},
    "Arch": {"fr": "Arche", "ml": "കമാനം", "pa": "ਮਿਹਰਾਬ", "hi": "मेहराब", "pt": "Arco", "es": "Arco", "it": "Arco"},
    "Arles": {"fr": "Arles", "ml": "ആർൽ", "pa": "ਆਰਲ", "hi": "आर्ल", "pt": "Arles", "es": "Arlés", "it": "Arles"},
    "Athens": {"fr": "Athènes", "ml": "ഏഥൻസ്", "pa": "ਏਥਨਜ਼", "hi": "एथेंस", "pt": "Atenas", "es": "Atenas", "it": "Atene"},
    "Autumn": {"fr": "Automne", "ml": "ശരത്കാലം", "pa": "ਪਤਝੜ", "hi": "शरद ऋतु", "pt": "Outono", "es": "Otoño", "it": "Autunno"},
    "Autumn leaves": {"fr": "Feuilles d'automne", "ml": "ശരത്കാല ഇലകൾ", "pa": "ਪਤਝੜ ਦੇ ਪੱਤੇ", "hi": "शरद ऋतु के पत्ते", "pt": "Folhas de outono", "es": "Hojas de otoño", "it": "Foglie autunnali"},
    "Balcony": {"fr": "Balcon", "ml": "ബാൽക്കണി", "pa": "ਬਾਲਕੋਨੀ", "hi": "बालकनी", "pt": "Varanda", "es": "Balcón", "it": "Balcone"},
    "Barcelona": {"fr": "Barcelone", "ml": "ബാഴ്സലോണ", "pa": "ਬਾਰਸਿਲੋਨਾ", "hi": "बार्सिलोना", "pt": "Barcelona", "es": "Barcelona", "it": "Barcellona"},
    "Basilica": {"fr": "Basilique", "ml": "ബസിലിക്ക", "pa": "ਬੈਸਿਲਿਕਾ", "hi": "बेसिलिका", "pt": "Basílica", "es": "Basílica", "it": "Basilica"},
    "Beach": {"fr": "Plage", "ml": "കടൽത്തീരം", "pa": "ਬੀਚ", "hi": "समुद्र तट", "pt": "Praia", "es": "Playa", "it": "Spiaggia"},
    "Bell": {"fr": "Cloche", "ml": "മണി", "pa": "ਘੰਟੀ", "hi": "घंटी", "pt": "Sino", "es": "Campana", "it": "Campana"},
    "Bent tree": {"fr": "Arbre courbé", "ml": "വളഞ്ഞ വൃക്ഷം", "pa": "ਝੁਕਿਆ ਰੁੱਖ", "hi": "झुका हुआ पेड़", "pt": "Árvore curvada", "es": "Árbol curvado", "it": "Albero piegato"},
    "Berlin": {"fr": "Berlin", "ml": "ബർലിൻ", "pa": "ਬਰਲਿਨ", "hi": "बर्लिन", "pt": "Berlim", "es": "Berlín", "it": "Berlino"},
    "Bologna": {"fr": "Bologne", "ml": "ബൊലോഞ്ഞ", "pa": "ਬੋਲੋਨਿਆ", "hi": "बोलोन्या", "pt": "Bolonha", "es": "Bolonia", "it": "Bologna"},
    "Bridge": {"fr": "Pont", "ml": "പാലം", "pa": "ਪੁਲ", "hi": "पुल", "pt": "Ponte", "es": "Puente", "it": "Ponte"},
    "Budapest": {"fr": "Budapest", "ml": "ബുഡാപെസ്റ്റ്", "pa": "ਬੁਡਾਪੇਸਟ", "hi": "बुडापेस्ट", "pt": "Budapeste", "es": "Budapest", "it": "Budapest"},
    "Building": {"fr": "Bâtiment", "ml": "കെട്ടിടം", "pa": "ਇਮਾਰਤ", "hi": "इमारत", "pt": "Edifício", "es": "Edificio", "it": "Edificio"},
    "Buildings": {"fr": "Bâtiments", "ml": "കെട്ടിടങ്ങൾ", "pa": "ਇਮਾਰਤਾਂ", "hi": "इमारतें", "pt": "Edifícios", "es": "Edificios", "it": "Edifici"},
    "Castle": {"fr": "Château", "ml": "കോട്ട", "pa": "ਕਿਲ੍ਹਾ", "hi": "किला", "pt": "Castelo", "es": "Castillo", "it": "Castello"},
    "Cathedral": {"fr": "Cathédrale", "ml": "കത്തീഡ്രൽ", "pa": "ਕੈਥੇਡ੍ਰਲ", "hi": "कैथेड्रल", "pt": "Catedral", "es": "Catedral", "it": "Cattedrale"},
    "Ceiling": {"fr": "Plafond", "ml": "മേൽത്തട്ട്", "pa": "ਛੱਤ", "hi": "छत", "pt": "Teto", "es": "Techo", "it": "Soffitto"},
    "Chapel": {"fr": "Chapelle", "ml": "ചാപ്പൽ", "pa": "ਚੈਪਲ", "hi": "चैपल", "pt": "Capela", "es": "Capilla", "it": "Cappella"},
    "Church": {"fr": "Église", "ml": "പള്ളി", "pa": "ਗਿਰਜਾਘਰ", "hi": "गिरजाघर", "pt": "Igreja", "es": "Iglesia", "it": "Chiesa"},
    "Church, Perouges": {"fr": "Église, Pérouges", "ml": "പള്ളി, പേരൂജ്", "pa": "ਗਿਰਜਾਘਰ, ਪੇਰੂਜ", "hi": "गिरजाघर, पेरूज", "pt": "Igreja, Pérouges", "es": "Iglesia, Pérouges", "it": "Chiesa, Pérouges"},
    "Cistern": {"fr": "Citerne", "ml": "ജലസംഭരണി", "pa": "ਜਲ-ਟੈਂਕੀ", "hi": "जलकुंड", "pt": "Cisterna", "es": "Cisterna", "it": "Cisterna"},
    "Cloister": {"fr": "Cloître", "ml": "ക്ലോയിസ്റ്റർ", "pa": "ਕਲੋਇਸਟਰ", "hi": "क्लॉइस्टर", "pt": "Claustro", "es": "Claustro", "it": "Chiostro"},
    "Courtyard": {"fr": "Cour", "ml": "മുറ്റം", "pa": "ਵਿਹੜਾ", "hi": "आँगन", "pt": "Pátio", "es": "Patio", "it": "Cortile"},
    "Door": {"fr": "Porte", "ml": "വാതിൽ", "pa": "ਦਰਵਾਜ਼ਾ", "hi": "दरवाज़ा", "pt": "Porta", "es": "Puerta", "it": "Porta"},
    "Double Rainbow": {"fr": "Double arc-en-ciel", "ml": "ഇരട്ട മഴവില്ല്", "pa": "ਦੋਹਰਾ ਸਤਰੰਗੀ ਪੀਂਘ", "hi": "दोहरा इंद्रधनुष", "pt": "Arco-íris duplo", "es": "Doble arcoíris", "it": "Doppio arcobaleno"},
    "Exterior": {"fr": "Extérieur", "ml": "പുറംഭാഗം", "pa": "ਬਾਹਰੀ ਦ੍ਰਿਸ਼", "hi": "बाहरी दृश्य", "pt": "Exterior", "es": "Exterior", "it": "Esterno"},
    "Facade": {"fr": "Façade", "ml": "മുൻഭാഗം", "pa": "ਅਗਲਾ ਹਿੱਸਾ", "hi": "अग्रभाग", "pt": "Fachada", "es": "Fachada", "it": "Facciata"},
    "Façade": {"fr": "Façade", "ml": "മുൻഭാഗം", "pa": "ਅਗਲਾ ਹਿੱਸਾ", "hi": "अग्रभाग", "pt": "Fachada", "es": "Fachada", "it": "Facciata"},
    "Façade with wood, Pérouges": {"fr": "Façade en bois, Pérouges", "ml": "തടി കൊണ്ടുള്ള മുൻഭാഗം, പേരൂജ്", "pa": "ਲੱਕੜ ਵਾਲਾ ਅਗਲਾ ਹਿੱਸਾ, ਪੇਰੂਜ", "hi": "लकड़ी का अग्रभाग, पेरूज", "pt": "Fachada de madeira, Pérouges", "es": "Fachada de madera, Pérouges", "it": "Facciata in legno, Pérouges"},
    "Florence": {"fr": "Florence", "ml": "ഫ്ലോറൻസ്", "pa": "ਫਲੋਰੈਂਸ", "hi": "फ्लोरेंस", "pt": "Florença", "es": "Florencia", "it": "Firenze"},
    "Flowers": {"fr": "Fleurs", "ml": "പൂക്കൾ", "pa": "ਫੁੱਲ", "hi": "फूल", "pt": "Flores", "es": "Flores", "it": "Fiori"},
    "Fort": {"fr": "Fort", "ml": "കോട്ട", "pa": "ਕਿਲ੍ਹਾ", "hi": "किला", "pt": "Forte", "es": "Fortaleza", "it": "Forte"},
    "Fountain": {"fr": "Fontaine", "ml": "ജലധാര", "pa": "ਫੁਹਾਰਾ", "hi": "फव्वारा", "pt": "Fonte", "es": "Fuente", "it": "Fontana"},
    "Garden": {"fr": "Jardin", "ml": "പൂന്തോട്ടം", "pa": "ਬਾਗ਼", "hi": "बगीचा", "pt": "Jardim", "es": "Jardín", "it": "Giardino"},
    "Garden view, Rue du Prince, Pérouges": {"fr": "Vue du jardin, Rue du Prince, Pérouges", "ml": "പൂന്തോട്ട ദൃശ്യം, റ്യൂ ദ്യൂ പ്രിൻസ്, പേരൂജ്", "pa": "ਬਾਗ਼ ਦਾ ਦ੍ਰਿਸ਼, ਰਯੂ ਦਯੂ ਪ੍ਰਿੰਸ, ਪੇਰੂਜ", "hi": "बगीचे का दृश्य, रयू दयू प्रिंस, पेरूज", "pt": "Vista do jardim, Rue du Prince, Pérouges", "es": "Vista del jardín, Rue du Prince, Pérouges", "it": "Veduta del giardino, Rue du Prince, Pérouges"},
    "Gdansk": {"fr": "Gdansk", "ml": "ഗ്ദാൻസ്ക്", "pa": "ਗਦਾਂਸਕ", "hi": "ग्दांस्क", "pt": "Gdansk", "es": "Gdansk", "it": "Danzica"},
    "Genoa": {"fr": "Gênes", "ml": "ജെനോവ", "pa": "ਜੇਨੋਆ", "hi": "जेनोआ", "pt": "Génova", "es": "Génova", "it": "Genova"},
    "Giuseppe Verdi": {"fr": "Giuseppe Verdi", "ml": "ജ്യൂസെപ്പെ വെർദി", "pa": "ਜੂਜ਼ੈੱਪੇ ਵਰਦੀ", "hi": "ज्यूसेप्पे वर्दी", "pt": "Giuseppe Verdi", "es": "Giuseppe Verdi", "it": "Giuseppe Verdi"},
    "Golden Hour": {"fr": "Heure dorée", "ml": "സുവർണ്ണ നേരം", "pa": "ਸੁਨਹਿਰੀ ਘੜੀ", "hi": "स्वर्णिम बेला", "pt": "Hora dourada", "es": "Hora dorada", "it": "Ora dorata"},
    "Golden hour": {"fr": "Heure dorée", "ml": "സുവർണ്ണ നേരം", "pa": "ਸੁਨਹਿਰੀ ਘੜੀ", "hi": "स्वर्णिम बेला", "pt": "Hora dourada", "es": "Hora dorada", "it": "Ora dorata"},
    "Gondolas": {"fr": "Gondoles", "ml": "ഗൊണ്ടോളകൾ", "pa": "ਗੋਂਡੋਲਾ", "hi": "गोंडोला", "pt": "Gôndolas", "es": "Góndolas", "it": "Gondole"},
    "Heraklion": {"fr": "Héraklion", "ml": "ഹെറാക്ലിയോൺ", "pa": "ਹੇਰਾਕਲਿਓਨ", "hi": "हेराक्लिओन", "pt": "Heraclião", "es": "Heraclión", "it": "Heraklion"},
    "Hotel": {"fr": "Hôtel", "ml": "ഹോട്ടൽ", "pa": "ਹੋਟਲ", "hi": "होटल", "pt": "Hotel", "es": "Hotel", "it": "Hotel"},
    "Interior": {"fr": "Intérieur", "ml": "അകംഭാഗം", "pa": "ਅੰਦਰੂਨੀ ਦ੍ਰਿਸ਼", "hi": "भीतरी दृश्य", "pt": "Interior", "es": "Interior", "it": "Interno"},
    "Issoire": {"fr": "Issoire", "ml": "ഇസ്വാർ", "pa": "ਇਸਵਾਰ", "hi": "इस्वार", "pt": "Issoire", "es": "Issoire", "it": "Issoire"},
    "Lake": {"fr": "Lac", "ml": "തടാകം", "pa": "ਝੀਲ", "hi": "झील", "pt": "Lago", "es": "Lago", "it": "Lago"},
    "Leaves": {"fr": "Feuilles", "ml": "ഇലകൾ", "pa": "ਪੱਤੇ", "hi": "पत्ते", "pt": "Folhas", "es": "Hojas", "it": "Foglie"},
    "Lights": {"fr": "Lumières", "ml": "വിളക്കുകൾ", "pa": "ਰੋਸ਼ਨੀਆਂ", "hi": "रोशनी", "pt": "Luzes", "es": "Luces", "it": "Luci"},
    "Lintel": {"fr": "Linteau", "ml": "കട്ടിളമേൽപ്പടി", "pa": "ਸਰਦਲ", "hi": "सरदल", "pt": "Lintel", "es": "Dintel", "it": "Architrave"},
    "Loupian": {"fr": "Loupian", "ml": "ലൂപ്പിയാൻ", "pa": "ਲੂਪਿਆਂ", "hi": "लूपियां", "pt": "Loupian", "es": "Loupian", "it": "Loupian"},
    "Market Square": {"fr": "Place du marché", "ml": "ചന്തസ്ഥലം", "pa": "ਬਾਜ਼ਾਰ ਚੌਕ", "hi": "बाज़ार चौक", "pt": "Praça do mercado", "es": "Plaza del mercado", "it": "Piazza del mercato"},
    "Market hall": {"fr": "Halle", "ml": "ചന്തമണ്ഡപം", "pa": "ਬਾਜ਼ਾਰ ਹਾਲ", "hi": "बाज़ार हॉल", "pt": "Mercado coberto", "es": "Mercado cubierto", "it": "Mercato coperto"},
    "Marseille": {"fr": "Marseille", "ml": "മാർസെയ്", "pa": "ਮਾਰਸੇ", "hi": "मार्सेय", "pt": "Marselha", "es": "Marsella", "it": "Marsiglia"},
    "Museum": {"fr": "Musée", "ml": "മ്യൂസിയം", "pa": "ਅਜਾਇਬ-ਘਰ", "hi": "संग्रहालय", "pt": "Museu", "es": "Museo", "it": "Museo"},
    "Nature": {"fr": "Nature", "ml": "പ്രകൃതി", "pa": "ਕੁਦਰਤ", "hi": "प्रकृति", "pt": "Natureza", "es": "Naturaleza", "it": "Natura"},
    "Nave": {"fr": "Nef", "ml": "നടുത്തളം", "pa": "ਨੇਵ", "hi": "नेव", "pt": "Nave", "es": "Nave", "it": "Navata"},
    "Nowy Sącz": {"fr": "Nowy Sącz", "ml": "നോവി-സോഞ്ച്", "pa": "ਨੋਵੀ-ਸੋਂਚ", "hi": "नोवी-सॉन्च", "pt": "Nowy Sącz", "es": "Nowy Sącz", "it": "Nowy Sącz"},
    "Palace": {"fr": "Palais", "ml": "കൊട്ടാരം", "pa": "ਮਹਿਲ", "hi": "महल", "pt": "Palácio", "es": "Palacio", "it": "Palazzo"},
    "Panorama": {"fr": "Panorama", "ml": "സമഗ്രദൃശ്യം", "pa": "ਪੈਨੋਰਮਾ", "hi": "विहंगम दृश्य", "pt": "Panorama", "es": "Panorama", "it": "Panorama"},
    "Passage": {"fr": "Passage", "ml": "ഇടനാഴി", "pa": "ਲਾਂਘਾ", "hi": "मार्ग", "pt": "Passagem", "es": "Pasaje", "it": "Passaggio"},
    "Pillars": {"fr": "Piliers", "ml": "തൂണുകൾ", "pa": "ਥੰਮ੍ਹ", "hi": "स्तंभ", "pt": "Pilares", "es": "Pilares", "it": "Pilastri"},
    "Pipe Organ": {"fr": "Orgue", "ml": "പൈപ്പ് ഓർഗൻ", "pa": "ਪਾਈਪ ਆਰਗਨ", "hi": "पाइप ऑर्गन", "pt": "Órgão de tubos", "es": "Órgano de tubos", "it": "Organo a canne"},
    "Pipe organ": {"fr": "Orgue", "ml": "പൈപ്പ് ഓർഗൻ", "pa": "ਪਾਈਪ ਆਰਗਨ", "hi": "पाइप ऑर्गन", "pt": "Órgão de tubos", "es": "Órgano de tubos", "it": "Organo a canne"},
    "Pisa": {"fr": "Pise", "ml": "പിസ", "pa": "ਪੀਸਾ", "hi": "पीसा", "pt": "Pisa", "es": "Pisa", "it": "Pisa"},
    "Portal": {"fr": "Portail", "ml": "കവാടം", "pa": "ਦਵਾਰ", "hi": "प्रवेशद्वार", "pt": "Portal", "es": "Portal", "it": "Portale"},
    "Porte Cailhau": {"fr": "Porte Cailhau", "ml": "പോർട്ട് കായൂ", "pa": "ਪੋਰਟ ਕਾਯੂ", "hi": "पोर्त काइयू", "pt": "Porte Cailhau", "es": "Porte Cailhau", "it": "Porte Cailhau"},
    "Pulpit": {"fr": "Chaire", "ml": "പ്രസംഗപീഠം", "pa": "ਪ੍ਰਚਾਰ-ਮੰਚ", "hi": "उपदेशमंच", "pt": "Púlpito", "es": "Púlpito", "it": "Pulpito"},
    "Pérouges": {"fr": "Pérouges", "ml": "പേരൂജ്", "pa": "ਪੇਰੂਜ", "hi": "पेरूज", "pt": "Pérouges", "es": "Pérouges", "it": "Pérouges"},
    "Reflection": {"fr": "Reflet", "ml": "പ്രതിഫലനം", "pa": "ਪ੍ਰਤੀਬਿੰਬ", "hi": "प्रतिबिंब", "pt": "Reflexo", "es": "Reflejo", "it": "Riflesso"},
    "Saint-Nazaire-en-Royans": {"fr": "Saint-Nazaire-en-Royans", "ml": "സാൻ-നസേർ-ആൻ-റോയാൻ", "pa": "ਸੈਂ-ਨਜ਼ੇਰ-ਆਂ-ਰੋਯਾਂ", "hi": "सैं-नजेर-आं-रॉयां", "pt": "Saint-Nazaire-en-Royans", "es": "Saint-Nazaire-en-Royans", "it": "Saint-Nazaire-en-Royans"},
    "Sanctuary": {"fr": "Sanctuaire", "ml": "വിശുദ്ധസ്ഥലം", "pa": "ਪਵਿੱਤਰ-ਅਸਥਾਨ", "hi": "गर्भगृह", "pt": "Santuário", "es": "Santuario", "it": "Santuario"},
    "Sculpture": {"fr": "Sculpture", "ml": "ശില്പം", "pa": "ਮੂਰਤੀ", "hi": "मूर्तिकला", "pt": "Escultura", "es": "Escultura", "it": "Scultura"},
    "Sky": {"fr": "Ciel", "ml": "ആകാശം", "pa": "ਅਸਮਾਨ", "hi": "आकाश", "pt": "Céu", "es": "Cielo", "it": "Cielo"},
    "Skyscrapers": {"fr": "Gratte-ciel", "ml": "അംബരചുംബികൾ", "pa": "ਅਸਮਾਨ-ਛੂਹ ਇਮਾਰਤਾਂ", "hi": "गगनचुंबी इमारतें", "pt": "Arranha-céus", "es": "Rascacielos", "it": "Grattacieli"},
    "Snow": {"fr": "Neige", "ml": "മഞ്ഞ്", "pa": "ਬਰਫ਼", "hi": "बर्फ़", "pt": "Neve", "es": "Nieve", "it": "Neve"},
    "Square": {"fr": "Place", "ml": "ചത്വരം", "pa": "ਚੌਕ", "hi": "चौक", "pt": "Praça", "es": "Plaza", "it": "Piazza"},
    "Station": {"fr": "Gare", "ml": "സ്റ്റേഷൻ", "pa": "ਸਟੇਸ਼ਨ", "hi": "स्टेशन", "pt": "Estação", "es": "Estación", "it": "Stazione"},
    "Statue": {"fr": "Statue", "ml": "പ്രതിമ", "pa": "ਮੂਰਤੀ", "hi": "प्रतिमा", "pt": "Estátua", "es": "Estatua", "it": "Statua"},
    "Stockholm": {"fr": "Stockholm", "ml": "സ്റ്റോക്ക്ഹോം", "pa": "ਸਟਾਕਹੋਮ", "hi": "स्टॉकहोम", "pt": "Estocolmo", "es": "Estocolmo", "it": "Stoccolma"},
    "Street light": {"fr": "Lampadaire", "ml": "തെരുവുവിളക്ക്", "pa": "ਗਲੀ ਦੀ ਰੋਸ਼ਨੀ", "hi": "सड़क की बत्ती", "pt": "Candeeiro de rua", "es": "Farola", "it": "Lampione"},
    "Sunrise": {"fr": "Lever du soleil", "ml": "സൂര്യോദയം", "pa": "ਸੂਰਜ ਚੜ੍ਹਨਾ", "hi": "सूर्योदय", "pt": "Nascer do sol", "es": "Amanecer", "it": "Alba"},
    "Sunset": {"fr": "Coucher du soleil", "ml": "സൂര്യാസ്തമയം", "pa": "ਸੂਰਜ ਡੁੱਬਣਾ", "hi": "सूर्यास्त", "pt": "Pôr do sol", "es": "Atardecer", "it": "Tramonto"},
    "Theater": {"fr": "Théâtre", "ml": "നാടകശാല", "pa": "ਥੀਏਟਰ", "hi": "रंगमंच", "pt": "Teatro", "es": "Teatro", "it": "Teatro"},
    "Toulouse": {"fr": "Toulouse", "ml": "തുലൂസ്", "pa": "ਤੁਲੂਜ਼", "hi": "तुलूज", "pt": "Toulouse", "es": "Tolosa", "it": "Tolosa"},
    "Trees": {"fr": "Arbres", "ml": "വൃക്ഷങ്ങൾ", "pa": "ਰੁੱਖ", "hi": "वृक्ष", "pt": "Árvores", "es": "Árboles", "it": "Alberi"},
    "Turin": {"fr": "Turin", "ml": "ടൂറിൻ", "pa": "ਟੂਰਿਨ", "hi": "तूरिन", "pt": "Turim", "es": "Turín", "it": "Torino"},
    "Twilight": {"fr": "Crépuscule", "ml": "സന്ധ്യ", "pa": "ਸ਼ਾਮ ਦਾ ਘੁਸਮੁਸਾ", "hi": "गोधूलि", "pt": "Crepúsculo", "es": "Crepúsculo", "it": "Crepuscolo"},
    "Vaise": {"fr": "Vaise", "ml": "വെയ്‌സ്", "pa": "ਵੇਜ਼", "hi": "वेज़", "pt": "Vaise", "es": "Vaise", "it": "Vaise"},
    "Volvic": {"fr": "Volvic", "ml": "വോൾവിക്", "pa": "ਵੋਲਵਿਕ", "hi": "वोल्विक", "pt": "Volvic", "es": "Volvic", "it": "Volvic"},
    "Wartburg": {"fr": "Wartburg", "ml": "വാർട്ട്‌ബർഗ്", "pa": "ਵਾਰਟਬਰਗ", "hi": "वार्टबुर्ग", "pt": "Wartburg", "es": "Wartburg", "it": "Wartburg"},
    "Windows, Pérouges": {"fr": "Fenêtres, Pérouges", "ml": "ജനാലകൾ, പേരൂജ്", "pa": "ਖਿੜਕੀਆਂ, ਪੇਰੂਜ", "hi": "खिड़कियाँ, पेरूज", "pt": "Janelas, Pérouges", "es": "Ventanas, Pérouges", "it": "Finestre, Pérouges"},
    "Wrocław": {"fr": "Wrocław", "ml": "വ്രോത്സ്വാവ്", "pa": "ਵ੍ਰੋਤਸਵਾਫ", "hi": "व्रॉत्सवाफ", "pt": "Wrocław", "es": "Wrocław", "it": "Breslavia"},
    "Ceiling, Église Sainte-Marie-Madeleine de Pérouges": {"fr": "Plafond, Église Sainte-Marie-Madeleine de Pérouges", "ml": "സാന്ത്-മാരി-മദ്‌ലെൻ ദെ പേരൂജ് പള്ളിയുടെ മേൽത്തട്ട്", "pa": "ਸੈਂਤ-ਮਾਰੀ-ਮਾਦਲੇਨ ਦੇ ਪੇਰੂਜ ਗਿਰਜਾਘਰ ਦੀ ਛੱਤ", "hi": "सैंत-मारी-मादलेन दे पेरूज गिरजाघर की छत", "pt": "Teto, Igreja de Sainte-Marie-Madeleine de Pérouges", "es": "Techo, Iglesia de Sainte-Marie-Madeleine de Pérouges", "it": "Soffitto, Chiesa di Sainte-Marie-Madeleine a Pérouges"},
    "Mural": {"fr": "Fresque murale", "ml": "ചുവർചിത്രം", "pa": "ਕੰਧ-ਚਿੱਤਰ", "hi": "भित्ति चित्र", "pt": "Mural", "es": "Mural", "it": "Murale"},
    "Stained-glass": {"fr": "Vitrail", "ml": "സ്റ്റെയിൻഡ് ഗ്ലാസ്", "pa": "ਰੰਗਦਾਰ ਕੱਚ", "hi": "रंगीन काँच", "pt": "Vitral", "es": "Vidriera", "it": "Vetrata"},
}

PHOTO_ALT_TRANSLATIONS = {
    "33 Mariacka Street in Katowice": {"fr": "33 rue Mariacka à Katowice", "ml": "കാറ്റോവിസിലെ 33 മാരിയാക്ക തെരുവ്", "pa": "ਕਾਤੋਵੀਤਸੇ ਵਿੱਚ 33 ਮਾਰੀਆਕਾ ਗਲੀ", "hi": "कातोवित्से में 33 मारियाका स्ट्रीट", "pt": "Rua Mariacka 33 em Katowice", "es": "Calle Mariacka 33 en Katowice", "it": "Via Mariacka 33 a Katowice"},
    "7 Mariacka Street in Katowice": {"fr": "7 rue Mariacka à Katowice", "ml": "കാറ്റോവിസിലെ 7 മാരിയാക്ക തെരുവ്", "pa": "ਕਾਤੋਵੀਤਸੇ ਵਿੱਚ 7 ਮਾਰੀਆਕਾ ਗਲੀ", "hi": "कातोवित्से में 7 मारियाका स्ट्रीट", "pt": "Rua Mariacka 7 em Katowice", "es": "Calle Mariacka 7 en Katowice", "it": "Via Mariacka 7 a Katowice"},
    "Agios Minas Cathedral Heraklion": {"fr": "Cathédrale Agios Minas, Héraklion", "ml": "ഏജിയോസ് മിനാസ് കത്തീഡ്രൽ, ഹെറാക്ലിയോൺ", "pa": "ਏਜੀਓਸ ਮੀਨਾਸ ਕੈਥੇਡ੍ਰਲ, ਹੇਰਾਕਲਿਓਨ", "hi": "एजियोस मिनास कैथेड्रल, हेराक्लिओन", "pt": "Catedral de Agios Minas, Heraclião", "es": "Catedral de Agios Minas, Heraclión", "it": "Cattedrale di Agios Minas, Heraklion"},
    "Alhambra Granada": {"fr": "Alhambra, Grenade", "ml": "അൽഹാംബ്ര, ഗ്രനാഡ", "pa": "ਅਲਹਾਮਬਰਾ, ਗ੍ਰਾਨਾਦਾ", "hi": "अलहाम्ब्रा, ग्रानादा", "pt": "Alhambra, Granada", "es": "Alhambra, Granada", "it": "Alhambra, Granada"},
    "Alhambra Palace Granada": {"fr": "Palais de l'Alhambra, Grenade", "ml": "അൽഹാംബ്ര കൊട്ടാരം, ഗ്രനാഡ", "pa": "ਅਲਹਾਮਬਰਾ ਮਹਿਲ, ਗ੍ਰਾਨਾਦਾ", "hi": "अलहाम्ब्रा महल, ग्रानादा", "pt": "Palácio de Alhambra, Granada", "es": "Palacio de la Alhambra, Granada", "it": "Palazzo dell'Alhambra, Granada"},
    "Alhambra, Generalife and Albayzín, Granada": {"fr": "Alhambra, Generalife et Albaicín, Grenade", "ml": "അൽഹാംബ്ര, ജനറലിഫെ, അൽബായ്സിൻ, ഗ്രനാഡ", "pa": "ਅਲਹਾਮਬਰਾ, ਜਨਰਾਲੀਫੇ ਅਤੇ ਅਲਬਾਇਸੀਨ, ਗ੍ਰਾਨਾਦਾ", "hi": "अलहाम्ब्रा, जेनेरालिफ़े और अल्बाइसिन, ग्रानादा", "pt": "Alhambra, Generalife e Albaicín, Granada", "es": "Alhambra, Generalife y Albaicín, Granada", "it": "Alhambra, Generalife e Albayzín, Granada"},
    "Altar, Collégiale Saint-André (Grenoble)": {"fr": "Autel, Collégiale Saint-André (Grenoble)", "ml": "അൾത്താര, സാൻ-ആന്ദ്രേ കൊളീജിയറ്റ് (ഗ്രെനോബ്ല്)", "pa": "ਵੇਦੀ, ਸੈਂ-ਆਂਦ੍ਰੇ ਕਾਲਜੀਏਟ (ਗ੍ਰੇਨੋਬਲ)", "hi": "वेदी, सैं-आंद्रे कॉलेजिएट (ग्रेनोबल)", "pt": "Altar, Colegiada de Saint-André (Grenoble)", "es": "Altar, Colegiata de Saint-André (Grenoble)", "it": "Altare, Collegiata di Saint-André (Grenoble)"},
    "Altar, Templo Expiatorio del Sagrado Corazón.jpg": {"fr": "Autel, Templo Expiatorio del Sagrado Corazón", "ml": "അൾത്താര, ടെംപ്ലോ എക്സ്പിയറ്റോറിയോ ഡെൽ സഗ്രാഡോ കൊറാസോൺ", "pa": "ਵੇਦੀ, ਟੈਂਪਲੋ ਐਕਸਪੀਆਤੋਰੀਓ ਡੇਲ ਸਾਗ੍ਰਾਡੋ ਕੋਰਾਸੋਨ", "hi": "वेदी, तेम्प्लो एक्सपियातोरियो देल साग्रादो कोराज़ोन", "pt": "Altar, Templo Expiatório do Sagrado Coração", "es": "Altar, Templo Expiatorio del Sagrado Corazón", "it": "Altare, Templo Expiatorio del Sagrado Corazón"},
    "Ancienne pharmacie du Cerf, Strasbourg": {"fr": "Ancienne pharmacie du Cerf, Strasbourg", "ml": "പുരാതന ഫാർമസി ദ്യൂ സെർഫ്, സ്ട്രാസ്ബൂർഗ്", "pa": "ਪੁਰਾਣੀ ਫਾਰਮੇਸੀ ਦਯੂ ਸੈਰਫ, ਸਟ੍ਰਾਸਬੁਰਗ", "hi": "पुरानी फार्मेसी दयू सेरफ़, स्ट्रासबुर्ग", "pt": "Antiga farmácia du Cerf, Estrasburgo", "es": "Antigua farmacia du Cerf, Estrasburgo", "it": "Antica farmacia du Cerf, Strasburgo"},
    "Annecy Saint-François-de-Sales (high altar)": {"fr": "Annecy Saint-François-de-Sales (maître-autel)", "ml": "ആനസി സാൻ-ഫ്രാൻസ്വ-ദെ-സാൽ (പ്രധാന അൾത്താര)", "pa": "ਐਨੇਸੀ ਸੈਂ-ਫ੍ਰਾਂਸਵਾ-ਦੇ-ਸਾਲ (ਮੁੱਖ ਵੇਦੀ)", "hi": "एनेसी सैं-फ्रांस्वा-दे-साल (मुख्य वेदी)", "pt": "Annecy Saint-François-de-Sales (altar-mor)", "es": "Annecy Saint-François-de-Sales (altar mayor)", "it": "Annecy Saint-François-de-Sales (altare maggiore)"},
    "Aqueduc de Saint-Nazaire-en-Royans": {"fr": "Aqueduc de Saint-Nazaire-en-Royans", "ml": "സാൻ-നസേർ-ആൻ-റോയാനിലെ ജലസേതു", "pa": "ਸੈਂ-ਨਜ਼ੇਰ-ਆਂ-ਰੋਯਾਂ ਦਾ ਜਲ-ਨਾਲਾ", "hi": "सैं-नजेर-आं-रॉयां का जलसेतु", "pt": "Aqueduto de Saint-Nazaire-en-Royans", "es": "Acueducto de Saint-Nazaire-en-Royans", "it": "Acquedotto di Saint-Nazaire-en-Royans"},
    "Arch in Turin": {"fr": "Arche à Turin", "ml": "ടൂറിനിലെ കമാനം", "pa": "ਟੂਰਿਨ ਵਿੱਚ ਮਿਹਰਾਬ", "hi": "तूरिन में मेहराब", "pt": "Arco em Turim", "es": "Arco en Turín", "it": "Arco a Torino"},
    "Arch of Saint-Trophime Cathedral": {"fr": "Arche de la cathédrale Saint-Trophime", "ml": "സാൻ-ട്രോഫീം കത്തീഡ്രലിന്റെ കമാനം", "pa": "ਸੈਂ-ਟ੍ਰੋਫੀਮ ਕੈਥੇਡ੍ਰਲ ਦਾ ਮਿਹਰਾਬ", "hi": "सैं-त्रोफीम कैथेड्रल का मेहराब", "pt": "Arco da Catedral de Saint-Trophime", "es": "Arco de la Catedral de Saint-Trophime", "it": "Arco della Cattedrale di Saint-Trophime"},
    "Arches in Turin": {"fr": "Arches à Turin", "ml": "ടൂറിനിലെ കമാനങ്ങൾ", "pa": "ਟੂਰਿਨ ਵਿੱਚ ਮਿਹਰਾਬਾਂ", "hi": "तूरिन में मेहराबें", "pt": "Arcos em Turim", "es": "Arcos en Turín", "it": "Archi a Torino"},
    "Autumn leaves in Mons": {"fr": "Feuilles d'automne à Mons", "ml": "മോൺസിലെ ശരത്കാല ഇലകൾ", "pa": "ਮੋਂਸ ਵਿੱਚ ਪਤਝੜ ਦੇ ਪੱਤੇ", "hi": "मॉन्स में शरद ऋतु के पत्ते", "pt": "Folhas de outono em Mons", "es": "Hojas de otoño en Mons", "it": "Foglie autunnali a Mons"},
    "Baptistry San Giovanni Pisa": {"fr": "Baptistère San Giovanni, Pise", "ml": "സാൻ ജൊവാന്നി സ്നാനഗൃഹം, പിസ", "pa": "ਸਾਨ ਜੋਵਾਨੀ ਬੈਪਟਿਸਟ੍ਰੀ, ਪੀਸਾ", "hi": "सान जोवान्नी बपतिस्मा-गृह, पीसा", "pt": "Batistério de San Giovanni, Pisa", "es": "Baptisterio de San Giovanni, Pisa", "it": "Battistero di San Giovanni, Pisa"},
    "Basilica of San Juan de Dios, Granada": {"fr": "Basilique de San Juan de Dios, Grenade", "ml": "സാൻ ഹ്വാൻ ദെ ദിയോസ് ബസിലിക്ക, ഗ്രനാഡ", "pa": "ਸਾਨ ਖੁਆਨ ਦੇ ਦਿਓਸ ਬੈਸਿਲਿਕਾ, ਗ੍ਰਾਨਾਦਾ", "hi": "सान खुआन दे दिओस बेसिलिका, ग्रानादा", "pt": "Basílica de San Juan de Dios, Granada", "es": "Basílica de San Juan de Dios, Granada", "it": "Basilica di San Juan de Dios, Granada"},
    "Basilique Saint-Paul de Narbonne": {"fr": "Basilique Saint-Paul de Narbonne", "ml": "നാർബോണിലെ സാൻ-പോൾ ബസിലിക്ക", "pa": "ਨਾਰਬੋਨ ਦੀ ਸੈਂ-ਪੋਲ ਬੈਸਿਲਿਕਾ", "hi": "नारबोन की सैं-पॉल बेसिलिका", "pt": "Basílica de Saint-Paul de Narbonne", "es": "Basílica de Saint-Paul de Narbona", "it": "Basilica di Saint-Paul a Narbonne"},
    "Bent tree near Mont Saint-Michel": {"fr": "Arbre courbé près du Mont Saint-Michel", "ml": "മോൺ-സാൻ-മിഷേലിന് സമീപമുള്ള വളഞ്ഞ വൃക്ഷം", "pa": "ਮੋਂ-ਸਾਂ-ਮੀਸ਼ੇਲ ਨੇੜੇ ਝੁਕਿਆ ਰੁੱਖ", "hi": "मों-सां-मिशेल के पास झुका हुआ पेड़", "pt": "Árvore curvada perto do Monte Saint-Michel", "es": "Árbol curvado cerca del Monte Saint-Michel", "it": "Albero piegato vicino a Mont Saint-Michel"},
    "Berlin Cathedral": {"fr": "Cathédrale de Berlin", "ml": "ബർലിൻ കത്തീഡ്രൽ", "pa": "ਬਰਲਿਨ ਕੈਥੇਡ੍ਰਲ", "hi": "बर्लिन कैथेड्रल", "pt": "Catedral de Berlim", "es": "Catedral de Berlín", "it": "Duomo di Berlino"},
    "Bourse Maritime (Bordeaux)": {"fr": "Bourse Maritime (Bordeaux)", "ml": "ബോഴ്സ് മാരിതീം (ബോർഡോ)", "pa": "ਬੂਰਸ ਮੈਰੀਤੀਮ (ਬੋਰਡੋ)", "hi": "बूर्स मैरितीम (बोर्डो)", "pt": "Bolsa Marítima (Bordéus)", "es": "Bolsa Marítima (Burdeos)", "it": "Borsa Marittima (Bordeaux)"},
    "Bridge connecting two cities, Narbonne": {"fr": "Pont reliant deux villes, Narbonne", "ml": "രണ്ട് നഗരങ്ങളെ ബന്ധിപ്പിക്കുന്ന പാലം, നാർബോൺ", "pa": "ਦੋ ਸ਼ਹਿਰਾਂ ਨੂੰ ਜੋੜਨ ਵਾਲਾ ਪੁਲ, ਨਾਰਬੋਨ", "hi": "दो शहरों को जोड़ने वाला पुल, नारबोन", "pt": "Ponte que liga duas cidades, Narbonne", "es": "Puente que conecta dos ciudades, Narbona", "it": "Ponte che collega due città, Narbonne"},
    "Bridge, Prato della Valle, Padua": {"fr": "Pont, Prato della Valle, Padoue", "ml": "പാലം, പ്രാറ്റോ ഡെല്ലാ വാല്ലെ, പാദുവ", "pa": "ਪੁਲ, ਪ੍ਰਾਤੋ ਡੇੱਲਾ ਵਾੱਲੇ, ਪਾਦੂਆ", "hi": "पुल, प्रातो देल्ला वाल्ले, पादुआ", "pt": "Ponte, Prato della Valle, Pádua", "es": "Puente, Prato della Valle, Padua", "it": "Ponte, Prato della Valle, Padova"},
    "Building in Genoa": {"fr": "Bâtiment à Gênes", "ml": "ജെനോവയിലെ കെട്ടിടം", "pa": "ਜੇਨੋਆ ਵਿੱਚ ਇਮਾਰਤ", "hi": "जेनोआ में इमारत", "pt": "Edifício em Génova", "es": "Edificio en Génova", "it": "Edificio a Genova"},
    "Byzantine Icon Athens": {"fr": "Icône byzantine, Athènes", "ml": "ബൈസന്റൈൻ ഐക്കൺ, ഏഥൻസ്", "pa": "ਬਾਈਜ਼ੈਂਟਾਈਨ ਆਈਕਨ, ਏਥਨਜ਼", "hi": "बीज़ान्टिन आइकन, एथेंस", "pt": "Ícone bizantino, Atenas", "es": "Icono bizantino, Atenas", "it": "Icona bizantina, Atene"},
    "Cathédrale Sainte-Marie-Majeure": {"fr": "Cathédrale Sainte-Marie-Majeure", "ml": "സാന്ത്-മാരി-മജേർ കത്തീഡ്രൽ", "pa": "ਸੈਂਤ-ਮਾਰੀ-ਮਾਜੇਰ ਕੈਥੇਡ੍ਰਲ", "hi": "सैंत-मारी-मजेर कैथेड्रल", "pt": "Catedral de Sainte-Marie-Majeure", "es": "Catedral de Sainte-Marie-Majeure", "it": "Cattedrale di Sainte-Marie-Majeure"},
    "Ceiling of the Cathedral of Granada": {"fr": "Plafond de la cathédrale de Grenade", "ml": "ഗ്രനാഡ കത്തീഡ്രലിന്റെ മേൽത്തട്ട്", "pa": "ਗ੍ਰਾਨਾਦਾ ਦੇ ਕੈਥੇਡ੍ਰਲ ਦੀ ਛੱਤ", "hi": "ग्रानादा के कैथेड्रल की छत", "pt": "Teto da Catedral de Granada", "es": "Techo de la Catedral de Granada", "it": "Soffitto della Cattedrale di Granada"},
    "Chairs Stockholm": {"fr": "Chaises, Stockholm", "ml": "കസേരകൾ, സ്റ്റോക്ക്ഹോം", "pa": "ਕੁਰਸੀਆਂ, ਸਟਾਕਹੋਮ", "hi": "कुर्सियाँ, स्टॉकहोम", "pt": "Cadeiras, Estocolmo", "es": "Sillas, Estocolmo", "it": "Sedie, Stoccolma"},
    "Chapel of St. George Sarandaris, Chersonissos": {"fr": "Chapelle Saint-Georges Sarandaris, Chersónissos", "ml": "സെന്റ് ജോർജ് സരന്ദാരിസ് ചാപ്പൽ, ഹെർസോണിസോസ്", "pa": "ਸੇਂਟ ਜਾਰਜ ਸਰੰਦਾਰਿਸ ਚੈਪਲ, ਹੇਰਸੋਨਿਸੋਸ", "hi": "सेंट जॉर्ज सरंदारिस चैपल, हेर्सोनिसोस", "pt": "Capela de São Jorge Sarandaris, Chersonissos", "es": "Capilla de San Jorge Sarandaris, Hersonissos", "it": "Cappella di San Giorgio Sarandaris, Chersonissos"},
    "Chapelle Saint-Aaron": {"fr": "Chapelle Saint-Aaron", "ml": "സാൻ-ആരോൺ ചാപ്പൽ", "pa": "ਸੈਂ-ਆਰੋਂ ਚੈਪਲ", "hi": "सैं-आरों चैपल", "pt": "Capela de Saint-Aaron", "es": "Capilla de Saint-Aaron", "it": "Cappella di Saint-Aaron"},
    "Christmas lights in Nantes": {"fr": "Illuminations de Noël à Nantes", "ml": "നാന്തിലെ ക്രിസ്മസ് വിളക്കുകൾ", "pa": "ਨਾਂਤ ਵਿੱਚ ਕ੍ਰਿਸਮਸ ਦੀਆਂ ਰੋਸ਼ਨੀਆਂ", "hi": "नांत में क्रिसमस की रोशनी", "pt": "Luzes de Natal em Nantes", "es": "Luces navideñas en Nantes", "it": "Luci di Natale a Nantes"},
    "Church Stary Sącz": {"fr": "Église, Stary Sącz", "ml": "പള്ളി, സ്റ്റാരി-സോഞ്ച്", "pa": "ਗਿਰਜਾਘਰ, ਸਟਾਰੀ-ਸੋਂਚ", "hi": "गिरजाघर, स्तारी-सॉन्च", "pt": "Igreja, Stary Sącz", "es": "Iglesia, Stary Sącz", "it": "Chiesa, Stary Sącz"},
    "Church in Stary Sącz": {"fr": "Église à Stary Sącz", "ml": "സ്റ്റാരി-സോഞ്ചിലെ പള്ളി", "pa": "ਸਟਾਰੀ-ਸੋਂਚ ਵਿੱਚ ਗਿਰਜਾਘਰ", "hi": "स्तारी-सॉन्च में गिरजाघर", "pt": "Igreja em Stary Sącz", "es": "Iglesia en Stary Sącz", "it": "Chiesa a Stary Sącz"},
    "Church of Megali Panagia Athens": {"fr": "Église de Megali Panagia, Athènes", "ml": "മേഗാലി പനാഗിയ പള്ളി, ഏഥൻസ്", "pa": "ਮੇਗਾਲੀ ਪਨਾਗੀਆ ਚਰਚ, ਏਥਨਜ਼", "hi": "मेगाली पनागिया चर्च, एथेंस", "pt": "Igreja de Megali Panagia, Atenas", "es": "Iglesia de Megali Panagia, Atenas", "it": "Chiesa di Megali Panagia, Atene"},
    "Church, Perouges": {"fr": "Église, Pérouges", "ml": "പള്ളി, പേരൂജ്", "pa": "ਗਿਰਜਾਘਰ, ਪੇਰੂਜ", "hi": "गिरजाघर, पेरूज", "pt": "Igreja, Pérouges", "es": "Iglesia, Pérouges", "it": "Chiesa, Pérouges"},
    "Château d'eau du Peyrou (Montpellier)": {"fr": "Château d'eau du Peyrou (Montpellier)", "ml": "ജലഗോപുരം ദ്യൂ പെയ്റൂ (മോംപെലിയേ)", "pa": "ਜਲ-ਮੀਨਾਰ ਦਯੂ ਪੇਰੂ (ਮੋਂਪੇਲੀਏ)", "hi": "जल मीनार दयू पेरू (मोंपेलिये)", "pt": "Torre de água du Peyrou (Montpellier)", "es": "Depósito de agua du Peyrou (Montpellier)", "it": "Torre dell'acqua du Peyrou (Montpellier)"},
    "Château de Tournoël View": {"fr": "Vue du Château de Tournoël", "ml": "ഷാറ്റോ ദെ ടൂർനോലിന്റെ ദൃശ്യം", "pa": "ਸ਼ਾਤੋ ਦੇ ਤੂਰਨੋਲ ਦਾ ਦ੍ਰਿਸ਼", "hi": "शातो दे तूरनोल का दृश्य", "pt": "Vista do Château de Tournoël", "es": "Vista del Château de Tournoël", "it": "Veduta del Château de Tournoël"},
    "Château des ducs de Bretagne (Nantes)": {"fr": "Château des ducs de Bretagne (Nantes)", "ml": "ഷാറ്റോ ദേ ദ്യൂക് ദെ ബ്രെത്താഞ് (നാന്ത്)", "pa": "ਸ਼ਾਤੋ ਦੇ ਦਯੂਕ ਦੇ ਬ੍ਰੇਤਾਞ (ਨਾਂਤ)", "hi": "शातो दे दयूक दे ब्रेताञ (नांत)", "pt": "Castelo dos Duques da Bretanha (Nantes)", "es": "Castillo de los Duques de Bretaña (Nantes)", "it": "Castello dei Duchi di Bretagna (Nantes)"},
    "Cour Saint Eutrope": {"fr": "Cour Saint Eutrope", "ml": "കൂർ സാൻ യൂട്രോപ്പ്", "pa": "ਕੂਰ ਸੈਂ ਯੂਟ੍ਰੋਪ", "hi": "कूर सैं यूट्रोप", "pt": "Cour Saint Eutrope", "es": "Cour Saint Eutrope", "it": "Cour Saint Eutrope"},
    "Cour du Corbeau, Strasbourg": {"fr": "Cour du Corbeau, Strasbourg", "ml": "കൂർ ദ്യൂ കോർബോ, സ്ട്രാസ്ബൂർഗ്", "pa": "ਕੂਰ ਦਯੂ ਕੋਰਬੋ, ਸਟ੍ਰਾਸਬੁਰਗ", "hi": "कूर दयू कोरबो, स्ट्रासबुर्ग", "pt": "Cour du Corbeau, Estrasburgo", "es": "Cour du Corbeau, Estrasburgo", "it": "Cour du Corbeau, Strasburgo"},
    "Door in Florence": {"fr": "Porte à Florence", "ml": "ഫ്ലോറൻസിലെ വാതിൽ", "pa": "ਫਲੋਰੈਂਸ ਵਿੱਚ ਦਰਵਾਜ਼ਾ", "hi": "फ्लोरेंस में दरवाज़ा", "pt": "Porta em Florença", "es": "Puerta en Florencia", "it": "Porta a Firenze"},
    "Door of Santa Giustina, Padua": {"fr": "Porte de Santa Giustina, Padoue", "ml": "സാന്താ ജ്യൂസ്റ്റീനയുടെ വാതിൽ, പാദുവ", "pa": "ਸਾਂਤਾ ਜੂਸਤੀਨਾ ਦਾ ਦਰਵਾਜ਼ਾ, ਪਾਦੂਆ", "hi": "सांता जुस्तीना का दरवाज़ा, पादुआ", "pt": "Porta de Santa Giustina, Pádua", "es": "Puerta de Santa Giustina, Padua", "it": "Porta di Santa Giustina, Padova"},
    "Door, Mariacka Street in Katowice": {"fr": "Porte, rue Mariacka à Katowice", "ml": "വാതിൽ, കാറ്റോവിസിലെ മാരിയാക്ക തെരുവ്", "pa": "ਦਰਵਾਜ਼ਾ, ਕਾਤੋਵੀਤਸੇ ਵਿੱਚ ਮਾਰੀਆਕਾ ਗਲੀ", "hi": "दरवाज़ा, कातोवित्से में मारियाका स्ट्रीट", "pt": "Porta, Rua Mariacka em Katowice", "es": "Puerta, Calle Mariacka en Katowice", "it": "Porta, Via Mariacka a Katowice"},
    "Double Rainbow, Lyon": {"fr": "Double arc-en-ciel, Lyon", "ml": "ഇരട്ട മഴവില്ല്, ലിയോൺ", "pa": "ਦੋਹਰਾ ਸਤਰੰਗੀ ਪੀਂਘ, ਲਿਓਂ", "hi": "दोहरा इंद्रधनुष, ल्यों", "pt": "Arco-íris duplo, Lyon", "es": "Doble arcoíris, Lyon", "it": "Doppio arcobaleno, Lione"},
    "Drawing Barcelona": {"fr": "Dessin, Barcelone", "ml": "ചിത്രം, ബാഴ്സലോണ", "pa": "ਚਿੱਤਰ, ਬਾਰਸਿਲੋਨਾ", "hi": "चित्र, बार्सिलोना", "pt": "Desenho, Barcelona", "es": "Dibujo, Barcelona", "it": "Disegno, Barcellona"},
    "Eglise Saint-Pierre du Mont Saint-Michel": {"fr": "Église Saint-Pierre du Mont Saint-Michel", "ml": "മോൺ-സാൻ-മിഷേലിലെ സാൻ-പിയേർ പള്ളി", "pa": "ਮੋਂ-ਸਾਂ-ਮੀਸ਼ੇਲ ਦਾ ਸੈਂ-ਪੀਅਰ ਗਿਰਜਾਘਰ", "hi": "मों-सां-मिशेल का सैं-पियर गिरजाघर", "pt": "Igreja de Saint-Pierre do Monte Saint-Michel", "es": "Iglesia de Saint-Pierre del Monte Saint-Michel", "it": "Chiesa di Saint-Pierre a Mont Saint-Michel"},
    "Església de Sant Francesc de Sales Barcelona": {"fr": "Église de Sant Francesc de Sales, Barcelone", "ml": "സാന്ത് ഫ്രാൻസെസ്ക് ദെ സാലെസ് പള്ളി, ബാഴ്സലോണ", "pa": "ਸਾਂਤ ਫ੍ਰਾਂਸੇਸਕ ਦੇ ਸਾਲੇਸ ਗਿਰਜਾਘਰ, ਬਾਰਸਿਲੋਨਾ", "hi": "सांत फ्रांसेस्क दे सालेस गिरजाघर, बार्सिलोना", "pt": "Igreja de Sant Francesc de Sales, Barcelona", "es": "Iglesia de Sant Francesc de Sales, Barcelona", "it": "Chiesa di Sant Francesc de Sales, Barcellona"},
    "Evening Sky": {"fr": "Ciel du soir", "ml": "സന്ധ്യാകാശം", "pa": "ਸ਼ਾਮ ਦਾ ਅਸਮਾਨ", "hi": "सांध्य आकाश", "pt": "Céu ao entardecer", "es": "Cielo al atardecer", "it": "Cielo serale"},
    "Exterior of Cathédrale Saint-Pierre de Rennes": {"fr": "Extérieur de la cathédrale Saint-Pierre de Rennes", "ml": "റെന്നയിലെ സാൻ-പിയേർ കത്തീഡ്രലിന്റെ പുറംഭാഗം", "pa": "ਰੇਨ ਦੇ ਸੈਂ-ਪੀਅਰ ਕੈਥੇਡ੍ਰਲ ਦਾ ਬਾਹਰੀ ਹਿੱਸਾ", "hi": "रेन के सैं-पियर कैथेड्रल का बाहरी भाग", "pt": "Exterior da Catedral de Saint-Pierre de Rennes", "es": "Exterior de la Catedral de Saint-Pierre de Rennes", "it": "Esterno della Cattedrale di Saint-Pierre a Rennes"},
    "Exterior of Mary Magdalene Church in Wrocław": {"fr": "Extérieur de l'église Sainte-Marie-Madeleine à Wrocław", "ml": "വ്രോത്സ്വാവിലെ മേരി മഗ്ദലന പള്ളിയുടെ പുറംഭാഗം", "pa": "ਵ੍ਰੋਤਸਵਾਫ ਵਿੱਚ ਮੈਰੀ ਮੈਗਡਲੀਨ ਗਿਰਜਾਘਰ ਦਾ ਬਾਹਰੀ ਹਿੱਸਾ", "hi": "व्रॉत्सवाफ में मैरी मैग्डलीन चर्च का बाहरी भाग", "pt": "Exterior da Igreja de Maria Madalena em Wrocław", "es": "Exterior de la Iglesia de María Magdalena en Wrocław", "it": "Esterno della Chiesa di Maria Maddalena a Wrocław"},
    "Exterior of Théâtre Graslin": {"fr": "Extérieur du Théâtre Graslin", "ml": "തിയാത്ര് ഗ്രാസ്ലിന്റെ പുറംഭാഗം", "pa": "ਥੀਆਤ੍ਰ ਗ੍ਰਾਸਲੈਂ ਦਾ ਬਾਹਰੀ ਹਿੱਸਾ", "hi": "थिआत्र ग्रास्लां का बाहरी भाग", "pt": "Exterior do Théâtre Graslin", "es": "Exterior del Théâtre Graslin", "it": "Esterno del Théâtre Graslin"},
    "Façade with wood, Pérouges": {"fr": "Façade en bois, Pérouges", "ml": "തടി കൊണ്ടുള്ള മുൻഭാഗം, പേരൂജ്", "pa": "ਲੱਕੜ ਵਾਲਾ ਅਗਲਾ ਹਿੱਸਾ, ਪੇਰੂਜ", "hi": "लकड़ी का अग्रभाग, पेरूज", "pt": "Fachada de madeira, Pérouges", "es": "Fachada de madera, Pérouges", "it": "Facciata in legno, Pérouges"},
    "Fisherman's Bastion Budapest": {"fr": "Bastion des pêcheurs, Budapest", "ml": "ഫിഷർമാൻസ് ബാസ്റ്റ്യൺ, ബുഡാപെസ്റ്റ്", "pa": "ਫਿਸ਼ਰਮੈਨਜ਼ ਬੇਸ਼ਨ, ਬੁਡਾਪੇਸਟ", "hi": "फ़िशरमैन्स बेस्शन, बुडापेस्ट", "pt": "Bastião dos Pescadores, Budapeste", "es": "Bastión de los Pescadores, Budapest", "it": "Bastione dei Pescatori, Budapest"},
    "Fisherman's Bastion Detail Budapest": {"fr": "Détail du Bastion des pêcheurs, Budapest", "ml": "ഫിഷർമാൻസ് ബാസ്റ്റ്യൺ വിശദാംശം, ബുഡാപെസ്റ്റ്", "pa": "ਫਿਸ਼ਰਮੈਨਜ਼ ਬੇਸ਼ਨ ਦਾ ਵੇਰਵਾ, ਬੁਡਾਪੇਸਟ", "hi": "फ़िशरमैन्स बेस्शन का विवरण, बुडापेस्ट", "pt": "Detalhe do Bastião dos Pescadores, Budapeste", "es": "Detalle del Bastión de los Pescadores, Budapest", "it": "Dettaglio del Bastione dei Pescatori, Budapest"},
    "Flowers in Lyon": {"fr": "Fleurs à Lyon", "ml": "ലിയോണിലെ പൂക്കൾ", "pa": "ਲਿਓਂ ਵਿੱਚ ਫੁੱਲ", "hi": "ल्यों में फूल", "pt": "Flores em Lyon", "es": "Flores en Lyon", "it": "Fiori a Lione"},
    "Fort National (Saint-Malo)": {"fr": "Fort National (Saint-Malo)", "ml": "ഫോർട്ട് നാഷണൽ (സാൻ-മാലോ)", "pa": "ਫੋਰਟ ਨੈਸ਼ਨਲ (ਸੈਂ-ਮਾਲੋ)", "hi": "फोर्ट नेशनल (सैं-मालो)", "pt": "Forte Nacional (Saint-Malo)", "es": "Fuerte Nacional (Saint-Malo)", "it": "Forte Nazionale (Saint-Malo)"},
    "Fractals of nature, Lyon": {"fr": "Fractales de la nature, Lyon", "ml": "പ്രകൃതിയുടെ ഫ്രാക്റ്റലുകൾ, ലിയോൺ", "pa": "ਕੁਦਰਤ ਦੇ ਫ੍ਰੈਕਟਲ, ਲਿਓਂ", "hi": "प्रकृति के भग्न, ल्यों", "pt": "Fractais da natureza, Lyon", "es": "Fractales de la naturaleza, Lyon", "it": "Frattali della natura, Lione"},
    "Fresco at Knossos Heraklion": {"fr": "Fresque à Knossos, Héraklion", "ml": "ക്നോസോസിലെ ചുവർചിത്രം, ഹെറാക്ലിയോൺ", "pa": "ਕਨੋਸੋਸ ਵਿੱਚ ਫ੍ਰੈਸਕੋ, ਹੇਰਾਕਲਿਓਨ", "hi": "क्नोसोस में भित्तिचित्र, हेराक्लिओन", "pt": "Fresco em Cnossos, Heraclião", "es": "Fresco en Cnosos, Heraclión", "it": "Affresco a Cnosso, Heraklion"},
    "Front view, Templo Expiatorio del Sagrado Corazón": {"fr": "Vue de face, Templo Expiatorio del Sagrado Corazón", "ml": "മുൻവശ ദൃശ്യം, ടെംപ്ലോ എക്സ്പിയറ്റോറിയോ ഡെൽ സഗ്രാഡോ കൊറാസോൺ", "pa": "ਸਾਹਮਣੇ ਦਾ ਦ੍ਰਿਸ਼, ਟੈਂਪਲੋ ਐਕਸਪੀਆਤੋਰੀਓ ਡੇਲ ਸਾਗ੍ਰਾਡੋ ਕੋਰਾਸੋਨ", "hi": "सामने का दृश्य, तेम्प्लो एक्सपियातोरियो देल साग्रादो कोराज़ोन", "pt": "Vista frontal, Templo Expiatório do Sagrado Coração", "es": "Vista frontal, Templo Expiatorio del Sagrado Corazón", "it": "Vista frontale, Templo Expiatorio del Sagrado Corazón"},
    "Garden view, Rue du Prince, Pérouges": {"fr": "Vue du jardin, Rue du Prince, Pérouges", "ml": "പൂന്തോട്ട ദൃശ്യം, റ്യൂ ദ്യൂ പ്രിൻസ്, പേരൂജ്", "pa": "ਬਾਗ਼ ਦਾ ਦ੍ਰਿਸ਼, ਰਯੂ ਦਯੂ ਪ੍ਰਿੰਸ, ਪੇਰੂਜ", "hi": "बगीचे का दृश्य, रयू दयू प्रिंस, पेरूज", "pt": "Vista do jardim, Rue du Prince, Pérouges", "es": "Vista del jardín, Rue du Prince, Pérouges", "it": "Veduta del giardino, Rue du Prince, Pérouges"},
    "Golden Hour in Lyon": {"fr": "Heure dorée à Lyon", "ml": "ലിയോണിലെ സുവർണ്ണ നേരം", "pa": "ਲਿਓਂ ਵਿੱਚ ਸੁਨਹਿਰੀ ਘੜੀ", "hi": "ल्यों में स्वर्णिम बेला", "pt": "Hora dourada em Lyon", "es": "Hora dorada en Lyon", "it": "Ora dorata a Lione"},
    "Golden hour in Saint-Malo": {"fr": "Heure dorée à Saint-Malo", "ml": "സാൻ-മാലോയിലെ സുവർണ്ണ നേരം", "pa": "ਸੈਂ-ਮਾਲੋ ਵਿੱਚ ਸੁਨਹਿਰੀ ਘੜੀ", "hi": "सैं-मालो में स्वर्णिम बेला", "pt": "Hora dourada em Saint-Malo", "es": "Hora dorada en Saint-Malo", "it": "Ora dorata a Saint-Malo"},
    "Golden hour, Lyon": {"fr": "Heure dorée, Lyon", "ml": "സുവർണ്ണ നേരം, ലിയോൺ", "pa": "ਸੁਨਹਿਰੀ ਘੜੀ, ਲਿਓਂ", "hi": "स्वर्णिम बेला, ल्यों", "pt": "Hora dourada, Lyon", "es": "Hora dorada, Lyon", "it": "Ora dorata, Lione"},
    "Gondolas in Venice facing St Mark's Campanile": {"fr": "Gondoles à Venise face au campanile Saint-Marc", "ml": "സെന്റ് മാർക്ക് കാമ്പനൈലിന് അഭിമുഖമായി വെനീസിലെ ഗൊണ്ടോളകൾ", "pa": "ਸੇਂਟ ਮਾਰਕ ਕੈਂਪਾਨਾਈਲ ਦੇ ਸਾਹਮਣੇ ਵੇਨਿਸ ਵਿੱਚ ਗੋਂਡੋਲਾ", "hi": "सेंट मार्क कैंपानील के सामने वेनिस में गोंडोला", "pt": "Gôndolas em Veneza diante do Campanário de São Marcos", "es": "Góndolas en Venecia frente al Campanile de San Marcos", "it": "Gondole a Venezia di fronte al Campanile di San Marco"},
    "Gondolas in Venice, Italy": {"fr": "Gondoles à Venise, Italie", "ml": "വെനീസിലെ ഗൊണ്ടോളകൾ, ഇറ്റലി", "pa": "ਵੇਨਿਸ ਵਿੱਚ ਗੋਂਡੋਲਾ, ਇਟਲੀ", "hi": "वेनिस में गोंडोला, इटली", "pt": "Gôndolas em Veneza, Itália", "es": "Góndolas en Venecia, Italia", "it": "Gondole a Venezia, Italia"},
    "Hotel Monopol in Katowice": {"fr": "Hôtel Monopol à Katowice", "ml": "കാറ്റോവിസിലെ ഹോട്ടൽ മോണോപോൾ", "pa": "ਕਾਤੋਵੀਤਸੇ ਵਿੱਚ ਹੋਟਲ ਮੋਨੋਪੋਲ", "hi": "कातोवित्से में होटल मोनोपोल", "pt": "Hotel Monopol em Katowice", "es": "Hotel Monopol en Katowice", "it": "Hotel Monopol a Katowice"},
    "Houses In Stockholm": {"fr": "Maisons à Stockholm", "ml": "സ്റ്റോക്ക്ഹോമിലെ വീടുകൾ", "pa": "ਸਟਾਕਹੋਮ ਵਿੱਚ ਘਰ", "hi": "स्टॉकहोम में घर", "pt": "Casas em Estocolmo", "es": "Casas en Estocolmo", "it": "Case a Stoccolma"},
    "Houses in Gdansk on Motława river": {"fr": "Maisons à Gdansk sur la rivière Motława", "ml": "മോട്ലാവ നദിക്കരയിൽ ഗ്ദാൻസ്കിലെ വീടുകൾ", "pa": "ਮੋਟਲਾਵਾ ਨਦੀ ਉੱਤੇ ਗਦਾਂਸਕ ਵਿੱਚ ਘਰ", "hi": "मोटवावा नदी पर ग्दांस्क में घर", "pt": "Casas em Gdansk no rio Motława", "es": "Casas en Gdansk sobre el río Motława", "it": "Case a Danzica sul fiume Motława"},
    "Hôpital général de Clermont-Ferrand": {"fr": "Hôpital général de Clermont-Ferrand", "ml": "ക്ലെർമോൺ-ഫെറാനിലെ ജനറൽ ആശുപത്രി", "pa": "ਕਲੇਰਮੋਂ-ਫੇਰਾਂ ਦਾ ਜਨਰਲ ਹਸਪਤਾਲ", "hi": "क्लेरमों-फेरां का सामान्य अस्पताल", "pt": "Hospital geral de Clermont-Ferrand", "es": "Hospital general de Clermont-Ferrand", "it": "Ospedale generale di Clermont-Ferrand"},
    "Hôtel de La Noue, Rennes": {"fr": "Hôtel de La Noue, Rennes", "ml": "ഓത്തൽ ദെ ലാ നൂ, റെന്ന", "pa": "ਓਤੇਲ ਦੇ ਲਾ ਨੂ, ਰੇਨ", "hi": "ओतेल दे ला नू, रेन", "pt": "Hôtel de La Noue, Rennes", "es": "Hôtel de La Noue, Rennes", "it": "Hôtel de La Noue, Rennes"},
    "Immeuble, 10 rue Saint-Georges (Rennes)": {"fr": "Immeuble, 10 rue Saint-Georges (Rennes)", "ml": "കെട്ടിടം, 10 റ്യൂ സാൻ-ജോർജ് (റെന്ന)", "pa": "ਇਮਾਰਤ, 10 ਰਯੂ ਸੈਂ-ਜੋਰਜ (ਰੇਨ)", "hi": "इमारत, 10 रयू सैं-जॉर्ज (रेन)", "pt": "Edifício, 10 rue Saint-Georges (Rennes)", "es": "Edificio, 10 rue Saint-Georges (Rennes)", "it": "Edificio, 10 rue Saint-Georges (Rennes)"},
    "Interior of Abbey of Mont Saint-Michel": {"fr": "Intérieur de l'abbaye du Mont Saint-Michel", "ml": "മോൺ-സാൻ-മിഷേൽ ആശ്രമത്തിന്റെ അകംഭാഗം", "pa": "ਮੋਂ-ਸਾਂ-ਮੀਸ਼ੇਲ ਦੇ ਮੱਠ ਦਾ ਅੰਦਰੂਨੀ ਹਿੱਸਾ", "hi": "मों-सां-मिशेल के मठ का भीतरी भाग", "pt": "Interior da Abadia do Monte Saint-Michel", "es": "Interior de la Abadía del Monte Saint-Michel", "it": "Interno dell'Abbazia di Mont Saint-Michel"},
    "Interior of Basilica of San Juan de Dios, Granada": {"fr": "Intérieur de la basilique de San Juan de Dios, Grenade", "ml": "സാൻ ഹ്വാൻ ദെ ദിയോസ് ബസിലിക്കയുടെ അകംഭാഗം, ഗ്രനാഡ", "pa": "ਸਾਨ ਖੁਆਨ ਦੇ ਦਿਓਸ ਬੈਸਿਲਿਕਾ ਦਾ ਅੰਦਰੂਨੀ ਹਿੱਸਾ, ਗ੍ਰਾਨਾਦਾ", "hi": "सान खुआन दे दिओस बेसिलिका का भीतरी भाग, ग्रानादा", "pt": "Interior da Basílica de San Juan de Dios, Granada", "es": "Interior de la Basílica de San Juan de Dios, Granada", "it": "Interno della Basilica di San Juan de Dios, Granada"},
    "Interior of Basilique Saint-Martin d'Ainay (Lyon)": {"fr": "Intérieur de la basilique Saint-Martin d'Ainay (Lyon)", "ml": "സാൻ-മാർട്ടാൻ ദെനെ ബസിലിക്കയുടെ അകംഭാഗം (ലിയോൺ)", "pa": "ਸੈਂ-ਮਾਰਤੈਂ ਦੇਨੇ ਬੈਸਿਲਿਕਾ ਦਾ ਅੰਦਰੂਨੀ ਹਿੱਸਾ (ਲਿਓਂ)", "hi": "सैं-मार्तें देने बेसिलिका का भीतरी भाग (ल्यों)", "pt": "Interior da Basílica Saint-Martin d'Ainay (Lyon)", "es": "Interior de la Basílica Saint-Martin d'Ainay (Lyon)", "it": "Interno della Basilica di Saint-Martin d'Ainay (Lione)"},
    "Interior of Basilique Saint-Nicolas (Nantes)": {"fr": "Intérieur de la basilique Saint-Nicolas (Nantes)", "ml": "സാൻ-നിക്കോള ബസിലിക്കയുടെ അകംഭാഗം (നാന്ത്)", "pa": "ਸੈਂ-ਨਿਕੋਲਾ ਬੈਸਿਲਿਕਾ ਦਾ ਅੰਦਰੂਨੀ ਹਿੱਸਾ (ਨਾਂਤ)", "hi": "सैं-निकोला बेसिलिका का भीतरी भाग (नांत)", "pt": "Interior da Basílica Saint-Nicolas (Nantes)", "es": "Interior de la Basílica Saint-Nicolas (Nantes)", "it": "Interno della Basilica di Saint-Nicolas (Nantes)"},
    "Interior of Cathédrale Notre-Dame de Grenoble": {"fr": "Intérieur de la cathédrale Notre-Dame de Grenoble", "ml": "നോത്ര്-ദാം ദെ ഗ്രെനോബ്ല് കത്തീഡ്രലിന്റെ അകംഭാഗം", "pa": "ਨੋਤ੍ਰ-ਦਾਮ ਦੇ ਗ੍ਰੇਨੋਬਲ ਕੈਥੇਡ੍ਰਲ ਦਾ ਅੰਦਰੂਨੀ ਹਿੱਸਾ", "hi": "नोत्र-दाम दे ग्रेनोबल कैथेड्रल का भीतरी भाग", "pt": "Interior da Catedral Notre-Dame de Grenoble", "es": "Interior de la Catedral Notre-Dame de Grenoble", "it": "Interno della Cattedrale di Notre-Dame a Grenoble"},
    "Interior of Cathédrale Saint-Pierre de Nantes": {"fr": "Intérieur de la cathédrale Saint-Pierre de Nantes", "ml": "നാന്തിലെ സാൻ-പിയേർ കത്തീഡ്രലിന്റെ അകംഭാഗം", "pa": "ਨਾਂਤ ਦੇ ਸੈਂ-ਪੀਅਰ ਕੈਥੇਡ੍ਰਲ ਦਾ ਅੰਦਰੂਨੀ ਹਿੱਸਾ", "hi": "नांत के सैं-पियर कैथेड्रल का भीतरी भाग", "pt": "Interior da Catedral de Saint-Pierre de Nantes", "es": "Interior de la Catedral de Saint-Pierre de Nantes", "it": "Interno della Cattedrale di Saint-Pierre a Nantes"},
    "Interior of St. Mary Magdalene Church in Wrocław": {"fr": "Intérieur de l'église Sainte-Marie-Madeleine à Wrocław", "ml": "വ്രോത്സ്വാവിലെ വിശുദ്ധ മേരി മഗ്ദലന പള്ളിയുടെ അകംഭാഗം", "pa": "ਵ੍ਰੋਤਸਵਾਫ ਵਿੱਚ ਸੇਂਟ ਮੈਰੀ ਮੈਗਡਲੀਨ ਗਿਰਜਾਘਰ ਦਾ ਅੰਦਰੂਨੀ ਹਿੱਸਾ", "hi": "व्रॉत्सवाफ में सेंट मैरी मैग्डलीन चर्च का भीतरी भाग", "pt": "Interior da Igreja de Santa Maria Madalena em Wrocław", "es": "Interior de la Iglesia de Santa María Magdalena en Wrocław", "it": "Interno della Chiesa di Santa Maria Maddalena a Wrocław"},
    "Interior of Église Saint-Louis de Bordeaux": {"fr": "Intérieur de l'église Saint-Louis de Bordeaux", "ml": "ബോർഡോയിലെ സാൻ-ലൂയി പള്ളിയുടെ അകംഭാഗം", "pa": "ਬੋਰਡੋ ਦੇ ਸੈਂ-ਲੂਈ ਗਿਰਜਾਘਰ ਦਾ ਅੰਦਰੂਨੀ ਹਿੱਸਾ", "hi": "बोर्डो के सैं-लुई गिरजाघर का भीतरी भाग", "pt": "Interior da Igreja de Saint-Louis de Bordéus", "es": "Interior de la Iglesia de Saint-Louis de Burdeos", "it": "Interno della Chiesa di Saint-Louis a Bordeaux"},
    "Jardin des plantes de Nantes in Winter (December)": {"fr": "Jardin des plantes de Nantes en hiver (décembre)", "ml": "ശൈത്യകാലത്ത് നാന്തിലെ ജാർദാൻ ദേ പ്ലാന്ത് (ഡിസംബർ)", "pa": "ਸਰਦੀਆਂ ਵਿੱਚ ਨਾਂਤ ਦਾ ਜਾਰਦੈਂ ਦੇ ਪਲਾਂਤ (ਦਸੰਬਰ)", "hi": "सर्दियों में नांत का जारदां दे प्लांत (दिसंबर)", "pt": "Jardim das plantas de Nantes no inverno (dezembro)", "es": "Jardín de plantas de Nantes en invierno (diciembre)", "it": "Giardino delle piante di Nantes in inverno (dicembre)"},
    "Leaning Tower of Pisa": {"fr": "Tour penchée de Pise", "ml": "പിസയിലെ ചരിഞ്ഞ ഗോപുരം", "pa": "ਪੀਸਾ ਦਾ ਝੁਕਿਆ ਮੀਨਾਰ", "hi": "पीसा की झुकी मीनार", "pt": "Torre Inclinada de Pisa", "es": "Torre Inclinada de Pisa", "it": "Torre di Pisa"},
    "Lintel of Eglise Saint-Pierre de Clermont": {"fr": "Linteau de l'église Saint-Pierre de Clermont", "ml": "ക്ലെർമോണിലെ സാൻ-പിയേർ പള്ളിയുടെ കട്ടിളമേൽപ്പടി", "pa": "ਕਲੇਰਮੋਂ ਦੇ ਸੈਂ-ਪੀਅਰ ਗਿਰਜਾਘਰ ਦਾ ਸਰਦਲ", "hi": "क्लेरमों के सैं-पियर गिरजाघर का सरदल", "pt": "Lintel da Igreja de Saint-Pierre de Clermont", "es": "Dintel de la Iglesia de Saint-Pierre de Clermont", "it": "Architrave della Chiesa di Saint-Pierre a Clermont"},
    "Main hall of the Musée d'Orsay": {"fr": "Hall principal du Musée d'Orsay", "ml": "മ്യൂസെ ദോർസെയുടെ പ്രധാന ഹാൾ", "pa": "ਮਿਊਜ਼ੇ ਦੋਰਸੇ ਦਾ ਮੁੱਖ ਹਾਲ", "hi": "म्यूज़े दॉर्से का मुख्य हॉल", "pt": "Salão principal do Museu d'Orsay", "es": "Sala principal del Museo de Orsay", "it": "Sala principale del Museo d'Orsay"},
    "Market square of Nowy Sącz cityscape": {"fr": "Place du marché de Nowy Sącz", "ml": "നോവി-സോഞ്ച് നഗരദൃശ്യത്തിലെ ചന്തസ്ഥലം", "pa": "ਨੋਵੀ-ਸੋਂਚ ਦੇ ਸ਼ਹਿਰੀ ਦ੍ਰਿਸ਼ ਦਾ ਬਾਜ਼ਾਰ ਚੌਕ", "hi": "नोवी-सॉन्च नगरदृश्य का बाज़ार चौक", "pt": "Praça do mercado de Nowy Sącz", "es": "Plaza del mercado de Nowy Sącz", "it": "Piazza del mercato di Nowy Sącz"},
    "Matthias Church Roof Budapest": {"fr": "Toit de l'église Matthias, Budapest", "ml": "മത്തിയാസ് പള്ളിയുടെ മേൽക്കൂര, ബുഡാപെസ്റ്റ്", "pa": "ਮੈਥਿਆਸ ਚਰਚ ਦੀ ਛੱਤ, ਬੁਡਾਪੇਸਟ", "hi": "मथायस चर्च की छत, बुडापेस्ट", "pt": "Telhado da Igreja de Matthias, Budapeste", "es": "Tejado de la Iglesia de Matías, Budapest", "it": "Tetto della Chiesa di Mattia, Budapest"},
    "Matthias Church at Night Budapest": {"fr": "Église Matthias la nuit, Budapest", "ml": "രാത്രിയിൽ മത്തിയാസ് പള്ളി, ബുഡാപെസ്റ്റ്", "pa": "ਰਾਤ ਨੂੰ ਮੈਥਿਆਸ ਚਰਚ, ਬੁਡਾਪੇਸਟ", "hi": "रात में मथायस चर्च, बुडापेस्ट", "pt": "Igreja de Matthias à noite, Budapeste", "es": "Iglesia de Matías de noche, Budapest", "it": "Chiesa di Mattia di notte, Budapest"},
    "Mont Saint-Michel at sunset time": {"fr": "Mont Saint-Michel au coucher du soleil", "ml": "സൂര്യാസ്തമയ സമയത്ത് മോൺ-സാൻ-മിഷേൽ", "pa": "ਸੂਰਜ ਡੁੱਬਣ ਵੇਲੇ ਮੋਂ-ਸਾਂ-ਮੀਸ਼ੇਲ", "hi": "सूर्यास्त के समय मों-सां-मिशेल", "pt": "Monte Saint-Michel ao pôr do sol", "es": "Monte Saint-Michel al atardecer", "it": "Mont Saint-Michel al tramonto"},
    "Nantes St Nicolas basilica (Virgin altar)": {"fr": "Basilique Saint-Nicolas de Nantes (autel de la Vierge)", "ml": "നാന്ത് സെന്റ് നിക്കോളസ് ബസിലിക്ക (കന്യകയുടെ അൾത്താര)", "pa": "ਨਾਂਤ ਸੇਂਟ ਨਿਕੋਲਸ ਬੈਸਿਲਿਕਾ (ਕੁਆਰੀ ਮਰੀਅਮ ਦੀ ਵੇਦੀ)", "hi": "नांत सेंट निकोलस बेसिलिका (कुँवारी मरियम की वेदी)", "pt": "Basílica de São Nicolau de Nantes (altar da Virgem)", "es": "Basílica de San Nicolás de Nantes (altar de la Virgen)", "it": "Basilica di San Nicola di Nantes (altare della Vergine)"},
    "Narbonne market hall": {"fr": "Halle de Narbonne", "ml": "നാർബോൺ ചന്തമണ്ഡപം", "pa": "ਨਾਰਬੋਨ ਬਾਜ਼ਾਰ ਹਾਲ", "hi": "नारबोन बाज़ार हॉल", "pt": "Mercado coberto de Narbonne", "es": "Mercado cubierto de Narbona", "it": "Mercato coperto di Narbonne"},
    "National Garden Athens": {"fr": "Jardin national, Athènes", "ml": "ദേശീയ ഉദ്യാനം, ഏഥൻസ്", "pa": "ਰਾਸ਼ਟਰੀ ਬਾਗ਼, ਏਥਨਜ਼", "hi": "राष्ट्रीय उद्यान, एथेंस", "pt": "Jardim Nacional, Atenas", "es": "Jardín Nacional, Atenas", "it": "Giardino Nazionale, Atene"},
    "Nave of the Cathedral of Granada": {"fr": "Nef de la cathédrale de Grenade", "ml": "ഗ്രനാഡ കത്തീഡ്രലിന്റെ നടുത്തളം", "pa": "ਗ੍ਰਾਨਾਦਾ ਦੇ ਕੈਥੇਡ੍ਰਲ ਦੀ ਨੇਵ", "hi": "ग्रानादा के कैथेड्रल की नेव", "pt": "Nave da Catedral de Granada", "es": "Nave de la Catedral de Granada", "it": "Navata della Cattedrale di Granada"},
    "Notre-Dame de Grâce, Clermont-Ferrand": {"fr": "Notre-Dame de Grâce, Clermont-Ferrand", "ml": "നോത്ര്-ദാം ദെ ഗ്രാസ്, ക്ലെർമോൺ-ഫെറാൻ", "pa": "ਨੋਤ੍ਰ-ਦਾਮ ਦੇ ਗ੍ਰਾਸ, ਕਲੇਰਮੋਂ-ਫੇਰਾਂ", "hi": "नोत्र-दाम दे ग्रास, क्लेरमों-फेरां", "pt": "Notre-Dame de Grâce, Clermont-Ferrand", "es": "Notre-Dame de Grâce, Clermont-Ferrand", "it": "Notre-Dame de Grâce, Clermont-Ferrand"},
    "Palais de l'Isle Annecy": {"fr": "Palais de l'Isle, Annecy", "ml": "പാലെ ദെ ലിൽ, ആനസി", "pa": "ਪਾਲੇ ਦੇ ਲਿਲ, ਐਨੇਸੀ", "hi": "पाले दे लिल, एनेसी", "pt": "Palais de l'Isle, Annecy", "es": "Palais de l'Isle, Annecy", "it": "Palais de l'Isle, Annecy"},
    "Panoramic view of Lyon": {"fr": "Vue panoramique de Lyon", "ml": "ലിയോണിന്റെ സമഗ്രദൃശ്യം", "pa": "ਲਿਓਂ ਦਾ ਪੈਨੋਰਮਿਕ ਦ੍ਰਿਸ਼", "hi": "ल्यों का विहंगम दृश्य", "pt": "Vista panorâmica de Lyon", "es": "Vista panorámica de Lyon", "it": "Vista panoramica di Lione"},
    "Panoramic view of Lyon and trees": {"fr": "Vue panoramique de Lyon et des arbres", "ml": "ലിയോണിന്റെയും വൃക്ഷങ്ങളുടെയും സമഗ്രദൃശ്യം", "pa": "ਲਿਓਂ ਅਤੇ ਰੁੱਖਾਂ ਦਾ ਪੈਨੋਰਮਿਕ ਦ੍ਰਿਸ਼", "hi": "ल्यों और वृक्षों का विहंगम दृश्य", "pt": "Vista panorâmica de Lyon e árvores", "es": "Vista panorámica de Lyon y árboles", "it": "Vista panoramica di Lione e alberi"},
    "Panoramics of Nantes": {"fr": "Panoramas de Nantes", "ml": "നാന്തിന്റെ സമഗ്രദൃശ്യങ്ങൾ", "pa": "ਨਾਂਤ ਦੇ ਪੈਨੋਰਮਿਕ ਦ੍ਰਿਸ਼", "hi": "नांत के विहंगम दृश्य", "pt": "Panorâmicas de Nantes", "es": "Panorámicas de Nantes", "it": "Panoramiche di Nantes"},
    "Passage Pommeraye in Winter (December)": {"fr": "Passage Pommeraye en hiver (décembre)", "ml": "ശൈത്യകാലത്ത് പസാഷ് പൊമ്മറെ (ഡിസംബർ)", "pa": "ਸਰਦੀਆਂ ਵਿੱਚ ਪਾਸਾਜ ਪੋਮਰੇ (ਦਸੰਬਰ)", "hi": "सर्दियों में पासाज पोमरे (दिसंबर)", "pt": "Passage Pommeraye no inverno (dezembro)", "es": "Passage Pommeraye en invierno (diciembre)", "it": "Passage Pommeraye in inverno (dicembre)"},
    "Pipe organ of Basilique Saint-Nicolas (Nantes)": {"fr": "Orgue de la basilique Saint-Nicolas (Nantes)", "ml": "സാൻ-നിക്കോള ബസിലിക്കയിലെ പൈപ്പ് ഓർഗൻ (നാന്ത്)", "pa": "ਸੈਂ-ਨਿਕੋਲਾ ਬੈਸਿਲਿਕਾ ਦਾ ਪਾਈਪ ਆਰਗਨ (ਨਾਂਤ)", "hi": "सैं-निकोला बेसिलिका का पाइप ऑर्गन (नांत)", "pt": "Órgão de tubos da Basílica Saint-Nicolas (Nantes)", "es": "Órgano de tubos de la Basílica Saint-Nicolas (Nantes)", "it": "Organo a canne della Basilica di Saint-Nicolas (Nantes)"},
    "Pisa Cathedral": {"fr": "Cathédrale de Pise", "ml": "പിസ കത്തീഡ്രൽ", "pa": "ਪੀਸਾ ਕੈਥੇਡ੍ਰਲ", "hi": "पीसा कैथेड्रल", "pt": "Catedral de Pisa", "es": "Catedral de Pisa", "it": "Duomo di Pisa"},
    "Pisa Cathedral Detail": {"fr": "Détail de la cathédrale de Pise", "ml": "പിസ കത്തീഡ്രലിന്റെ വിശദാംശം", "pa": "ਪੀਸਾ ਕੈਥੇਡ੍ਰਲ ਦਾ ਵੇਰਵਾ", "hi": "पीसा कैथेड्रल का विवरण", "pt": "Detalhe da Catedral de Pisa", "es": "Detalle de la Catedral de Pisa", "it": "Dettaglio del Duomo di Pisa"},
    "Place du Marché aux Légumes (Saint-Malo)": {"fr": "Place du Marché aux Légumes (Saint-Malo)", "ml": "പ്ലാസ് ദ്യൂ മാർഷെ ഓ ലെഗ്യൂം (സാൻ-മാലോ)", "pa": "ਪਲਾਸ ਦਯੂ ਮਾਰਸ਼ੇ ਓ ਲੇਗਯੂਮ (ਸੈਂ-ਮਾਲੋ)", "hi": "प्लास दयू मार्शे ओ लेग्यूम (सैं-मालो)", "pt": "Praça do Mercado de Legumes (Saint-Malo)", "es": "Plaza del Mercado de Verduras (Saint-Malo)", "it": "Piazza del Mercato delle Verdure (Saint-Malo)"},
    "Pont-Vieux (Carcassonne, Aude)": {"fr": "Pont-Vieux (Carcassonne, Aude)", "ml": "പോൻ-വ്യൂ (കാർകസോൺ, ഓദ്)", "pa": "ਪੋਂ-ਵਿਯੂ (ਕਾਰਕਾਸੋਨ, ਔਦ)", "hi": "पों-व्यू (कारकासोन, औद)", "pt": "Pont-Vieux (Carcassonne, Aude)", "es": "Pont-Vieux (Carcasona, Aude)", "it": "Pont-Vieux (Carcassonne, Aude)"},
    "Portal in Stary Sącz": {"fr": "Portail à Stary Sącz", "ml": "സ്റ്റാരി-സോഞ്ചിലെ കവാടം", "pa": "ਸਟਾਰੀ-ਸੋਂਚ ਵਿੱਚ ਦਵਾਰ", "hi": "स्तारी-सॉन्च में प्रवेशद्वार", "pt": "Portal em Stary Sącz", "es": "Portal en Stary Sącz", "it": "Portale a Stary Sącz"},
    "Portal of église Saint-Merri, Paris": {"fr": "Portail de l'église Saint-Merri, Paris", "ml": "സാൻ-മെറി പള്ളിയുടെ കവാടം, പാരിസ്", "pa": "ਸੈਂ-ਮੈਰੀ ਗਿਰਜਾਘਰ ਦਾ ਦਵਾਰ, ਪੈਰਿਸ", "hi": "सैं-मेरी गिरजाघर का प्रवेशद्वार, पेरिस", "pt": "Portal da Igreja de Saint-Merri, Paris", "es": "Portal de la Iglesia de Saint-Merri, París", "it": "Portale della Chiesa di Saint-Merri, Parigi"},
    "Porte Cailhau": {"fr": "Porte Cailhau", "ml": "പോർട്ട് കായൂ", "pa": "ਪੋਰਟ ਕਾਯੂ", "hi": "पोर्त काइयू", "pt": "Porte Cailhau", "es": "Porte Cailhau", "it": "Porte Cailhau"},
    "Porte Mordelaise, Rennes": {"fr": "Porte Mordelaise, Rennes", "ml": "പോർട്ട് മോർദെലെസ്, റെന്ന", "pa": "ਪੋਰਟ ਮੋਰਦੇਲੇਜ਼, ਰੇਨ", "hi": "पोर्त मोर्देलेज़, रेन", "pt": "Porte Mordelaise, Rennes", "es": "Porte Mordelaise, Rennes", "it": "Porte Mordelaise, Rennes"},
    "Porte Saint-Vincent (Saint-Malo)": {"fr": "Porte Saint-Vincent (Saint-Malo)", "ml": "പോർട്ട് സാൻ-വാൻസാൻ (സാൻ-മാലോ)", "pa": "ਪੋਰਟ ਸੈਂ-ਵੈਂਸਾਂ (ਸੈਂ-ਮਾਲੋ)", "hi": "पोर्त सैं-वांसां (सैं-मालो)", "pt": "Porte Saint-Vincent (Saint-Malo)", "es": "Porte Saint-Vincent (Saint-Malo)", "it": "Porte Saint-Vincent (Saint-Malo)"},
    "Prison Saint-Michel (Rennes)": {"fr": "Prison Saint-Michel (Rennes)", "ml": "സാൻ-മിഷേൽ ജയിൽ (റെന്ന)", "pa": "ਸੈਂ-ਮੀਸ਼ੇਲ ਜੇਲ੍ਹ (ਰੇਨ)", "hi": "सैं-मिशेल जेल (रेन)", "pt": "Prisão Saint-Michel (Rennes)", "es": "Prisión Saint-Michel (Rennes)", "it": "Prigione Saint-Michel (Rennes)"},
    "Pulpit of Église Saint-Merri": {"fr": "Chaire de l'église Saint-Merri", "ml": "സാൻ-മെറി പള്ളിയുടെ പ്രസംഗപീഠം", "pa": "ਸੈਂ-ਮੈਰੀ ਗਿਰਜਾਘਰ ਦਾ ਪ੍ਰਚਾਰ-ਮੰਚ", "hi": "सैं-मेरी गिरजाघर का उपदेशमंच", "pt": "Púlpito da Igreja de Saint-Merri", "es": "Púlpito de la Iglesia de Saint-Merri", "it": "Pulpito della Chiesa di Saint-Merri"},
    "Pérouges": {"fr": "Pérouges", "ml": "പേരൂജ്", "pa": "ਪੇਰੂਜ", "hi": "पेरूज", "pt": "Pérouges", "es": "Pérouges", "it": "Pérouges"},
    "Red flowers in Bilbao": {"fr": "Fleurs rouges à Bilbao", "ml": "ബിൽബാവോയിലെ ചുവന്ന പൂക്കൾ", "pa": "ਬਿਲਬਾਓ ਵਿੱਚ ਲਾਲ ਫੁੱਲ", "hi": "बिलबाओ में लाल फूल", "pt": "Flores vermelhas em Bilbao", "es": "Flores rojas en Bilbao", "it": "Fiori rossi a Bilbao"},
    "Remote view of Santa Giustina, Padua": {"fr": "Vue lointaine de Santa Giustina, Padoue", "ml": "സാന്താ ജ്യൂസ്റ്റീനയുടെ ദൂരദൃശ്യം, പാദുവ", "pa": "ਸਾਂਤਾ ਜੂਸਤੀਨਾ ਦਾ ਦੂਰ ਦ੍ਰਿਸ਼, ਪਾਦੂਆ", "hi": "सांता जुस्तीना का दूर दृश्य, पादुआ", "pt": "Vista distante de Santa Giustina, Pádua", "es": "Vista lejana de Santa Giustina, Padua", "it": "Veduta lontana di Santa Giustina, Padova"},
    "Riverside façade of Palais Rohan, Strasbourg": {"fr": "Façade côté rivière du Palais Rohan, Strasbourg", "ml": "പാലെ റോഹാന്റെ നദീതീര മുൻഭാഗം, സ്ട്രാസ്ബൂർഗ്", "pa": "ਪਾਲੇ ਰੋਹਾਂ ਦਾ ਨਦੀ-ਕੰਢੇ ਵਾਲਾ ਅਗਲਾ ਹਿੱਸਾ, ਸਟ੍ਰਾਸਬੁਰਗ", "hi": "पाले रोहां का नदी किनारे वाला अग्रभाग, स्ट्रासबुर्ग", "pt": "Fachada ribeirinha do Palais Rohan, Estrasburgo", "es": "Fachada junto al río del Palais Rohan, Estrasburgo", "it": "Facciata sul fiume del Palais Rohan, Strasburgo"},
    "Saint Austremoine Church Facade Issoire": {"fr": "Façade de l'église Saint-Austremoine, Issoire", "ml": "സെന്റ് ഓസ്ട്രെമൊയ്ൻ പള്ളിയുടെ മുൻഭാഗം, ഇസ്വാർ", "pa": "ਸੇਂਟ ਆਸਤ੍ਰੇਮੋਇਨ ਗਿਰਜਾਘਰ ਦਾ ਅਗਲਾ ਹਿੱਸਾ, ਇਸਵਾਰ", "hi": "सेंट ऑस्त्रेमोइन गिरजाघर का अग्रभाग, इस्वार", "pt": "Fachada da Igreja de Saint-Austremoine, Issoire", "es": "Fachada de la Iglesia de Saint-Austremoine, Issoire", "it": "Facciata della Chiesa di Saint-Austremoine, Issoire"},
    "Saint Austremoine Church Interior Issoire": {"fr": "Intérieur de l'église Saint-Austremoine, Issoire", "ml": "സെന്റ് ഓസ്ട്രെമൊയ്ൻ പള്ളിയുടെ അകംഭാഗം, ഇസ്വാർ", "pa": "ਸੇਂਟ ਆਸਤ੍ਰੇਮੋਇਨ ਗਿਰਜਾਘਰ ਦਾ ਅੰਦਰੂਨੀ ਹਿੱਸਾ, ਇਸਵਾਰ", "hi": "सेंट ऑस्त्रेमोइन गिरजाघर का भीतरी भाग, इस्वार", "pt": "Interior da Igreja de Saint-Austremoine, Issoire", "es": "Interior de la Iglesia de Saint-Austremoine, Issoire", "it": "Interno della Chiesa di Saint-Austremoine, Issoire"},
    "Saint Austremoine Church Issoire": {"fr": "Église Saint-Austremoine, Issoire", "ml": "സെന്റ് ഓസ്ട്രെമൊയ്ൻ പള്ളി, ഇസ്വാർ", "pa": "ਸੇਂਟ ਆਸਤ੍ਰੇਮੋਇਨ ਗਿਰਜਾਘਰ, ਇਸਵਾਰ", "hi": "सेंट ऑस्त्रेमोइन गिरजाघर, इस्वार", "pt": "Igreja de Saint-Austremoine, Issoire", "es": "Iglesia de Saint-Austremoine, Issoire", "it": "Chiesa di Saint-Austremoine, Issoire"},
    "Sainte-Croix church of Lyon": {"fr": "Église Sainte-Croix de Lyon", "ml": "ലിയോണിലെ സാന്ത്-ക്ര്വ പള്ളി", "pa": "ਲਿਓਂ ਦਾ ਸੈਂਤ-ਕ੍ਰੂਆ ਗਿਰਜਾਘਰ", "hi": "ल्यों का सैंत-क्रूआ गिरजाघर", "pt": "Igreja de Sainte-Croix de Lyon", "es": "Iglesia de Sainte-Croix de Lyon", "it": "Chiesa di Sainte-Croix a Lione"},
    "Sanctuary of Our Lady of Lourdes": {"fr": "Sanctuaire Notre-Dame de Lourdes", "ml": "ലൂർദിലെ പരിശുദ്ധ കന്യാമറിയത്തിന്റെ തീർത്ഥകേന്ദ്രം", "pa": "ਲੂਰਦ ਦੀ ਮਾਤਾ ਮਰੀਅਮ ਦਾ ਤੀਰਥ ਅਸਥਾਨ", "hi": "लूर्द की देवी मरियम का तीर्थस्थल", "pt": "Santuário de Nossa Senhora de Lourdes", "es": "Santuario de Nuestra Señora de Lourdes", "it": "Santuario di Nostra Signora di Lourdes"},
    "Skyscrapers, Katowice": {"fr": "Gratte-ciel, Katowice", "ml": "അംബരചുംബികൾ, കാറ്റോവിസ്", "pa": "ਅਸਮਾਨ-ਛੂਹ ਇਮਾਰਤਾਂ, ਕਾਤੋਵੀਤਸੇ", "hi": "गगनचुंबी इमारतें, कातोवित्से", "pt": "Arranha-céus, Katowice", "es": "Rascacielos, Katowice", "it": "Grattacieli, Katowice"},
    "Snow in Montjuzet park": {"fr": "Neige dans le parc de Montjuzet", "ml": "മൊൻഷ്യൂസെ പാർക്കിലെ മഞ്ഞ്", "pa": "ਮੋਂਜ਼ੂਜ਼ੇ ਪਾਰਕ ਵਿੱਚ ਬਰਫ਼", "hi": "मोंजूज़े पार्क में बर्फ़", "pt": "Neve no parque de Montjuzet", "es": "Nieve en el parque de Montjuzet", "it": "Neve nel parco di Montjuzet"},
    "South portal of Notre-Dame du Port": {"fr": "Portail sud de Notre-Dame du Port", "ml": "നോത്ര്-ദാം ദ്യൂ പോറിന്റെ തെക്കേ കവാടം", "pa": "ਨੋਤ੍ਰ-ਦਾਮ ਦਯੂ ਪੋਰ ਦਾ ਦੱਖਣੀ ਦਵਾਰ", "hi": "नोत्र-दाम दयू पोर का दक्षिणी प्रवेशद्वार", "pt": "Portal sul de Notre-Dame du Port", "es": "Portal sur de Notre-Dame du Port", "it": "Portale sud di Notre-Dame du Port"},
    "Station of Stary Sącz": {"fr": "Gare de Stary Sącz", "ml": "സ്റ്റാരി-സോഞ്ചിലെ സ്റ്റേഷൻ", "pa": "ਸਟਾਰੀ-ਸੋਂਚ ਦਾ ਸਟੇਸ਼ਨ", "hi": "स्तारी-सॉन्च का स्टेशन", "pt": "Estação de Stary Sącz", "es": "Estación de Stary Sącz", "it": "Stazione di Stary Sącz"},
    "Statue in Tibidabo": {"fr": "Statue au Tibidabo", "ml": "തിബിദാബോയിലെ പ്രതിമ", "pa": "ਤਿਬਿਦਾਬੋ ਵਿੱਚ ਮੂਰਤੀ", "hi": "तिबिदाबो में प्रतिमा", "pt": "Estátua no Tibidabo", "es": "Estatua en el Tibidabo", "it": "Statua al Tibidabo"},
    "Statue of Giuseppe Verdi in Bilbao": {"fr": "Statue de Giuseppe Verdi à Bilbao", "ml": "ബിൽബാവോയിലെ ജ്യൂസെപ്പെ വെർദിയുടെ പ്രതിമ", "pa": "ਬਿਲਬਾਓ ਵਿੱਚ ਜੂਜ਼ੈੱਪੇ ਵਰਦੀ ਦੀ ਮੂਰਤੀ", "hi": "बिलबाओ में ज्यूसेप्पे वर्दी की प्रतिमा", "pt": "Estátua de Giuseppe Verdi em Bilbao", "es": "Estatua de Giuseppe Verdi en Bilbao", "it": "Statua di Giuseppe Verdi a Bilbao"},
    "Statue of man playing guitar, Katowice": {"fr": "Statue d'un homme jouant de la guitare, Katowice", "ml": "ഗിറ്റാർ വായിക്കുന്ന മനുഷ്യന്റെ പ്രതിമ, കാറ്റോവിസ്", "pa": "ਗਿਟਾਰ ਵਜਾਉਂਦੇ ਆਦਮੀ ਦੀ ਮੂਰਤੀ, ਕਾਤੋਵੀਤਸੇ", "hi": "गिटार बजाते आदमी की प्रतिमा, कातोवित्से", "pt": "Estátua de homem tocando guitarra, Katowice", "es": "Estatua de hombre tocando la guitarra, Katowice", "it": "Statua di un uomo che suona la chitarra, Katowice"},
    "Street benches in Katowice": {"fr": "Bancs publics à Katowice", "ml": "കാറ്റോവിസിലെ തെരുവ് ബെഞ്ചുകൾ", "pa": "ਕਾਤੋਵੀਤਸੇ ਵਿੱਚ ਗਲੀ ਦੇ ਬੈਂਚ", "hi": "कातोवित्से में सड़क की बेंचें", "pt": "Bancos de rua em Katowice", "es": "Bancos de calle en Katowice", "it": "Panchine di strada a Katowice"},
    "Street light Stockholm": {"fr": "Lampadaire, Stockholm", "ml": "തെരുവുവിളക്ക്, സ്റ്റോക്ക്ഹോം", "pa": "ਗਲੀ ਦੀ ਰੋਸ਼ਨੀ, ਸਟਾਕਹੋਮ", "hi": "सड़क की बत्ती, स्टॉकहोम", "pt": "Candeeiro de rua, Estocolmo", "es": "Farola, Estocolmo", "it": "Lampione, Stoccolma"},
    "Street light in Bilbao": {"fr": "Lampadaire à Bilbao", "ml": "ബിൽബാവോയിലെ തെരുവുവിളക്ക്", "pa": "ਬਿਲਬਾਓ ਵਿੱਚ ਗਲੀ ਦੀ ਰੋਸ਼ਨੀ", "hi": "बिलबाओ में सड़क की बत्ती", "pt": "Candeeiro de rua em Bilbao", "es": "Farola en Bilbao", "it": "Lampione a Bilbao"},
    "Street light in Granada": {"fr": "Lampadaire à Grenade", "ml": "ഗ്രനാഡയിലെ തെരുവുവിളക്ക്", "pa": "ਗ੍ਰਾਨਾਦਾ ਵਿੱਚ ਗਲੀ ਦੀ ਰੋਸ਼ਨੀ", "hi": "ग्रानादा में सड़क की बत्ती", "pt": "Candeeiro de rua em Granada", "es": "Farola en Granada", "it": "Lampione a Granada"},
    "Street light in Nowy Sącz": {"fr": "Lampadaire à Nowy Sącz", "ml": "നോവി-സോഞ്ചിലെ തെരുവുവിളക്ക്", "pa": "ਨੋਵੀ-ਸੋਂਚ ਵਿੱਚ ਗਲੀ ਦੀ ਰੋਸ਼ਨੀ", "hi": "नोवी-सॉन्च में सड़क की बत्ती", "pt": "Candeeiro de rua em Nowy Sącz", "es": "Farola en Nowy Sącz", "it": "Lampione a Nowy Sącz"},
    "Street light in Stary Sącz": {"fr": "Lampadaire à Stary Sącz", "ml": "സ്റ്റാരി-സോഞ്ചിലെ തെരുവുവിളക്ക്", "pa": "ਸਟਾਰੀ-ਸੋਂਚ ਵਿੱਚ ਗਲੀ ਦੀ ਰੋਸ਼ਨੀ", "hi": "स्तारी-सॉन्च में सड़क की बत्ती", "pt": "Candeeiro de rua em Stary Sącz", "es": "Farola en Stary Sącz", "it": "Lampione a Stary Sącz"},
    "Street light in Turin": {"fr": "Lampadaire à Turin", "ml": "ടൂറിനിലെ തെരുവുവിളക്ക്", "pa": "ਟੂਰਿਨ ਵਿੱਚ ਗਲੀ ਦੀ ਰੋਸ਼ਨੀ", "hi": "तूरिन में सड़क की बत्ती", "pt": "Candeeiro de rua em Turim", "es": "Farola en Turín", "it": "Lampione a Torino"},
    "Street light in Vaise": {"fr": "Lampadaire à Vaise", "ml": "വെയ്‌സിലെ തെരുവുവിളക്ക്", "pa": "ਵੇਜ਼ ਵਿੱਚ ਗਲੀ ਦੀ ਰੋਸ਼ਨੀ", "hi": "वेज़ में सड़क की बत्ती", "pt": "Candeeiro de rua em Vaise", "es": "Farola en Vaise", "it": "Lampione a Vaise"},
    "Street light of Abbey of Mont Saint-Michel": {"fr": "Lampadaire de l'abbaye du Mont Saint-Michel", "ml": "മോൺ-സാൻ-മിഷേൽ ആശ്രമത്തിലെ തെരുവുവിളക്ക്", "pa": "ਮੋਂ-ਸਾਂ-ਮੀਸ਼ੇਲ ਦੇ ਮੱਠ ਦੀ ਗਲੀ ਦੀ ਰੋਸ਼ਨੀ", "hi": "मों-सां-मिशेल के मठ की सड़क की बत्ती", "pt": "Candeeiro de rua da Abadia do Monte Saint-Michel", "es": "Farola de la Abadía del Monte Saint-Michel", "it": "Lampione dell'Abbazia di Mont Saint-Michel"},
    "Street lights detail Bologna": {"fr": "Détail des lampadaires, Bologne", "ml": "തെരുവുവിളക്കുകളുടെ വിശദാംശം, ബൊലോഞ്ഞ", "pa": "ਗਲੀ ਦੀਆਂ ਰੋਸ਼ਨੀਆਂ ਦਾ ਵੇਰਵਾ, ਬੋਲੋਨਿਆ", "hi": "सड़क की बत्तियों का विवरण, बोलोन्या", "pt": "Detalhe dos candeeiros de rua, Bolonha", "es": "Detalle de las farolas, Bolonia", "it": "Dettaglio dei lampioni, Bologna"},
    "Street lights in Bologna": {"fr": "Lampadaires à Bologne", "ml": "ബൊലോഞ്ഞയിലെ തെരുവുവിളക്കുകൾ", "pa": "ਬੋਲੋਨਿਆ ਵਿੱਚ ਗਲੀ ਦੀਆਂ ਰੋਸ਼ਨੀਆਂ", "hi": "बोलोन्या में सड़क की बत्तियाँ", "pt": "Candeeiros de rua em Bolonha", "es": "Farolas en Bolonia", "it": "Lampioni a Bologna"},
    "Street lights in Nantes": {"fr": "Lampadaires à Nantes", "ml": "നാന്തിലെ തെരുവുവിളക്കുകൾ", "pa": "ਨਾਂਤ ਵਿੱਚ ਗਲੀ ਦੀਆਂ ਰੋਸ਼ਨੀਆਂ", "hi": "नांत में सड़क की बत्तियाँ", "pt": "Candeeiros de rua em Nantes", "es": "Farolas en Nantes", "it": "Lampioni a Nantes"},
    "Street view in Carcassonne": {"fr": "Vue de rue à Carcassonne", "ml": "കാർകസോണിലെ തെരുവ് ദൃശ്യം", "pa": "ਕਾਰਕਾਸੋਨ ਵਿੱਚ ਗਲੀ ਦਾ ਦ੍ਰਿਸ਼", "hi": "कारकासोन में सड़क का दृश्य", "pt": "Vista de rua em Carcassonne", "es": "Vista de calle en Carcasona", "it": "Vista della strada a Carcassonne"},
    "Sunset and reflection of clouds in Venice": {"fr": "Coucher de soleil et reflet des nuages à Venise", "ml": "വെനീസിലെ സൂര്യാസ്തമയവും മേഘങ്ങളുടെ പ്രതിഫലനവും", "pa": "ਵੇਨਿਸ ਵਿੱਚ ਸੂਰਜ ਡੁੱਬਣਾ ਅਤੇ ਬੱਦਲਾਂ ਦਾ ਪ੍ਰਤੀਬਿੰਬ", "hi": "वेनिस में सूर्यास्त और बादलों का प्रतिबिंब", "pt": "Pôr do sol e reflexo das nuvens em Veneza", "es": "Atardecer y reflejo de las nubes en Venecia", "it": "Tramonto e riflesso delle nuvole a Venezia"},
    "Sunset viewed at Mons": {"fr": "Coucher de soleil vu à Mons", "ml": "മോൺസിൽ കണ്ട സൂര്യാസ്തമയം", "pa": "ਮੋਂਸ ਵਿੱਚ ਦੇਖਿਆ ਸੂਰਜ ਡੁੱਬਣਾ", "hi": "मॉन्स में देखा गया सूर्यास्त", "pt": "Pôr do sol visto em Mons", "es": "Atardecer visto en Mons", "it": "Tramonto visto a Mons"},
    "Sunset, Le Grand Crohot": {"fr": "Coucher de soleil, Le Grand Crohot", "ml": "സൂര്യാസ്തമയം, ലെ ഗ്രാൻ ക്രോവോ", "pa": "ਸੂਰਜ ਡੁੱਬਣਾ, ਲੇ ਗ੍ਰਾਂ ਕ੍ਰੋਓ", "hi": "सूर्यास्त, ले ग्रां क्रोओ", "pt": "Pôr do sol, Le Grand Crohot", "es": "Atardecer, Le Grand Crohot", "it": "Tramonto, Le Grand Crohot"},
    "Sunset, Pic-Saint-Loup": {"fr": "Coucher de soleil, Pic-Saint-Loup", "ml": "സൂര്യാസ്തമയം, പിക്-സാൻ-ലൂ", "pa": "ਸੂਰਜ ਡੁੱਬਣਾ, ਪਿਕ-ਸੈਂ-ਲੂ", "hi": "सूर्यास्त, पिक-सैं-लू", "pt": "Pôr do sol, Pic-Saint-Loup", "es": "Atardecer, Pic-Saint-Loup", "it": "Tramonto, Pic-Saint-Loup"},
    "Sunset, Plage du Môle (Saint-Malo)": {"fr": "Coucher de soleil, Plage du Môle (Saint-Malo)", "ml": "സൂര്യാസ്തമയം, പ്ലാഷ് ദ്യൂ മോൾ (സാൻ-മാലോ)", "pa": "ਸੂਰਜ ਡੁੱਬਣਾ, ਪਲਾਜ ਦਯੂ ਮੋਲ (ਸੈਂ-ਮਾਲੋ)", "hi": "सूर्यास्त, प्लाज दयू मोल (सैं-मालो)", "pt": "Pôr do sol, Plage du Môle (Saint-Malo)", "es": "Atardecer, Plage du Môle (Saint-Malo)", "it": "Tramonto, Plage du Môle (Saint-Malo)"},
    "Temple of Hephaestus Athens": {"fr": "Temple d'Héphaïstos, Athènes", "ml": "ഹെഫെസ്റ്റസ് ക്ഷേത്രം, ഏഥൻസ്", "pa": "ਹੇਫੈਸਟਸ ਦਾ ਮੰਦਰ, ਏਥਨਜ਼", "hi": "हेफ़ेस्तस का मंदिर, एथेंस", "pt": "Templo de Hefesto, Atenas", "es": "Templo de Hefesto, Atenas", "it": "Tempio di Efesto, Atene"},
    "Tree in Autumn in Mons at Sunset": {"fr": "Arbre en automne à Mons au coucher du soleil", "ml": "സൂര്യാസ്തമയത്തിൽ മോൺസിലെ ശരത്കാല വൃക്ഷം", "pa": "ਸੂਰਜ ਡੁੱਬਣ ਵੇਲੇ ਮੋਂਸ ਵਿੱਚ ਪਤਝੜ ਦਾ ਰੁੱਖ", "hi": "सूर्यास्त के समय मॉन्स में शरद ऋतु का पेड़", "pt": "Árvore no outono em Mons ao pôr do sol", "es": "Árbol en otoño en Mons al atardecer", "it": "Albero in autunno a Mons al tramonto"},
    "Trees in Mont Saint-Michel in Winter (December)": {"fr": "Arbres au Mont Saint-Michel en hiver (décembre)", "ml": "ശൈത്യകാലത്ത് മോൺ-സാൻ-മിഷേലിലെ വൃക്ഷങ്ങൾ (ഡിസംബർ)", "pa": "ਸਰਦੀਆਂ ਵਿੱਚ ਮੋਂ-ਸਾਂ-ਮੀਸ਼ੇਲ ਦੇ ਰੁੱਖ (ਦਸੰਬਰ)", "hi": "सर्दियों में मों-सां-मिशेल के पेड़ (दिसंबर)", "pt": "Árvores no Monte Saint-Michel no inverno (dezembro)", "es": "Árboles en el Monte Saint-Michel en invierno (diciembre)", "it": "Alberi a Mont Saint-Michel in inverno (dicembre)"},
    "Trees, Lempdes, Auvergne": {"fr": "Arbres, Lempdes, Auvergne", "ml": "വൃക്ഷങ്ങൾ, ലെംപ്‌ദ്, ഓവേർഞ്", "pa": "ਰੁੱਖ, ਲਾਂਪਦ, ਓਵੇਰਞ", "hi": "वृक्ष, लांप्द, ओवेर्ञ", "pt": "Árvores, Lempdes, Auvergne", "es": "Árboles, Lempdes, Auvernia", "it": "Alberi, Lempdes, Alvernia"},
    "Twilight, Plage du Môle (Saint-Malo)": {"fr": "Crépuscule, Plage du Môle (Saint-Malo)", "ml": "സന്ധ്യ, പ്ലാഷ് ദ്യൂ മോൾ (സാൻ-മാലോ)", "pa": "ਸ਼ਾਮ ਦਾ ਘੁਸਮੁਸਾ, ਪਲਾਜ ਦਯੂ ਮੋਲ (ਸੈਂ-ਮਾਲੋ)", "hi": "गोधूलि, प्लाज दयू मोल (सैं-मालो)", "pt": "Crepúsculo, Plage du Môle (Saint-Malo)", "es": "Crepúsculo, Plage du Môle (Saint-Malo)", "it": "Crepuscolo, Plage du Môle (Saint-Malo)"},
    "Victoire de Samothrace, Montpellier": {"fr": "Victoire de Samothrace, Montpellier", "ml": "വിക്ത്വാർ ദെ സമോത്രാസ്, മോംപെലിയേ", "pa": "ਵਿਕਤੁਆਰ ਦੇ ਸਮੋਤ੍ਰਾਸ, ਮੋਂਪੇਲੀਏ", "hi": "विकत्वार दे समोत्रास, मोंपेलिये", "pt": "Vitória de Samotrácia, Montpellier", "es": "Victoria de Samotracia, Montpellier", "it": "Vittoria di Samotracia, Montpellier"},
    "View of Château de Châteauvieux from Lake Annecy": {"fr": "Vue du Château de Châteauvieux depuis le lac d'Annecy", "ml": "ആനസി തടാകത്തിൽ നിന്നുള്ള ഷാറ്റോ ദെ ഷാറ്റോവ്യൂവിന്റെ ദൃശ്യം", "pa": "ਐਨੇਸੀ ਝੀਲ ਤੋਂ ਸ਼ਾਤੋ ਦੇ ਸ਼ਾਤੋਵੀਯੂ ਦਾ ਦ੍ਰਿਸ਼", "hi": "एनेसी झील से शातो दे शातोव्यू का दृश्य", "pt": "Vista do Château de Châteauvieux a partir do Lago de Annecy", "es": "Vista del Château de Châteauvieux desde el lago de Annecy", "it": "Veduta del Château de Châteauvieux dal Lago di Annecy"},
    "View of John Paul II Altar in Stary Sącz": {"fr": "Vue de l'autel Jean-Paul II à Stary Sącz", "ml": "സ്റ്റാരി-സോഞ്ചിലെ ജോൺ പോൾ രണ്ടാമൻ അൾത്താരയുടെ ദൃശ്യം", "pa": "ਸਟਾਰੀ-ਸੋਂਚ ਵਿੱਚ ਜੌਨ ਪੌਲ ਦੂਜੇ ਦੀ ਵੇਦੀ ਦਾ ਦ੍ਰਿਸ਼", "hi": "स्तारी-सॉन्च में जॉन पॉल द्वितीय की वेदी का दृश्य", "pt": "Vista do altar de João Paulo II em Stary Sącz", "es": "Vista del altar de Juan Pablo II en Stary Sącz", "it": "Veduta dell'altare di Giovanni Paolo II a Stary Sącz"},
    "View of Nowy Sącz": {"fr": "Vue de Nowy Sącz", "ml": "നോവി-സോഞ്ചിന്റെ ദൃശ്യം", "pa": "ਨੋਵੀ-ਸੋਂਚ ਦਾ ਦ੍ਰਿਸ਼", "hi": "नोवी-सॉन्च का दृश्य", "pt": "Vista de Nowy Sącz", "es": "Vista de Nowy Sącz", "it": "Veduta di Nowy Sącz"},
    "View of Nowy Sącz cityscape": {"fr": "Vue panoramique de Nowy Sącz", "ml": "നോവി-സോഞ്ച് നഗരദൃശ്യം", "pa": "ਨੋਵੀ-ਸੋਂਚ ਦੇ ਸ਼ਹਿਰੀ ਦ੍ਰਿਸ਼ ਦਾ ਨਜ਼ਾਰਾ", "hi": "नोवी-सॉन्च नगरदृश्य का नज़ारा", "pt": "Vista da paisagem urbana de Nowy Sącz", "es": "Vista del paisaje urbano de Nowy Sącz", "it": "Veduta del paesaggio urbano di Nowy Sącz"},
    "View of Saint-Malo Beach": {"fr": "Vue de la plage de Saint-Malo", "ml": "സാൻ-മാലോ കടൽത്തീരത്തിന്റെ ദൃശ്യം", "pa": "ਸੈਂ-ਮਾਲੋ ਬੀਚ ਦਾ ਦ੍ਰਿਸ਼", "hi": "सैं-मालो समुद्र तट का दृश्य", "pt": "Vista da praia de Saint-Malo", "es": "Vista de la playa de Saint-Malo", "it": "Veduta della spiaggia di Saint-Malo"},
    "View of high altar of Annecy cathedral": {"fr": "Vue du maître-autel de la cathédrale d'Annecy", "ml": "ആനസി കത്തീഡ്രലിന്റെ പ്രധാന അൾത്താരയുടെ ദൃശ്യം", "pa": "ਐਨੇਸੀ ਕੈਥੇਡ੍ਰਲ ਦੀ ਮੁੱਖ ਵੇਦੀ ਦਾ ਦ੍ਰਿਸ਼", "hi": "एनेसी कैथेड्रल की मुख्य वेदी का दृश्य", "pt": "Vista do altar-mor da catedral de Annecy", "es": "Vista del altar mayor de la catedral de Annecy", "it": "Veduta dell'altare maggiore della cattedrale di Annecy"},
    "View of main organ of Annecy cathedral": {"fr": "Vue de l'orgue principal de la cathédrale d'Annecy", "ml": "ആനസി കത്തീഡ്രലിന്റെ പ്രധാന ഓർഗന്റെ ദൃശ്യം", "pa": "ਐਨੇਸੀ ਕੈਥੇਡ੍ਰਲ ਦੇ ਮੁੱਖ ਆਰਗਨ ਦਾ ਦ੍ਰਿਸ਼", "hi": "एनेसी कैथेड्रल के मुख्य ऑर्गन का दृश्य", "pt": "Vista do órgão principal da catedral de Annecy", "es": "Vista del órgano principal de la catedral de Annecy", "it": "Veduta dell'organo principale della cattedrale di Annecy"},
    "Walls at Knossos Heraklion": {"fr": "Murs à Knossos, Héraklion", "ml": "ക്നോസോസിലെ ചുവരുകൾ, ഹെറാക്ലിയോൺ", "pa": "ਕਨੋਸੋਸ ਦੀਆਂ ਕੰਧਾਂ, ਹੇਰਾਕਲਿਓਨ", "hi": "क्नोसोस की दीवारें, हेराक्लिओन", "pt": "Muros em Cnossos, Heraclião", "es": "Muros en Cnosos, Heraclión", "it": "Mura a Cnosso, Heraklion"},
    "Water reflections of trees, Parc de la Tête d'Or": {"fr": "Reflets des arbres dans l'eau, Parc de la Tête d'Or", "ml": "വൃക്ഷങ്ങളുടെ ജലപ്രതിഫലനങ്ങൾ, പാർക് ദെ ലാ തെത് ദോർ", "pa": "ਰੁੱਖਾਂ ਦੇ ਪਾਣੀ ਵਿਚਲੇ ਪ੍ਰਤੀਬਿੰਬ, ਪਾਰਕ ਦੇ ਲਾ ਤੇਤ ਦੋਰ", "hi": "वृक्षों के जल-प्रतिबिंब, पार्क दे ला तेत दोर", "pt": "Reflexos das árvores na água, Parc de la Tête d'Or", "es": "Reflejos de los árboles en el agua, Parc de la Tête d'Or", "it": "Riflessi degli alberi nell'acqua, Parc de la Tête d'Or"},
    "West facade of Cathédrale Saint-Pierre de Rennes": {"fr": "Façade ouest de la cathédrale Saint-Pierre de Rennes", "ml": "റെന്നയിലെ സാൻ-പിയേർ കത്തീഡ്രലിന്റെ പടിഞ്ഞാറൻ മുൻഭാഗം", "pa": "ਰੇਨ ਦੇ ਸੈਂ-ਪੀਅਰ ਕੈਥੇਡ੍ਰਲ ਦਾ ਪੱਛਮੀ ਅਗਲਾ ਹਿੱਸਾ", "hi": "रेन के सैं-पियर कैथेड्रल का पश्चिमी अग्रभाग", "pt": "Fachada oeste da Catedral de Saint-Pierre de Rennes", "es": "Fachada oeste de la Catedral de Saint-Pierre de Rennes", "it": "Facciata ovest della Cattedrale di Saint-Pierre a Rennes"},
    "Windows of Wartburg Castle": {"fr": "Fenêtres du château de la Wartburg", "ml": "വാർട്ട്‌ബർഗ് കോട്ടയുടെ ജനാലകൾ", "pa": "ਵਾਰਟਬਰਗ ਕਿਲ੍ਹੇ ਦੀਆਂ ਖਿੜਕੀਆਂ", "hi": "वार्टबुर्ग किले की खिड़कियाँ", "pt": "Janelas do Castelo de Wartburg", "es": "Ventanas del Castillo de Wartburg", "it": "Finestre del Castello di Wartburg"},
    "Windows, Pérouges": {"fr": "Fenêtres, Pérouges", "ml": "ജനാലകൾ, പേരൂജ്", "pa": "ਖਿੜਕੀਆਂ, ਪੇਰੂਜ", "hi": "खिड़कियाँ, पेरूज", "pt": "Janelas, Pérouges", "es": "Ventanas, Pérouges", "it": "Finestre, Pérouges"},
    "Église Saint-Aubin Toulouse": {"fr": "Église Saint-Aubin, Toulouse", "ml": "സാൻ-ഓബാൻ പള്ളി, തുലൂസ്", "pa": "ਸੈਂ-ਓਬੈਂ ਗਿਰਜਾਘਰ, ਤੁਲੂਜ਼", "hi": "सैं-ओबें गिरजाघर, तुलूज", "pt": "Igreja de Saint-Aubin, Toulouse", "es": "Iglesia de Saint-Aubin, Tolosa", "it": "Chiesa di Saint-Aubin, Tolosa"},
    "Église Saint-Louis de Bordeaux": {"fr": "Église Saint-Louis de Bordeaux", "ml": "ബോർഡോയിലെ സാൻ-ലൂയി പള്ളി", "pa": "ਬੋਰਡੋ ਦਾ ਸੈਂ-ਲੂਈ ਗਿਰਜਾਘਰ", "hi": "बोर्डो का सैं-लुई गिरजाघर", "pt": "Igreja de Saint-Louis de Bordéus", "es": "Iglesia de Saint-Louis de Burdeos", "it": "Chiesa di Saint-Louis a Bordeaux"},
    "Église Saint-Pierre-aux-Liens (Moissat-Bas)": {"fr": "Église Saint-Pierre-aux-Liens (Moissat-Bas)", "ml": "സാൻ-പിയേർ-ഓ-ലിയാൻ പള്ളി (മോയ്സ-ബാ)", "pa": "ਸੈਂ-ਪੀਅਰ-ਓ-ਲੀਆਂ ਗਿਰਜਾਘਰ (ਮੋਇਸਾ-ਬਾ)", "hi": "सैं-पियर-ओ-लियां गिरजाघर (मोइसा-बा)", "pt": "Igreja de Saint-Pierre-aux-Liens (Moissat-Bas)", "es": "Iglesia de Saint-Pierre-aux-Liens (Moissat-Bas)", "it": "Chiesa di Saint-Pierre-aux-Liens (Moissat-Bas)"},
    "Église Saint-Pothin (Lyon)": {"fr": "Église Saint-Pothin (Lyon)", "ml": "സാൻ-പോത്താൻ പള്ളി (ലിയോൺ)", "pa": "ਸੈਂ-ਪੋਤੈਂ ਗਿਰਜਾਘਰ (ਲਿਓਂ)", "hi": "सैं-पोतें गिरजाघर (ल्यों)", "pt": "Igreja de Saint-Pothin (Lyon)", "es": "Iglesia de Saint-Pothin (Lyon)", "it": "Chiesa di Saint-Pothin (Lione)"},
    "Église Saint-Sébastien de Narbonne": {"fr": "Église Saint-Sébastien de Narbonne", "ml": "നാർബോണിലെ സാൻ-സെബാസ്ത്യാൻ പള്ളി", "pa": "ਨਾਰਬੋਨ ਦਾ ਸੈਂ-ਸੇਬਾਸਤੀਅਨ ਗਿਰਜਾਘਰ", "hi": "नारबोन का सैं-सेबास्तिएं गिरजाघर", "pt": "Igreja de Saint-Sébastien de Narbonne", "es": "Iglesia de Saint-Sébastien de Narbona", "it": "Chiesa di Saint-Sébastien a Narbonne"},
    "Église Sainte-Anne de Montpellier": {"fr": "Église Sainte-Anne de Montpellier", "ml": "മോംപെലിയേയിലെ സാന്ത്-ആൻ പള്ളി", "pa": "ਮੋਂਪੇਲੀਏ ਦਾ ਸੈਂਤ-ਆਨ ਗਿਰਜਾਘਰ", "hi": "मोंपेलिये का सैंत-आन गिरजाघर", "pt": "Igreja de Sainte-Anne de Montpellier", "es": "Iglesia de Sainte-Anne de Montpellier", "it": "Chiesa di Sainte-Anne a Montpellier"},
    "Église Sainte-Madeleine-de-l'Île de Martigues": {"fr": "Église Sainte-Madeleine-de-l'Île de Martigues", "ml": "മാർട്ടിഗിലെ സാന്ത്-മദ്‌ലെൻ-ദെ-ലിൽ പള്ളി", "pa": "ਮਾਰਤੀਗ ਦਾ ਸੈਂਤ-ਮਾਦਲੇਨ-ਦੇ-ਲਿਲ ਗਿਰਜਾਘਰ", "hi": "मार्तिग का सैंत-मादलेन-दे-लिल गिरजाघर", "pt": "Igreja de Sainte-Madeleine-de-l'Île de Martigues", "es": "Iglesia de Sainte-Madeleine-de-l'Île de Martigues", "it": "Chiesa di Sainte-Madeleine-de-l'Île a Martigues"},
    "Église de Sainte Cécile de Loupian": {"fr": "Église Sainte-Cécile de Loupian", "ml": "ലൂപ്പിയാനിലെ സാന്ത്-സെസീൽ പള്ളി", "pa": "ਲੂਪਿਆਂ ਦਾ ਸੈਂਤ-ਸੇਸੀਲ ਗਿਰਜਾਘਰ", "hi": "लूपियां का सैंत-सेसील गिरजाघर", "pt": "Igreja de Sainte-Cécile de Loupian", "es": "Iglesia de Sainte-Cécile de Loupian", "it": "Chiesa di Sainte-Cécile a Loupian"},
    "Église du Bon-Pasteur (Lyon)": {"fr": "Église du Bon-Pasteur (Lyon)", "ml": "ബോൺ-പാസ്ത്യൂർ പള്ളി (ലിയോൺ)", "pa": "ਬੋਂ-ਪਾਸਤਯੂਰ ਗਿਰਜਾਘਰ (ਲਿਓਂ)", "hi": "बों-पास्तर गिरजाघर (ल्यों)", "pt": "Igreja do Bom Pastor (Lyon)", "es": "Iglesia del Buen Pastor (Lyon)", "it": "Chiesa del Buon Pastore (Lione)"},
    "Basilica di San Giorgio Maggiore (Venice) - remote view": {"fr": "Basilique San Giorgio Maggiore (Venise) - vue lointaine", "ml": "സാൻ ജോർജോ മാജോറെ ബസിലിക്ക (വെനീസ്) - ദൂരദൃശ്യം", "pa": "ਸਾਨ ਜੋਰਜੋ ਮਾਜੋਰੇ ਬੈਸਿਲਿਕਾ (ਵੇਨਿਸ) - ਦੂਰ ਦ੍ਰਿਸ਼", "hi": "सान जोर्जो माजोरे बेसिलिका (वेनिस) - दूर दृश्य", "pt": "Basílica de San Giorgio Maggiore (Veneza) - vista distante", "es": "Basílica de San Giorgio Maggiore (Venecia) - vista lejana", "it": "Basilica di San Giorgio Maggiore (Venezia) - veduta lontana"},
    "Ceiling, Église Sainte-Marie-Madeleine de Pérouges": {"fr": "Plafond, Église Sainte-Marie-Madeleine de Pérouges", "ml": "സാന്ത്-മാരി-മദ്‌ലെൻ ദെ പേരൂജ് പള്ളിയുടെ മേൽത്തട്ട്", "pa": "ਸੈਂਤ-ਮਾਰੀ-ਮਾਦਲੇਨ ਦੇ ਪੇਰੂਜ ਗਿਰਜਾਘਰ ਦੀ ਛੱਤ", "hi": "सैंत-मारी-मादलेन दे पेरूज गिरजाघर की छत", "pt": "Teto, Igreja de Sainte-Marie-Madeleine de Pérouges", "es": "Techo, Iglesia de Sainte-Marie-Madeleine de Pérouges", "it": "Soffitto, Chiesa di Sainte-Marie-Madeleine a Pérouges"},
    "Cistern of the Chaplaincy of the Mont Saint-Michel Abbey": {"fr": "Citerne de l'aumônerie de l'abbaye du Mont Saint-Michel", "ml": "മോൺ-സാൻ-മിഷേൽ ആശ്രമത്തിലെ ചാപ്ലെൻസിയുടെ ജലസംഭരണി", "pa": "ਮੋਂ-ਸਾਂ-ਮੀਸ਼ੇਲ ਦੇ ਮੱਠ ਦੀ ਚੈਪਲੈਂਸੀ ਦੀ ਜਲ-ਟੈਂਕੀ", "hi": "मों-सां-मिशेल मठ के पादरीगृह का जलकुंड", "pt": "Cisterna da capelania da Abadia do Monte Saint-Michel", "es": "Cisterna de la capellanía de la Abadía del Monte Saint-Michel", "it": "Cisterna della cappellania dell'Abbazia di Mont Saint-Michel"},
    "Exterior of Basilique Saint-Nazaire de Carcassonne": {"fr": "Extérieur de la basilique Saint-Nazaire de Carcassonne", "ml": "കാർകസോണിലെ സാൻ-നസേർ ബസിലിക്കയുടെ പുറംഭാഗം", "pa": "ਕਾਰਕਾਸੋਨ ਦੀ ਸੈਂ-ਨਜ਼ੇਰ ਬੈਸਿਲਿਕਾ ਦਾ ਬਾਹਰੀ ਹਿੱਸਾ", "hi": "कारकासोन की सैं-नजेर बेसिलिका का बाहरी भाग", "pt": "Exterior da Basílica de Saint-Nazaire de Carcassonne", "es": "Exterior de la Basílica de Saint-Nazaire de Carcasona", "it": "Esterno della Basilica di Saint-Nazaire a Carcassonne"},
    "Exterior of Cathédrale Saint-Pierre de Montpellier": {"fr": "Extérieur de la cathédrale Saint-Pierre de Montpellier", "ml": "മോംപെലിയേയിലെ സാൻ-പിയേർ കത്തീഡ്രലിന്റെ പുറംഭാഗം", "pa": "ਮੋਂਪੇਲੀਏ ਦੇ ਸੈਂ-ਪੀਅਰ ਕੈਥੇਡ੍ਰਲ ਦਾ ਬਾਹਰੀ ਹਿੱਸਾ", "hi": "मोंपेलिये के सैं-पियर कैथेड्रल का बाहरी भाग", "pt": "Exterior da Catedral de Saint-Pierre de Montpellier", "es": "Exterior de la Catedral de Saint-Pierre de Montpellier", "it": "Esterno della Cattedrale di Saint-Pierre a Montpellier"},
    "Exterior of Saint-Pierre-le-Jeune Protestant Church, Strasbourg": {"fr": "Extérieur de l'église protestante Saint-Pierre-le-Jeune, Strasbourg", "ml": "സാൻ-പിയേർ-ലെ-ഷ്യൂൻ പ്രൊട്ടസ്റ്റന്റ് പള്ളിയുടെ പുറംഭാഗം, സ്ട്രാസ്ബൂർഗ്", "pa": "ਸੈਂ-ਪੀਅਰ-ਲੇ-ਜਨ ਪ੍ਰੋਟੈਸਟੈਂਟ ਗਿਰਜਾਘਰ ਦਾ ਬਾਹਰੀ ਹਿੱਸਾ, ਸਟ੍ਰਾਸਬੁਰਗ", "hi": "सैं-पियर-ले-जन प्रोटेस्टेंट गिरजाघर का बाहरी भाग, स्ट्रासबुर्ग", "pt": "Exterior da Igreja Protestante Saint-Pierre-le-Jeune, Estrasburgo", "es": "Exterior de la Iglesia Protestante Saint-Pierre-le-Jeune, Estrasburgo", "it": "Esterno della Chiesa Protestante Saint-Pierre-le-Jeune, Strasburgo"},
    "Exterior view of Immaculate Conception church in Katowice": {"fr": "Vue extérieure de l'église de l'Immaculée-Conception à Katowice", "ml": "കാറ്റോവിസിലെ അമലോത്ഭവ പള്ളിയുടെ പുറംദൃശ്യം", "pa": "ਕਾਤੋਵੀਤਸੇ ਵਿੱਚ ਇਮੈਕੁਲੇਟ ਕਨਸੈਪਸ਼ਨ ਗਿਰਜਾਘਰ ਦਾ ਬਾਹਰੀ ਦ੍ਰਿਸ਼", "hi": "कातोवित्से में इमैकुलेट कन्सेप्शन गिरजाघर का बाहरी दृश्य", "pt": "Vista exterior da Igreja da Imaculada Conceição em Katowice", "es": "Vista exterior de la Iglesia de la Inmaculada Concepción en Katowice", "it": "Vista esterna della Chiesa dell'Immacolata Concezione a Katowice"},
    "Facade details of Cathedral of Granada in Plaza de las Pasiegas": {"fr": "Détails de la façade de la cathédrale de Grenade sur la Plaza de las Pasiegas", "ml": "പ്ലാസ ദെ ലാസ് പാസിയേഗാസിലെ ഗ്രനാഡ കത്തീഡ്രലിന്റെ മുൻഭാഗ വിശദാംശങ്ങൾ", "pa": "ਪਲਾਜ਼ਾ ਦੇ ਲਾਸ ਪਾਸੀਏਗਾਸ ਵਿੱਚ ਗ੍ਰਾਨਾਦਾ ਦੇ ਕੈਥੇਡ੍ਰਲ ਦੇ ਅਗਲੇ ਹਿੱਸੇ ਦੇ ਵੇਰਵੇ", "hi": "प्लाज़ा दे लास पासिएगास में ग्रानादा के कैथेड्रल के अग्रभाग का विवरण", "pt": "Detalhes da fachada da Catedral de Granada na Plaza de las Pasiegas", "es": "Detalles de la fachada de la Catedral de Granada en la Plaza de las Pasiegas", "it": "Dettagli della facciata della Cattedrale di Granada in Plaza de las Pasiegas"},
    "Fountain in front of building of Polish National Radio Symphony Orchestra, Katowice": {"fr": "Fontaine devant le bâtiment de l'Orchestre symphonique national de la radio polonaise, Katowice", "ml": "പോളിഷ് നാഷണൽ റേഡിയോ സിംഫണി ഓർക്കസ്ട്രയുടെ കെട്ടിടത്തിന് മുന്നിലെ ജലധാര, കാറ്റോവിസ്", "pa": "ਪੋਲਿਸ਼ ਨੈਸ਼ਨਲ ਰੇਡੀਓ ਸਿੰਫਨੀ ਆਰਕੈਸਟਰਾ ਦੀ ਇਮਾਰਤ ਦੇ ਸਾਹਮਣੇ ਫੁਹਾਰਾ, ਕਾਤੋਵੀਤਸੇ", "hi": "पोलिश नेशनल रेडियो सिम्फनी ऑर्केस्ट्रा की इमारत के सामने फव्वारा, कातोवित्से", "pt": "Fonte em frente ao edifício da Orquestra Sinfónica Nacional da Rádio Polaca, Katowice", "es": "Fuente frente al edificio de la Orquesta Sinfónica Nacional de la Radio Polaca, Katowice", "it": "Fontana davanti all'edificio dell'Orchestra Sinfonica Nazionale della Radio Polacca, Katowice"},
    "Frescos of Saint-Pierre-le-Jeune Protestant Church, Strasbourg (Cloister)": {"fr": "Fresques de l'église protestante Saint-Pierre-le-Jeune, Strasbourg (cloître)", "ml": "സാൻ-പിയേർ-ലെ-ഷ്യൂൻ പ്രൊട്ടസ്റ്റന്റ് പള്ളിയിലെ ചുവർചിത്രങ്ങൾ, സ്ട്രാസ്ബൂർഗ് (ക്ലോയിസ്റ്റർ)", "pa": "ਸੈਂ-ਪੀਅਰ-ਲੇ-ਜਨ ਪ੍ਰੋਟੈਸਟੈਂਟ ਗਿਰਜਾਘਰ ਦੇ ਫ੍ਰੈਸਕੋ, ਸਟ੍ਰਾਸਬੁਰਗ (ਕਲੋਇਸਟਰ)", "hi": "सैं-पियर-ले-जन प्रोटेस्टेंट गिरजाघर के भित्तिचित्र, स्ट्रासबुर्ग (क्लॉइस्टर)", "pt": "Frescos da Igreja Protestante Saint-Pierre-le-Jeune, Estrasburgo (Claustro)", "es": "Frescos de la Iglesia Protestante Saint-Pierre-le-Jeune, Estrasburgo (Claustro)", "it": "Affreschi della Chiesa Protestante Saint-Pierre-le-Jeune, Strasburgo (Chiostro)"},
    "Interior details of St. Mary Magdalene Church in Wrocław": {"fr": "Détails intérieurs de l'église Sainte-Marie-Madeleine à Wrocław", "ml": "വ്രോത്സ്വാവിലെ വിശുദ്ധ മേരി മഗ്ദലന പള്ളിയുടെ അകത്തെ വിശദാംശങ്ങൾ", "pa": "ਵ੍ਰੋਤਸਵਾਫ ਵਿੱਚ ਸੇਂਟ ਮੈਰੀ ਮੈਗਡਲੀਨ ਗਿਰਜਾਘਰ ਦੇ ਅੰਦਰੂਨੀ ਵੇਰਵੇ", "hi": "व्रॉत्सवाफ में सेंट मैरी मैग्डलीन चर्च के भीतरी विवरण", "pt": "Detalhes interiores da Igreja de Santa Maria Madalena em Wrocław", "es": "Detalles interiores de la Iglesia de Santa María Magdalena en Wrocław", "it": "Dettagli interni della Chiesa di Santa Maria Maddalena a Wrocław"},
    "Interior of Abbatiale de Mont Saint-Michel 20 (cropped)": {"fr": "Intérieur de l'abbatiale du Mont Saint-Michel", "ml": "മോൺ-സാൻ-മിഷേൽ ആശ്രമപ്പള്ളിയുടെ അകംഭാഗം", "pa": "ਮੋਂ-ਸਾਂ-ਮੀਸ਼ੇਲ ਦੇ ਮੱਠ-ਗਿਰਜਾਘਰ ਦਾ ਅੰਦਰੂਨੀ ਹਿੱਸਾ", "hi": "मों-सां-मिशेल के मठ-गिरजाघर का भीतरी भाग", "pt": "Interior da Igreja Abacial do Monte Saint-Michel", "es": "Interior de la Iglesia Abacial del Monte Saint-Michel", "it": "Interno della Chiesa Abbaziale di Mont Saint-Michel"},
    "Interior of Chapelle Sainte-Anne-des-Grèves de Saint-Malo": {"fr": "Intérieur de la chapelle Sainte-Anne-des-Grèves de Saint-Malo", "ml": "സാൻ-മാലോയിലെ സാന്ത്-ആൻ-ദേ-ഗ്രെവ് ചാപ്പലിന്റെ അകംഭാഗം", "pa": "ਸੈਂ-ਮਾਲੋ ਦੀ ਸੈਂਤ-ਆਨ-ਦੇ-ਗ੍ਰੇਵ ਚੈਪਲ ਦਾ ਅੰਦਰੂਨੀ ਹਿੱਸਾ", "hi": "सैं-मालो की सैंत-आन-दे-ग्रेव चैपल का भीतरी भाग", "pt": "Interior da Capela Sainte-Anne-des-Grèves de Saint-Malo", "es": "Interior de la Capilla Sainte-Anne-des-Grèves de Saint-Malo", "it": "Interno della Cappella Sainte-Anne-des-Grèves a Saint-Malo"},
    "Interior view of Église Sainte-Madeleine-de-l'Île de Martigues": {"fr": "Vue intérieure de l'église Sainte-Madeleine-de-l'Île de Martigues", "ml": "മാർട്ടിഗിലെ സാന്ത്-മദ്‌ലെൻ-ദെ-ലിൽ പള്ളിയുടെ അകംദൃശ്യം", "pa": "ਮਾਰਤੀਗ ਦੇ ਸੈਂਤ-ਮਾਦਲੇਨ-ਦੇ-ਲਿਲ ਗਿਰਜਾਘਰ ਦਾ ਅੰਦਰੂਨੀ ਦ੍ਰਿਸ਼", "hi": "मार्तिग के सैंत-मादलेन-दे-लिल गिरजाघर का भीतरी दृश्य", "pt": "Vista interior da Igreja de Sainte-Madeleine-de-l'Île de Martigues", "es": "Vista interior de la Iglesia de Sainte-Madeleine-de-l'Île de Martigues", "it": "Vista interna della Chiesa di Sainte-Madeleine-de-l'Île a Martigues"},
    "March of the Nations towards the Cross, Strasbourg": {"fr": "Marche des nations vers la Croix, Strasbourg", "ml": "കുരിശിലേക്കുള്ള രാഷ്ട്രങ്ങളുടെ പ്രയാണം, സ്ട്രാസ്ബൂർഗ്", "pa": "ਸਲੀਬ ਵੱਲ ਕੌਮਾਂ ਦਾ ਮਾਰਚ, ਸਟ੍ਰਾਸਬੁਰਗ", "hi": "क्रॉस की ओर राष्ट्रों का कूच, स्ट्रासबुर्ग", "pt": "Marcha das Nações rumo à Cruz, Estrasburgo", "es": "Marcha de las Naciones hacia la Cruz, Estrasburgo", "it": "Marcia delle Nazioni verso la Croce, Strasburgo"},
    "Panoramic View of Clermont-Ferrand from Montjuzet Park": {"fr": "Vue panoramique de Clermont-Ferrand depuis le parc de Montjuzet", "ml": "മൊൻഷ്യൂസെ പാർക്കിൽ നിന്നുള്ള ക്ലെർമോൺ-ഫെറാന്റെ സമഗ്രദൃശ്യം", "pa": "ਮੋਂਜ਼ੂਜ਼ੇ ਪਾਰਕ ਤੋਂ ਕਲੇਰਮੋਂ-ਫੇਰਾਂ ਦਾ ਪੈਨੋਰਮਿਕ ਦ੍ਰਿਸ਼", "hi": "मोंजूज़े पार्क से क्लेरमों-फेरां का विहंगम दृश्य", "pt": "Vista panorâmica de Clermont-Ferrand a partir do Parque de Montjuzet", "es": "Vista panorámica de Clermont-Ferrand desde el Parque de Montjuzet", "it": "Vista panoramica di Clermont-Ferrand dal Parco di Montjuzet"},
    "Pipe organ of Saint-Pierre-le-Jeune Protestant Church - Strasbourg": {"fr": "Orgue de l'église protestante Saint-Pierre-le-Jeune - Strasbourg", "ml": "സാൻ-പിയേർ-ലെ-ഷ്യൂൻ പ്രൊട്ടസ്റ്റന്റ് പള്ളിയിലെ പൈപ്പ് ഓർഗൻ - സ്ട്രാസ്ബൂർഗ്", "pa": "ਸੈਂ-ਪੀਅਰ-ਲੇ-ਜਨ ਪ੍ਰੋਟੈਸਟੈਂਟ ਗਿਰਜਾਘਰ ਦਾ ਪਾਈਪ ਆਰਗਨ - ਸਟ੍ਰਾਸਬੁਰਗ", "hi": "सैं-पियर-ले-जन प्रोटेस्टेंट गिरजाघर का पाइप ऑर्गन - स्ट्रासबुर्ग", "pt": "Órgão de tubos da Igreja Protestante Saint-Pierre-le-Jeune - Estrasburgo", "es": "Órgano de tubos de la Iglesia Protestante Saint-Pierre-le-Jeune - Estrasburgo", "it": "Organo a canne della Chiesa Protestante Saint-Pierre-le-Jeune - Strasburgo"},
    "Reflection of building of Polish National Radio Symphony Orchestra, Katowice": {"fr": "Reflet du bâtiment de l'Orchestre symphonique national de la radio polonaise, Katowice", "ml": "പോളിഷ് നാഷണൽ റേഡിയോ സിംഫണി ഓർക്കസ്ട്രയുടെ കെട്ടിടത്തിന്റെ പ്രതിഫലനം, കാറ്റോവിസ്", "pa": "ਪੋਲਿਸ਼ ਨੈਸ਼ਨਲ ਰੇਡੀਓ ਸਿੰਫਨੀ ਆਰਕੈਸਟਰਾ ਦੀ ਇਮਾਰਤ ਦਾ ਪ੍ਰਤੀਬਿੰਬ, ਕਾਤੋਵੀਤਸੇ", "hi": "पोलिश नेशनल रेडियो सिम्फनी ऑर्केस्ट्रा की इमारत का प्रतिबिंब, कातोवित्से", "pt": "Reflexo do edifício da Orquestra Sinfónica Nacional da Rádio Polaca, Katowice", "es": "Reflejo del edificio de la Orquesta Sinfónica Nacional de la Radio Polaca, Katowice", "it": "Riflesso dell'edificio dell'Orchestra Sinfonica Nazionale della Radio Polacca, Katowice"},
    "Remote view of Mont Saint-Michel Abbey in the morning": {"fr": "Vue lointaine de l'abbaye du Mont Saint-Michel le matin", "ml": "രാവിലെ മോൺ-സാൻ-മിഷേൽ ആശ്രമത്തിന്റെ ദൂരദൃശ്യം", "pa": "ਸਵੇਰੇ ਮੋਂ-ਸਾਂ-ਮੀਸ਼ੇਲ ਦੇ ਮੱਠ ਦਾ ਦੂਰ ਦ੍ਰਿਸ਼", "hi": "सुबह मों-सां-मिशेल मठ का दूर दृश्य", "pt": "Vista distante da Abadia do Monte Saint-Michel pela manhã", "es": "Vista lejana de la Abadía del Monte Saint-Michel por la mañana", "it": "Veduta lontana dell'Abbazia di Mont Saint-Michel al mattino"},
    "Silbermann pipe organ of Église Saint-Thomas, Strasbourg": {"fr": "Orgue Silbermann de l'église Saint-Thomas, Strasbourg", "ml": "സാൻ-തോമ പള്ളിയിലെ സിൽബർമാൻ പൈപ്പ് ഓർഗൻ, സ്ട്രാസ്ബൂർഗ്", "pa": "ਸੈਂ-ਤੋਮਾ ਗਿਰਜਾਘਰ ਦਾ ਸਿਲਬਰਮਾਨ ਪਾਈਪ ਆਰਗਨ, ਸਟ੍ਰਾਸਬੁਰਗ", "hi": "सैं-तोमा गिरजाघर का सिल्बरमान पाइप ऑर्गन, स्ट्रासबुर्ग", "pt": "Órgão de tubos Silbermann da Igreja de Saint-Thomas, Estrasburgo", "es": "Órgano de tubos Silbermann de la Iglesia de Saint-Thomas, Estrasburgo", "it": "Organo a canne Silbermann della Chiesa di Saint-Thomas, Strasburgo"},
    "Stained glass windows of the Basilique Saint-Nazaire de Carcassonne": {"fr": "Vitraux de la basilique Saint-Nazaire de Carcassonne", "ml": "കാർകസോണിലെ സാൻ-നസേർ ബസിലിക്കയുടെ സ്റ്റെയിൻഡ് ഗ്ലാസ് ജനാലകൾ", "pa": "ਕਾਰਕਾਸੋਨ ਦੀ ਸੈਂ-ਨਜ਼ੇਰ ਬੈਸਿਲਿਕਾ ਦੀਆਂ ਰੰਗਦਾਰ ਕੱਚ ਦੀਆਂ ਖਿੜਕੀਆਂ", "hi": "कारकासोन की सैं-नजेर बेसिलिका की रंगीन काँच की खिड़कियाँ", "pt": "Vitrais da Basílica de Saint-Nazaire de Carcassonne", "es": "Vidrieras de la Basílica de Saint-Nazaire de Carcasona", "it": "Vetrate della Basilica di Saint-Nazaire a Carcassonne"},
    "Tympanum of the central portal of the western facade of Notre-Dame de Strasbourg": {"fr": "Tympan du portail central de la façade occidentale de Notre-Dame de Strasbourg", "ml": "നോത്ര്-ദാം ദെ സ്ട്രാസ്ബൂർഗിന്റെ പടിഞ്ഞാറൻ മുൻഭാഗത്തെ കേന്ദ്ര കവാടത്തിന്റെ ടിംപനം", "pa": "ਨੋਤ੍ਰ-ਦਾਮ ਦੇ ਸਟ੍ਰਾਸਬੁਰਗ ਦੇ ਪੱਛਮੀ ਅਗਲੇ ਹਿੱਸੇ ਦੇ ਕੇਂਦਰੀ ਦਵਾਰ ਦਾ ਟਿੰਪਨਮ", "hi": "नोत्र-दाम दे स्ट्रासबुर्ग के पश्चिमी अग्रभाग के केंद्रीय प्रवेशद्वार का टिम्पैनम", "pt": "Tímpano do portal central da fachada ocidental de Notre-Dame de Estrasburgo", "es": "Tímpano del portal central de la fachada occidental de Notre-Dame de Estrasburgo", "it": "Timpano del portale centrale della facciata occidentale di Notre-Dame di Strasburgo"},
    "Vitraux de la cathédrale Saint-Vincent de Saint-Malo": {"fr": "Vitraux de la cathédrale Saint-Vincent de Saint-Malo", "ml": "സാൻ-മാലോയിലെ സാൻ-വാൻസാൻ കത്തീഡ്രലിന്റെ സ്റ്റെയിൻഡ് ഗ്ലാസ് ജനാലകൾ", "pa": "ਸੈਂ-ਮਾਲੋ ਦੇ ਸੈਂ-ਵੈਂਸਾਂ ਕੈਥੇਡ੍ਰਲ ਦੀਆਂ ਰੰਗਦਾਰ ਕੱਚ ਦੀਆਂ ਖਿੜਕੀਆਂ", "hi": "सैं-मालो के सैं-वांसां कैथेड्रल की रंगीन काँच की खिड़कियाँ", "pt": "Vitrais da Catedral de Saint-Vincent de Saint-Malo", "es": "Vidrieras de la Catedral de Saint-Vincent de Saint-Malo", "it": "Vetrate della Cattedrale di Saint-Vincent a Saint-Malo"},
    "Église Notre-Dame-de-la-Nativité de Mons at Sunset": {"fr": "Église Notre-Dame-de-la-Nativité de Mons au coucher du soleil", "ml": "സൂര്യാസ്തമയത്തിൽ മോൺസിലെ നോത്ര്-ദാം-ദെ-ലാ-നാറ്റിവിറ്റേ പള്ളി", "pa": "ਸੂਰਜ ਡੁੱਬਣ ਵੇਲੇ ਮੋਂਸ ਦਾ ਨੋਤ੍ਰ-ਦਾਮ-ਦੇ-ਲਾ-ਨਾਤੀਵੀਤੇ ਗਿਰਜਾਘਰ", "hi": "सूर्यास्त के समय मॉन्स का नोत्र-दाम-दे-ला-नातिविते गिरजाघर", "pt": "Igreja Notre-Dame-de-la-Nativité de Mons ao pôr do sol", "es": "Iglesia Notre-Dame-de-la-Nativité de Mons al atardecer", "it": "Chiesa di Notre-Dame-de-la-Nativité a Mons al tramonto"},
}


def escape_image_text(text: str, in_attr: bool = False) -> str:
    """Escape only what HTML strictly requires, preserving accents/apostrophes."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if in_attr:
        text = text.replace('"', "&quot;")
    return text


def translate_image_text(text: str, lang: str) -> str:
    if lang == "en":
        return text
    key = text.strip()
    for table in (PHOTO_ALT_TRANSLATIONS, PHOTO_CAPTION_TRANSLATIONS):
        translated = table.get(key, {}).get(lang)
        if translated:
            return translated
    return text


def translate_image_descriptions(content: str, lang: str) -> str:
    """Translate gallery photo alt text and photo-location captions in place."""
    if lang == "en":
        return content

    def replace_alt(match: re.Match[str]) -> str:
        translated = translate_image_text(html.unescape(match.group(2)), lang)
        return f"{match.group(1)}{escape_image_text(translated, in_attr=True)}{match.group(3)}"

    content = re.sub(
        r'(<img\b[^>]*\balt=")([^"]*)("[^>]*\bclass="photo-image")',
        replace_alt,
        content,
    )

    def replace_caption(match: re.Match[str]) -> str:
        translated = translate_image_text(strip_tags(match.group(2)), lang)
        return f"{match.group(1)}{escape_image_text(translated)}{match.group(3)}"

    return re.sub(
        r'(<h4 class="photo-location">)(.*?)(</h4>)',
        replace_caption,
        content,
        flags=re.DOTALL,
    )


MANUAL_PAGE_GROUPS = [
    {
        "en": "en/photography/an-amateur.html",
        "fr": "fr/voyages/un-amateur.html",
        "ml": "ml/യാത്രകൾ/അമച്വർ-ഫോട്ടോഗ്രാഫർ.html",
        "pa": "pa/ਯਾਤਰਾ/ਇੱਕ-ਸ਼ੁਕੀਨ.html",
        "hi": "hi/यात्रा/एक-शौकिया-फोटोग्राफर.html",
        "pt": "pt/viagens/um-amador.html",
        "es": "es/viajes/un-aficionado.html",
        "it": "it/viaggi/un-dilettante.html",
    },
    {
        "en": "en/travel/drawings.html",
        "fr": "fr/voyages/dessins.html",
        "ml": "ml/യാത്രകൾ/ചിത്രങ്ങൾ.html",
        "pa": "pa/ਯਾਤਰਾ/ਚਿੱਤਰਕਾਰੀ.html",
        "hi": "hi/यात्रा/चित्र.html",
        "pt": "pt/viagens/desenhos.html",
        "es": "es/viajes/dibujos.html",
        "it": "it/viaggi/disegni.html",
    },
    {
        "en": "en/photography/celebrations.html",
        "fr": "fr/voyages/festivités.html",
        "ml": "ml/യാത്രകൾ/ആഘോഷങ്ങൾ.html",
        "pa": "pa/ਯਾਤਰਾ/ਜਸ਼ਨ.html",
        "hi": "hi/यात्रा/समारोह.html",
        "pt": "pt/viagens/celebrações.html",
        "es": "es/viajes/celebraciones.html",
        "it": "it/viaggi/celebrazioni.html",
    },
    {
        "en": "en/travel/miles-to-go.html",
        "fr": "fr/voyages/kilomètres-à-parcourir.html",
        "ml": "ml/യാത്രകൾ/മൈലുകൾ-പോകണം.html",
        "pa": "pa/ਯਾਤਰਾ/ਸਫ਼ਰ-ਕਰਨ-ਲਈ-ਕਿਲੋਮੀਟਰ-ਹਨ.html",
        "hi": "hi/यात्रा/कई-किलोमीटर-की-यात्रा-करनी-है.html",
        "pt": "pt/viagens/milhas-por-percorrer.html",
        "es": "es/viajes/millas-por-recorrer.html",
        "it": "it/viaggi/miglia-da-percorrere.html",
    },
    {
        "en": "en/travel/pilgrimage.html",
        "fr": "fr/voyages/pèlerinage.html",
        "ml": "ml/യാത്രകൾ/തീർത്ഥാടനം.html",
        "pa": "pa/ਯਾਤਰਾ/ਤੀਰਥ-ਯਾਤਰਾ.html",
        "hi": "hi/यात्रा/तीर्थयात्रा.html",
        "pt": "pt/viagens/peregrinação.html",
        "es": "es/viajes/peregrinación.html",
        "it": "it/viaggi/pellegrinaggio.html",
    },
    {
        "en": "en/photography/software.html",
        "fr": "fr/voyages/logiciel.html",
        "ml": "ml/യാത്രകൾ/സോഫ്‌റ്റ്‌വെയർ.html",
        "pa": "pa/ਯਾਤਰਾ/ਸਾਫਟਵੇਅਰ.html",
        "hi": "hi/यात्रा/सॉफ़्टवेयर.html",
        "pt": "pt/viagens/software.html",
        "es": "es/viajes/software.html",
        "it": "it/viaggi/software.html",
    },
    {
        "en": "en/photography/sunset.html",
        "fr": "fr/voyages/coucher-du-soleil.html",
        "ml": "ml/യാത്രകൾ/സൂര്യാസ്തമയം.html",
        "pa": "pa/ਯਾਤਰਾ/ਸੂਰਜ-ਡੁੱਬਣ.html",
        "hi": "hi/यात्रा/सूर्यास्त.html",
        "pt": "pt/viagens/pôr-do-sol.html",
        "es": "es/viajes/atardecer.html",
        "it": "it/viaggi/tramonto.html",
    },
]


@dataclass
class GalleryItem:
    image_src: str
    label: str
    href: str = ""
    image_alt: str = ""


@dataclass
class GallerySection:
    title: str
    items: list[GalleryItem] = field(default_factory=list)


@dataclass
class OldTravelPage:
    path: Path
    lang: str
    title: str
    heading: str
    nav_labels: dict[str, tuple[str, str]]
    sections: list[GallerySection]
    content_html: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str, dry_run: bool) -> None:
    if dry_run:
        return
    path.write_text(content, encoding="utf-8")


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def normalize_href(href: str, base_file: Path) -> str | None:
    if href.startswith(("http://", "https://", "mailto:", "tel:", "#")):
        return None
    return (base_file.parent / html.unescape(href)).resolve().relative_to(REPO_ROOT).as_posix()


def current_lang_for_path(path: Path) -> str | None:
    rel = repo_rel(path)
    return lang_for_repo_path(rel)


def lang_for_repo_path(rel: str) -> str | None:
    for lang, directory in TRAVEL_DIRS.items():
        if rel.startswith(directory.as_posix() + "/"):
            return lang
    for lang, directory in TRAVEL_INDEX_DIRS.items():
        if rel.startswith(directory.as_posix() + "/"):
            return lang
    return None


def extract_lang_links(content: str, path: Path) -> dict[str, str]:
    links: dict[str, str] = {}
    for match in re.finditer(
        r'<li[^>]*id="([a-z]{2})page"[^>]*>.*?<a[^>]*href="([^"]+)"',
        content,
        flags=re.DOTALL,
    ):
        lang, href = match.groups()
        normalized = normalize_href(href, path)
        if normalized:
            actual_lang = lang_for_repo_path(normalized)
            if actual_lang and actual_lang != lang:
                continue
            links[lang] = normalized

    current_lang = current_lang_for_path(path)
    if current_lang:
        links[current_lang] = repo_rel(path)
    return links


def english_page_path(slug: str) -> str:
    directory = TRAVEL_INDEX_DIRS["en"] if slug in EN_TRAVEL_PAGES else TRAVEL_DIRS["en"]
    return (directory / f"{slug}.html").as_posix()


def translated_page_path(slug: str, lang: str) -> str:
    if lang == "en":
        return english_page_path(slug)
    translated_slug = PAGE_SLUG_TRANSLATIONS[slug][lang]
    return (TRAVEL_INDEX_DIRS[lang] / f"{translated_slug}.html").as_posix()


def page_translation_groups() -> list[dict[str, str]]:
    groups: list[dict[str, str]] = []
    for slug, translations in PAGE_SLUG_TRANSLATIONS.items():
        group = {"en": english_page_path(slug)}
        group.update(
            {
                lang: translated_page_path(slug, lang)
                for lang in LANGUAGE_ORDER
                if lang != "en" and lang in translations
            }
        )
        groups.append(group)
    return groups


def country_translation_groups() -> list[dict[str, str]]:
    country_dir_slugs = {"en": "countries"} | PAGE_SLUG_TRANSLATIONS["countries"]
    groups: list[dict[str, str]] = []
    for english_name, translations in COUNTRY_NAME_TRANSLATIONS.items():
        names = {"en": english_name} | translations
        group: dict[str, str] = {}
        for lang in LANGUAGE_ORDER:
            directory = TRAVEL_DIRS[lang] / country_dir_slugs[lang]
            path = directory / f"{names[lang]}.html"
            rel = path.as_posix()
            if (REPO_ROOT / rel).exists():
                group[lang] = rel
        if group:
            groups.append(group)
    return groups


def expected_country_translation_groups() -> list[dict[str, str]]:
    country_dir_slugs = {"en": "countries"} | PAGE_SLUG_TRANSLATIONS["countries"]
    groups: list[dict[str, str]] = []
    for english_name, translations in COUNTRY_NAME_TRANSLATIONS.items():
        names = {"en": english_name} | translations
        groups.append(
            {
                lang: (TRAVEL_DIRS[lang] / country_dir_slugs[lang] / f"{names[lang]}.html").as_posix()
                for lang in LANGUAGE_ORDER
            }
        )
    return groups


def expected_translation_groups() -> list[dict[str, str]]:
    return page_translation_groups() + expected_country_translation_groups() + expected_city_translation_groups()


def country_page_path(english_name: str, lang: str) -> str:
    country_dir_slugs = {"en": "countries"} | PAGE_SLUG_TRANSLATIONS["countries"]
    names = {"en": english_name} | COUNTRY_NAME_TRANSLATIONS[english_name]
    return (TRAVEL_DIRS[lang] / country_dir_slugs[lang] / f"{names[lang]}.html").as_posix()


def city_dir_slug(lang: str) -> str:
    return "cities" if lang == "en" else PAGE_SLUG_TRANSLATIONS["cities"][lang]


def city_country_dir_name(english_country: str, lang: str) -> str:
    return english_country if lang == "en" else COUNTRY_NAME_TRANSLATIONS[english_country][lang]


def translated_city_name(city_name: str, lang: str) -> str:
    if lang in INDIC_LANGS:
        return CITY_NAME_TRANSLATIONS.get(city_name, {}).get(lang, city_name)
    return city_name


def translated_city_filename(city_filename: str, lang: str) -> str:
    city_name = Path(city_filename).stem
    translated_name = translated_city_name(city_name, lang)
    return f"{translated_name}.html"


def rewrite_local_city_hrefs(content: str, lang: str) -> str:
    if lang not in INDIC_LANGS:
        return content

    def rewrite(match: re.Match[str]) -> str:
        href = html.unescape(match.group(1))
        if "/" in href or href.startswith(("#", "mailto:", "tel:", "http://", "https://")):
            return match.group(0)
        city_name = Path(href).stem
        if city_name not in CITY_NAME_TRANSLATIONS:
            return match.group(0)
        return f'{match.group(1)[:0]}href="{html.escape(translated_city_filename(href, lang))}"'

    return re.sub(r'href="([^"]+\.html)"', rewrite, content)


def city_page_path(english_country: str, city_filename: str, lang: str, french_path: str | None = None) -> str:
    if lang == "fr" and french_path:
        return french_path
    filename = translated_city_filename(city_filename, lang)
    return (
        TRAVEL_DIRS[lang]
        / city_dir_slug(lang)
        / city_country_dir_name(english_country, lang)
        / filename
    ).as_posix()


def first_image_src(path: Path) -> str:
    match = re.search(r'<img\b[^>]*\bsrc="([^"]+)"', read_text(path), flags=re.DOTALL)
    return html.unescape(match.group(1)) if match else ""


def french_city_pages_by_image() -> dict[str, str]:
    french_pages: dict[str, str] = {}
    french_root = REPO_ROOT / TRAVEL_DIRS["fr"] / city_dir_slug("fr")
    if not french_root.exists():
        return french_pages
    for path in french_root.glob("*/*.html"):
        image_src = first_image_src(path)
        if image_src:
            french_pages[image_src] = repo_rel(path)
    return french_pages


def expected_city_translation_groups() -> list[dict[str, str]]:
    french_pages = french_city_pages_by_image()
    groups: list[dict[str, str]] = []
    english_root = REPO_ROOT / TRAVEL_DIRS["en"] / city_dir_slug("en")
    if not english_root.exists():
        return groups
    for source_path in sorted(english_root.glob("*/*.html")):
        english_country = source_path.parent.name
        if english_country not in COUNTRY_NAME_TRANSLATIONS:
            continue
        city_filename = source_path.name
        french_path = french_pages.get(first_image_src(source_path)) or FRENCH_CITY_FILENAME_OVERRIDES.get(
            (english_country, city_filename)
        )
        group = {
            lang: city_page_path(english_country, city_filename, lang, french_path)
            for lang in LANGUAGE_ORDER
        }
        groups.append(group)
    return groups


def city_translation_groups() -> list[dict[str, str]]:
    groups: list[dict[str, str]] = []
    for expected_group in expected_city_translation_groups():
        group = {
            lang: target
            for lang, target in expected_group.items()
            if (REPO_ROOT / target).exists()
        }
        if group:
            groups.append(group)
    return groups


def is_country_detail_path(path: Path) -> bool:
    rel = repo_rel(path)
    country_dir_slugs = {"en": "countries"} | PAGE_SLUG_TRANSLATIONS["countries"]
    return any(
        rel.startswith((TRAVEL_DIRS[lang] / country_dir_slugs[lang]).as_posix() + "/")
        for lang in LANGUAGE_ORDER
    )


def is_city_detail_path(path: Path) -> bool:
    rel = repo_rel(path)
    return any(
        rel.startswith((TRAVEL_DIRS[lang] / city_dir_slug(lang)).as_posix() + "/")
        for lang in LANGUAGE_ORDER
    )


def collect_page_groups() -> dict[str, dict[str, str]]:
    groups: list[dict[str, str]] = []
    groups.extend(page_translation_groups())
    groups.extend(country_translation_groups())
    groups.extend(city_translation_groups())
    for manual_group in MANUAL_PAGE_GROUPS:
        groups.append(dict(manual_group))
    for directory in set(TRAVEL_DIRS.values()) | set(TRAVEL_INDEX_DIRS.values()):
        absolute_dir = REPO_ROOT / directory
        if not absolute_dir.exists():
            continue
        for path in absolute_dir.rglob("*.html"):
            links = extract_lang_links(read_text(path), path)
            if not links:
                continue
            current_rel = repo_rel(path)
            current_matches = [
                index
                for index, group in enumerate(groups)
                if current_rel in group.values()
            ]
            matching = current_matches or [
                index
                for index, group in enumerate(groups)
                if set(group.values()) & set(links.values())
            ]
            if not matching:
                groups.append(dict(links))
                continue
            primary = matching[0]
            for lang, target in links.items():
                if current_matches and lang not in groups[primary] and target != current_rel:
                    continue
                groups[primary].setdefault(lang, target)
            for duplicate in reversed(matching[1:]):
                groups[primary].update(groups[duplicate])
                del groups[duplicate]

    groups.extend(page_translation_groups())
    groups.extend(country_translation_groups())
    groups.extend(city_translation_groups())

    keyed: dict[str, dict[str, str]] = {}
    for group in groups:
        key = group.get("en") or group.get("fr") or sorted(group.values())[0]
        keyed.setdefault(key, {}).update(group)
    for group in page_translation_groups() + country_translation_groups() + city_translation_groups():
        key = group.get("en") or group.get("fr") or sorted(group.values())[0]
        keyed[key] = dict(group)
    return keyed


def strip_tags(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    return html.unescape(" ".join(text.split())).strip()


def extract_attr(fragment: str, attr: str) -> str:
    match = re.search(rf'{attr}="([^"]*)"', fragment)
    return html.unescape(match.group(1)) if match else ""


def extract_nav_labels(content: str) -> dict[str, tuple[str, str]]:
    labels: dict[str, tuple[str, str]] = {}
    for match in re.finditer(
        r'<li[^>]*typeof="ListItem"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?'
        r'<span[^>]*property="name"[^>]*>(.*?)</span>',
        content,
        flags=re.DOTALL,
    ):
        href, label = match.groups()
        clean_label = strip_tags(label)
        if clean_label:
            labels[href] = (href, clean_label)
    return labels


def parse_old_page(path: Path, lang: str) -> OldTravelPage:
    content = read_text(path)
    title_match = re.search(r"<title>(.*?)</title>", content, flags=re.DOTALL)
    title = strip_tags(title_match.group(1)) if title_match else ""
    content_match = re.search(
        r'<div class="content">(.*?)(?:</div>\s*<br\s*/?>\s*</div>|</div>\s*</body>)',
        content,
        flags=re.DOTALL,
    )
    if content_match:
        content_html = content_match.group(1).strip()
    else:
        modern_match = re.search(
            r'<section class="main-content">\s*<article class="content-card">\s*(.*?)\s*</article>\s*</section>',
            content,
            flags=re.DOTALL,
        )
        content_html = modern_match.group(1).strip() if modern_match else ""
    content_html = re.sub(r'<section id="langsection">.*?</section>', "", content_html, flags=re.DOTALL).strip()
    content_html = re.sub(r"\s*</div>\s*$", "", content_html).strip()
    body = content_html
    heading_match = re.search(r"<h2[^>]*>(.*?)</h2>", body, flags=re.DOTALL)
    heading = strip_tags(heading_match.group(1)) if heading_match else title.split(":")[1].strip() if ":" in title else title

    sections: list[GallerySection] = []
    current = GallerySection(HIGHLIGHTS.get(lang, "Highlights"))
    for token in re.finditer(r"<h3[^>]*>(.*?)</h3>|<li[^>]*>(.*?)</li>", body, flags=re.DOTALL):
        section_title, item_html = token.groups()
        if section_title is not None:
            if current.items:
                sections.append(current)
            current = GallerySection(strip_tags(section_title))
            continue
        if not item_html:
            continue
        img_match = re.search(r"<img\b[^>]*>", item_html, flags=re.DOTALL)
        if not img_match:
            continue
        img_html = img_match.group(0)
        src = extract_attr(img_html, "src")
        label = strip_tags(item_html[img_match.end() :])
        href_match = re.search(r'<a[^>]*href="([^"]+)"', item_html, flags=re.DOTALL)
        href = html.unescape(href_match.group(1)) if href_match else ""
        alt = extract_attr(img_html, "alt") or label
        if src and label:
            current.items.append(GalleryItem(src, label, href, alt))
    if current.items:
        sections.append(current)

    return OldTravelPage(path, lang, title, heading, extract_nav_labels(content), sections, content_html)


def replace_one(pattern: str, replacement: str, content: str, flags: int = re.DOTALL) -> str:
    return re.sub(pattern, replacement, content, count=1, flags=flags)


def find_card_templates(content: str) -> list[str]:
    matches = re.findall(r"(<article\b.*?</article>)", content, flags=re.DOTALL)
    if not matches:
        raise ValueError("Could not find a gallery card template")
    return matches


def render_card(template: str, item: GalleryItem) -> str:
    card = re.sub(r'(<img\b[^>]*\balt=")[^"]*(")', rf"\g<1>{html.escape(item.image_alt or item.label)}\2", template, count=1)
    card = re.sub(r"(<h4\b[^>]*>)(.*?)(</h4>)", rf"\g<1>{html.escape(item.label)}\3", card, count=1, flags=re.DOTALL)
    return card


def render_gallery(content: str, old_page: OldTravelPage) -> str:
    card_templates = find_card_templates(content)
    card_index = 0
    rendered_sections = []
    for section in old_page.sections:
        cards = []
        for item in section.items:
            template = card_templates[min(card_index, len(card_templates) - 1)]
            cards.append(render_card(template, item))
            card_index += 1
        cards_html = "\n".join(cards)
        rendered_sections.append(
            f'''                <div class="region-section">
                    <h3 class="region-title">{html.escape(section.title)}</h3>
                    <div class="gallery-grid">
{cards_html}
                    </div>
                </div>'''
        )
    gallery_inner = "\n\n".join(rendered_sections)
    return re.sub(
        r'(<section class="[^"]*gallery[^"]*">\s*)(.*?)(\s*</section>\s*<!-- Footer|\s*</section>\s*<footer)',
        lambda m: f"{m.group(1)}\n{gallery_inner}\n\n            {m.group(3).lstrip()}",
        content,
        count=1,
        flags=re.DOTALL,
    )


def source_index_image_map(source_content: str, source_path: Path) -> dict[str, str]:
    source_images: dict[str, str] = {}
    for match in re.finditer(
        r'<a href="([^"]+)" class="gallery-card">.*?<img src="([^"]+)"',
        source_content,
        flags=re.DOTALL,
    ):
        href, src = match.groups()
        normalized = normalize_href(href, source_path)
        if normalized:
            source_images[normalized] = src
    return source_images


def english_equivalent_for(target_path: str, target_lang: str) -> str | None:
    for group in collect_page_groups().values():
        if group.get(target_lang) == target_path:
            return group.get("en")
    return None


def translated_equivalent_for(source_path: str, target_lang: str) -> str | None:
    for group in collect_page_groups().values():
        if group.get("en") == source_path:
            return group.get(target_lang)
    return None


def old_index_labels(old_page: OldTravelPage) -> dict[str, str]:
    labels: dict[str, str] = {}
    for section in old_page.sections:
        for item in section.items:
            target = normalize_href(item.href, old_page.path) if item.href else None
            if target and item.label:
                labels[target] = item.label
    return labels


def old_index_section_titles(old_page: OldTravelPage) -> list[str]:
    if not old_page.sections:
        return [old_page.heading]
    titles = [section.title for section in old_page.sections]
    if old_page.heading:
        titles[0] = old_page.heading
    return titles


def old_index_section_title_map(old_page: OldTravelPage) -> dict[str, str]:
    titles = old_index_section_titles(old_page)

    def title_at(index: int, fallback: str) -> str:
        return titles[index] if index < len(titles) else fallback

    return {
        "Highlights": old_page.heading,
        "World": title_at(1, old_page.heading),
        "Architecture and Infrastructure": title_at(2, old_page.heading),
        "Flora": title_at(4, old_page.heading),
        "Water": title_at(5, old_page.heading),
        "Patterns": title_at(7, old_page.heading),
        "Personal": title_at(9, old_page.heading),
    }


def render_index_card(card_html: str, old_page: OldTravelPage, source_path: Path, labels: dict[str, str]) -> str:
    href = extract_attr(card_html, "href")
    source_target = normalize_href(href, source_path) if href else None
    translated_target = translated_equivalent_for(source_target, old_page.lang) if source_target else None
    label = labels.get(translated_target or "")
    if not label:
        title_match = re.search(r'<h3 class="card-title">(.*?)</h3>', card_html, flags=re.DOTALL)
        label = strip_tags(title_match.group(1)) if title_match else ""

    card = card_html
    if translated_target:
        href = os.path.relpath(REPO_ROOT / translated_target, old_page.path.parent).replace(os.sep, "/")
        card = re.sub(r'(<a\b[^>]*\bhref=")[^"]*(")', rf"\g<1>{html.escape(href)}\2", card, count=1)
    if label:
        escaped_label = html.escape(label)
        card = re.sub(r'(<img\b[^>]*\balt=")[^"]*(")', rf"\g<1>{escaped_label}\2", card, count=1)
        card = re.sub(
            r'(<h3 class="card-title">).*?(</h3>)',
            rf"\g<1>{escaped_label}\2",
            card,
            count=1,
            flags=re.DOTALL,
        )
    return re.sub(
        r'\s*<p class="card-description">.*?</p>',
        "",
        card,
        count=1,
        flags=re.DOTALL,
    )


def render_index_main(content: str, old_page: OldTravelPage, source_path: Path) -> str:
    labels = old_index_labels(old_page)
    section_titles = old_index_section_title_map(old_page)

    def render_section(match: re.Match[str]) -> str:
        section = match.group(0)
        heading_match = re.search(r'<div class="section-header">\s*<h2>(.*?)</h2>\s*</div>', section, flags=re.DOTALL)
        source_heading = strip_tags(heading_match.group(1)) if heading_match else ""
        translated_heading = section_titles.get(source_heading)
        if translated_heading:
            section = re.sub(
                r'(<div class="section-header">\s*<h2>).*?(</h2>\s*</div>)',
                rf"\g<1>{html.escape(translated_heading)}\2",
                section,
                count=1,
                flags=re.DOTALL,
            )
        return re.sub(
            r'<a\b[^>]*\bhref="[^"]+"[^>]*class="gallery-card"[^>]*>.*?</a>',
            lambda card_match: render_index_card(card_match.group(0), old_page, source_path, labels),
            section,
            flags=re.DOTALL,
        )

    return re.sub(
        r'<section class="gallery-section">.*?</section>',
        render_section,
        content,
        flags=re.DOTALL,
    )


def rewrite_linked_image_sources(
    translated_content: str,
    source_content: str,
    source_path: Path,
    translated_path: Path,
    target_lang: str,
) -> str:
    source_images = source_index_image_map(source_content, source_path)
    if not source_images:
        return translated_content

    def replace_item(match: re.Match[str]) -> str:
        item_html = match.group(0)
        href_match = re.search(r'<a[^>]*href="([^"]+)"', item_html)
        if not href_match:
            return item_html
        target = normalize_href(href_match.group(1), translated_path)
        if not target:
            return item_html
        english_target = english_equivalent_for(target, target_lang)
        if not english_target:
            return item_html
        source_src = source_images.get(english_target)
        if not source_src:
            return item_html
        return re.sub(
            r'(<img\b[^>]*\bsrc=")[^"]*(")',
            rf"\g<1>{html.escape(source_src)}\2",
            item_html,
            count=1,
        )

    return re.sub(r"<li\b.*?</li>", replace_item, translated_content, flags=re.DOTALL)


def rewrite_content_image_sources(
    translated_content: str,
    source_content: str,
    source_path: Path,
    translated_path: Path,
    target_lang: str,
) -> str:
    translated_content = rewrite_linked_image_sources(
        translated_content,
        source_content,
        source_path,
        translated_path,
        target_lang,
    )
    source_srcs = re.findall(r'<img\b[^>]*\bsrc="([^"]+)"', source_content)
    if not source_srcs:
        return translated_content

    index = 0

    def replace_src(match: re.Match[str]) -> str:
        nonlocal index
        if index >= len(source_srcs):
            return match.group(0)
        source_src = html.escape(source_srcs[index])
        index += 1
        return f'{match.group(1)}{source_src}{match.group(2)}'

    return re.sub(r'(<img\b[^>]*\bsrc=")[^"]*(")', replace_src, translated_content)


def render_fallback_content(content: str, old_page: OldTravelPage, source_path: Path) -> str:
    translated_content = old_page.content_html or f"<h2>{html.escape(old_page.heading)}</h2>"
    translated_content = rewrite_content_image_sources(
        translated_content,
        content,
        source_path,
        old_page.path,
        old_page.lang,
    )
    fallback = f'''            <section class="main-content">
                <article class="content-card">
{translated_content}
                </article>
            </section>

            '''
    footer_match = re.search(r"(\s*(?:<!-- Footer.*?-->\s*)?<footer\b)", content, flags=re.DOTALL)
    if not footer_match:
        raise ValueError("Could not find footer for fallback content")
    footer_start = footer_match.start(1)
    hero_match = re.search(r'<section class="[^"]*hero[^"]*"[^>]*>.*?</section>', content, flags=re.DOTALL)
    if hero_match:
        return content[: hero_match.end()] + "\n\n" + fallback + content[footer_start:]
    return content[:footer_start] + fallback + content[footer_start:]


def render_langlist(group: dict[str, str], current_lang: str, current_file: Path, class_name: str = "") -> str:
    class_attr = f' class="{class_name}"' if class_name else ""
    lines = [f'                        <ul{class_attr} id="langlist">']
    for lang in LANGUAGE_ORDER:
        target = group.get(lang)
        if not target:
            continue
        href = os.path.relpath(REPO_ROOT / target, current_file.parent).replace(os.sep, "/")
        highlight = ' class="highlight"' if lang == current_lang else ""
        lines.extend(
            [
                f'                            <li{highlight} id="{lang}page" rel="hasPart" resource="#{lang}page">',
                f'                                <span lang="{lang}">',
                f'                                    <a class="langlink" href="{html.escape(href)}" property="url" typeof="WebPage">',
                f'                                        <span property="inLanguage">{LANGUAGE_NAMES[lang]}</span>',
                "                                    </a>",
                "                                </span>",
                "                            </li>",
            ]
        )
    lines.append("                        </ul>")
    return "\n".join(lines)


def replace_langlist(content: str, group: dict[str, str], current_lang: str, current_file: Path) -> str:
    class_name = "lang-list" if is_city_detail_path(current_file) else ""
    rendered = "\n" + render_langlist(group, current_lang, current_file, class_name)
    return replace_one(r'\s*<ul\b([^>]*\s)?id="langlist"[^>]*>.*?</ul>', rendered, content)


def replace_footer_language_block(content: str, group: dict[str, str], current_lang: str, current_file: Path) -> str:
    class_name = "lang-list" if is_city_detail_path(current_file) else ""
    lang_section = f'''                    <!-- Language Section -->
                    <section class="lang-section" id="langsection">
{render_langlist(group, current_lang, current_file, class_name)}
                    </section>'''
    if re.search(r'<section\b[^>]*id="langsection"[^>]*>.*?</section>', content, flags=re.DOTALL):
        return re.sub(
            r'\s*<section\b[^>]*id="langsection"[^>]*>.*?</section>',
            "\n" + lang_section,
            content,
            count=1,
            flags=re.DOTALL,
        )
    if re.search(r'\s*<!-- Language Links -->\s*<div class="footer-languages">.*?</div>', content, flags=re.DOTALL):
        return re.sub(
            r'\s*<!-- Language Links -->\s*<div class="footer-languages">.*?</div>',
            "\n" + lang_section,
            content,
            count=1,
            flags=re.DOTALL,
        )
    if '<p class="footer-credits">' in content:
        return content.replace('                <p class="footer-credits">', lang_section + '\n                <p class="footer-credits">', 1)

    footer_match = re.search(r"<footer\b[^>]*>.*?</footer>", content, flags=re.DOTALL)
    if not footer_match:
        return content
    footer = footer_match.group(0)
    # A few bespoke pages use an English-only button selector. Keep their
    # styled footer container and localized heading, replacing only the links.
    if re.search(r'<div class="language-selector">.*?</div>', footer, flags=re.DOTALL):
        footer = re.sub(
            r'\s*<div class="language-selector">.*?</div>',
            "\n" + render_langlist(group, current_lang, current_file),
            footer,
            count=1,
            flags=re.DOTALL,
        )
        return content[:footer_match.start()] + footer + content[footer_match.end():]

    footer = footer.replace("</footer>", lang_section + "\n        </footer>", 1)
    return content[:footer_match.start()] + footer + content[footer_match.end():]


def move_langlist_into_footer(content: str) -> str:
    """Move an existing language section into the footer without restyling it."""
    footer_match = re.search(r"<footer\b[^>]*>.*?</footer>", content, flags=re.DOTALL)
    if not footer_match or 'id="langlist"' in footer_match.group(0):
        return content

    section_match = re.search(
        r'\s*<section\b[^>]*class="[^"]*language-section[^"]*"[^>]*>.*?'
        r'<ul\b[^>]*id="langlist"[^>]*>.*?</ul>.*?</section>',
        content,
        flags=re.DOTALL,
    )
    if not section_match:
        return content

    section = section_match.group(0).strip()
    without_section = content[:section_match.start()] + content[section_match.end():]
    footer_match = re.search(r"<footer\b[^>]*>.*?</footer>", without_section, flags=re.DOTALL)
    if not footer_match:
        return content
    footer = footer_match.group(0).replace("</footer>", f"    {section}\n        </footer>", 1)
    return without_section[:footer_match.start()] + footer + without_section[footer_match.end():]


def repair_orphan_footer(content: str) -> str:
    """Restore a missing opening footer around an existing footer body."""
    if re.search(r"<footer\b", content) or "</footer>" not in content:
        return content
    marker = re.search(
        r'\s*(?:<!-- Language Section -->\s*)?<section\b[^>]*id="langsection"',
        content,
        flags=re.DOTALL,
    )
    if not marker:
        return content
    opening = '\n            <footer>\n                <div class="footer-content">\n'
    return content[:marker.start()] + opening + content[marker.start():]


COUNTRY_LANGLIST_CSS = '''
            #langlist {
                list-style: none;
                display: flex;
                justify-content: center;
                align-items: center;
                flex-wrap: wrap;
                gap: var(--space-lg, 1rem);
                padding: 0;
                margin: 0;
            }

            #langlist li {
                position: relative;
            }

            #langlist a {
                text-decoration: none;
                color: var(--text-muted, inherit);
                font-size: var(--text-sm, 0.95rem);
                letter-spacing: 0.08em;
                padding: var(--space-sm, 0.5rem) var(--space-md, 1rem);
                border-radius: 8px;
                transition: all 0.3s ease;
                display: block;
                background: rgba(212, 165, 116, 0.06);
                border: 1px solid rgba(212, 165, 116, 0.15);
                white-space: nowrap;
            }

            #langlist a:hover {
                background: rgba(212, 165, 116, 0.12);
                border-color: rgba(212, 165, 116, 0.3);
                color: var(--baltic-deep-amber, currentColor);
                transform: translateY(-2px);
                box-shadow: var(--shadow-sm, 0 4px 12px rgba(0, 0, 0, 0.12));
            }

            #langlist .highlight a {
                background: linear-gradient(135deg, var(--baltic-deep-teal, #0f766e), var(--baltic-amber, #d4a574));
                color: var(--baltic-cream, #fffaf0);
                border-color: var(--baltic-deep-amber, #b7791f);
            }
'''


def ensure_country_langlist_css(content: str) -> str:
    if "#langlist {" in content:
        return content
    if ".lang-list {" in content:
        return content
    if "            .licence {" in content:
        return content.replace("            .licence {", COUNTRY_LANGLIST_CSS + "\n            .licence {", 1)
    return content.replace("        </style>", COUNTRY_LANGLIST_CSS + "\n        </style>", 1)


def update_common_language_bits(content: str, lang: str) -> str:
    content = replace_one(r'<html lang="[^"]+">', f'<html lang="{lang}">', content)
    content = re.sub(
        r'<meta ([^>]*http-equiv="Content-Language"[^>]*)content="[^"]*"([^>]*)/>',
        rf'<meta \1content="{lang}"\2/>',
        content,
        count=1,
    )
    content = re.sub(
        r'<meta ([^>]*content=")[^"]*("[^>]*http-equiv="Content-Language"[^>]*)/>',
        rf'<meta \1{lang}\2/>',
        content,
        count=1,
    )
    return content


def localize_country_page(
    source_html: str,
    english_name: str,
    lang: str,
    target_path: Path,
    group: dict[str, str],
) -> str:
    labels = COUNTRY_PAGE_LABELS[lang]
    country = COUNTRY_NAME_TRANSLATIONS[english_name][lang] if lang != "en" else english_name
    content = update_common_language_bits(source_html, lang)
    content = replace_one(
        r"<title>.*?</title>",
        f"<title>{html.escape(labels['photography'])}: {html.escape(country)} - John Samuel</title>",
        content,
    )
    content = replace_one(
        r'(<p class="site-tagline">).*?(</p>)',
        rf"\g<1>{labels['site_tagline']}\2",
        content,
    )
    home_href = os.path.relpath(REPO_ROOT / lang / "index.html", target_path.parent).replace(os.sep, "/")
    travel_href = os.path.relpath(REPO_ROOT / TRAVEL_INDEX_DIRS[lang] / "index.html", target_path.parent).replace(os.sep, "/")
    content = re.sub(
        r'(<a\b[^>]*\bhref=")[^"]*("[^>]*>\s*<span property="name">)Home(</span>)',
        rf"\g<1>{html.escape(home_href)}\2{html.escape(labels['home'])}\3",
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'(<a\b[^>]*\bhref=")[^"]*("[^>]*>\s*<span property="name">)Travel(</span>)',
        rf"\g<1>{html.escape(travel_href)}\2{html.escape(labels['travel'])}\3",
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = replace_one(
        r'(<h2 class="hero-title">).*?(</h2>)',
        rf"\g<1>{html.escape(country.upper())}\2",
        content,
    )
    content = replace_one(
        r'(<p class="hero-subtitle">).*?(</p>)',
        rf"\g<1>{labels['hero_subtitle']}\2",
        content,
    )
    content = replace_one(
        r'(<h3 class="footer-title">).*?(</h3>)',
        rf"\g<1>{html.escape(labels['footer'].format(country=country))}\2",
        content,
    )
    content = replace_one(
        r'(<p class="footer-credits">© 2025 <strong>John Samuel</strong> - ).*?(</p>)',
        rf"\g<1>{labels['credits']}\2",
        content,
    )

    def rewrite_city_href(match: re.Match[str]) -> str:
        href = html.unescape(match.group(1))
        english_target = (REPO_ROOT / "en/photography/countries" / href).resolve()
        rel = os.path.relpath(english_target, target_path.parent).replace(os.sep, "/")
        return f'{match.group(1)[:0]}href="{html.escape(rel)}"'

    content = re.sub(r'href="(\.\./cities/[^"]+)"', rewrite_city_href, content)
    content = translate_image_descriptions(content, lang)
    content = replace_footer_language_block(content, group, lang, target_path)
    content = ensure_country_langlist_css(content)
    return content


def generate_missing_country_pages(groups: dict[str, dict[str, str]], dry_run: bool) -> list[Path]:
    changed: list[Path] = []
    for english_name in COUNTRY_NAME_TRANSLATIONS:
        source_path = REPO_ROOT / country_page_path(english_name, "en")
        if not source_path.exists():
            continue
        source_html = read_text(source_path)
        group = {
            lang: country_page_path(english_name, lang)
            for lang in LANGUAGE_ORDER
            if (lang == "en" or lang in COUNTRY_NAME_TRANSLATIONS[english_name])
        }
        groups[group["en"]] = group
        for lang in LANGUAGE_ORDER:
            if lang in ("en", "fr"):
                continue
            target = group[lang]
            target_path = REPO_ROOT / target
            if target_path.exists():
                continue
            localized = localize_country_page(source_html, english_name, lang, target_path, group)
            if not dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
            write_text(target_path, localized, dry_run)
            changed.append(target_path)
    return changed


def localize_city_page(
    source_html: str,
    english_country: str,
    city_name: str,
    lang: str,
    target_path: Path,
    group: dict[str, str],
) -> str:
    labels = CITY_PAGE_LABELS[lang]
    country = COUNTRY_NAME_TRANSLATIONS[english_country][lang] if lang != "en" else english_country
    localized_city = translated_city_name(city_name, lang)
    content = update_common_language_bits(source_html, lang)
    content = replace_one(
        r"<title>.*?</title>",
        f"<title>{html.escape(labels['photography'])}: {html.escape(localized_city)} - John Samuel</title>",
        content,
    )
    content = replace_one(
        r'(<p class="site-tagline">).*?(</p>)',
        rf"\g<1>{labels['site_tagline']}\2",
        content,
    )
    home_href = os.path.relpath(REPO_ROOT / lang / "index.html", target_path.parent).replace(os.sep, "/")
    travel_href = os.path.relpath(REPO_ROOT / TRAVEL_INDEX_DIRS[lang] / "index.html", target_path.parent).replace(os.sep, "/")
    country_href = os.path.relpath(REPO_ROOT / country_page_path(english_country, lang), target_path.parent).replace(os.sep, "/")
    content = re.sub(
        r'(<a\b[^>]*\bhref=")[^"]*("[^>]*>\s*<span property="name">)Home(</span>)',
        rf"\g<1>{html.escape(home_href)}\2{html.escape(labels['home'])}\3",
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'(<a\b[^>]*\bhref=")[^"]*("[^>]*>\s*<span property="name">)Travel(</span>)',
        rf"\g<1>{html.escape(travel_href)}\2{html.escape(labels['travel'])}\3",
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'(<a\b[^>]*\bhref=")[^"]*countries/[^"]*("[^>]*>\s*<span property="name">)[^<]*(</span>)',
        rf"\g<1>{html.escape(country_href)}\2{html.escape(country)}\3",
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = replace_one(
        r'(<h2 class="hero-title">).*?(</h2>)',
        rf"\g<1>{html.escape(localized_city)}\2",
        content,
    )
    content = replace_one(
        r'(<p class="hero-subtitle">).*?(</p>)',
        rf"\g<1>{html.escape(localized_city)}, {html.escape(country)}</p>",
        content,
    )
    content = replace_one(
        r'(<h3 class="region-title">).*?(</h3>)',
        rf"\g<1>{html.escape(country)}\2",
        content,
    )
    content = replace_one(
        r'(<h4 class="city-name">).*?(</h4>)',
        rf"\g<1>{html.escape(localized_city)}\2",
        content,
    )
    content = content.replace(f'href="{html.escape(Path(group["en"]).name)}"', f'href="{html.escape(target_path.name)}"')
    content = rewrite_local_city_hrefs(content, lang)
    content = translate_image_descriptions(content, lang)
    content = replace_one(
        r'(<h3 class="footer-title">).*?(</h3>)',
        rf"\g<1>{html.escape(labels['footer'].format(city=localized_city, country=country))}\2",
        content,
    )
    content = replace_one(
        r'(<p class="footer-credits">© 2025 <strong>John Samuel</strong> - ).*?(</p>)',
        rf"\g<1>{labels['credits']}\2",
        content,
    )
    content = replace_footer_language_block(content, group, lang, target_path)
    return content


def city_display_name(city_name: str, lang: str, group: dict[str, str]) -> str:
    if lang == "fr" and group.get("fr"):
        return Path(group["fr"]).stem
    return translated_city_name(city_name, lang)


def update_city_detail_names(
    content: str,
    english_country: str,
    city_name: str,
    lang: str,
    group: dict[str, str],
) -> str:
    labels = CITY_PAGE_LABELS[lang]
    country = COUNTRY_NAME_TRANSLATIONS[english_country][lang] if lang != "en" else english_country
    localized_city = city_display_name(city_name, lang, group)
    content = replace_one(
        r"<title>.*?</title>",
        f"<title>{html.escape(labels['photography'])}: {html.escape(localized_city)} - John Samuel</title>",
        content,
    )
    content = replace_one(
        r'(<h2 class="hero-title">).*?(</h2>)',
        rf"\g<1>{html.escape(localized_city)}\2",
        content,
    )
    content = replace_one(
        r'(<p class="hero-subtitle">).*?(</p>)',
        rf"\g<1>{html.escape(localized_city)}, {html.escape(country)}</p>",
        content,
    )
    content = replace_one(
        r'(<h3 class="region-title">).*?(</h3>)',
        rf"\g<1>{html.escape(country)}\2",
        content,
    )
    content = replace_one(
        r'(<h4 class="city-name">).*?(</h4>)',
        rf"\g<1>{html.escape(localized_city)}\2",
        content,
    )
    return replace_one(
        r'(<h3 class="footer-title">).*?(</h3>)',
        rf"\g<1>{html.escape(labels['footer'].format(city=localized_city, country=country))}\2",
        content,
    )


def generate_missing_city_pages(groups: dict[str, dict[str, str]], dry_run: bool) -> list[Path]:
    changed: list[Path] = []
    for group in expected_city_translation_groups():
        source = group.get("en")
        if not source:
            continue
        source_path = REPO_ROOT / source
        if not source_path.exists():
            continue
        english_country = source_path.parent.name
        city_name = source_path.stem
        source_html = read_text(source_path)
        groups[source] = group
        for lang in LANGUAGE_ORDER:
            if lang in ("en", "fr"):
                continue
            target = group[lang]
            target_path = REPO_ROOT / target
            if target_path.exists():
                continue
            localized = localize_city_page(source_html, english_country, city_name, lang, target_path, group)
            if not dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
            write_text(target_path, localized, dry_run)
            changed.append(target_path)
    return changed


def update_indic_page(source_html: str, old_page: OldTravelPage, group: dict[str, str], source_path: Path) -> str:
    content = update_common_language_bits(source_html, old_page.lang)
    content = replace_one(r"<title>.*?</title>", f"<title>{html.escape(old_page.title)}</title>", content)
    content = replace_one(
        r'<p class="site-tagline">.*?</p>',
        f'<p class="site-tagline">{SITE_TAGLINES[old_page.lang]}</p>',
        content,
    )
    nav_values = list(old_page.nav_labels.values())
    home_label = nav_values[0][1] if nav_values else LANGUAGE_NAMES[old_page.lang]
    research = nav_values[1] if len(nav_values) > 1 else ("../research/research.html", "Research")
    writings = nav_values[3] if len(nav_values) > 3 else ("../writings/index.html", "Writings")
    travel_label = nav_values[-1][1] if nav_values else old_page.heading
    travel_dir = TRAVEL_INDEX_DIRS[old_page.lang].parts[1]
    content = replace_one(r'(<span property="name">)Home(</span>)', rf"\1{home_label}\2", content)
    content = replace_one(r'(<span property="name">)Research(</span>)', rf"\1{research[1]}\2", content)
    content = replace_one(r'(<span property="name">)Writings(</span>)', rf"\1{writings[1]}\2", content)
    content = replace_one(r'(<span property="name">)Travel(</span>)', rf"\1{travel_label}\2", content)
    content = content.replace('../research/research.html', research[0])
    content = content.replace('../writings/index.html', writings[0])
    content = content.replace('../travel/index.html', f'../{travel_dir}/index.html')
    content = re.sub(
        r'<h([12]) class="hero-title">.*?</h\1>',
        lambda m: f'<h{m.group(1)} class="hero-title">{html.escape(old_page.heading)}</h{m.group(1)}>',
        content,
        count=1,
        flags=re.DOTALL,
    )
    content = replace_one(r'\s*<p class="hero-subtitle">.*?</p>', "", content)
    content = replace_one(r'\s*<p class="hero-description">.*?</p>', "", content)
    if repo_rel(source_path) == "en/travel/index.html":
        content = render_index_main(content, old_page, source_path)
    elif old_page.sections:
        try:
            content = render_gallery(content, old_page)
        except ValueError:
            content = render_fallback_content(content, old_page, source_path)
    else:
        content = render_fallback_content(content, old_page, source_path)
    content = replace_one(
        r'(<h3 class="footer-title">).*?(</h3>)',
        rf"\1{FOOTER_TITLES[old_page.lang]}\2",
        content,
    )
    content = replace_one(
        r'(<p class="footer-credits">© 2025 <strong>John Samuel</strong> - ).*?(</p>)',
        rf"\1{SITE_TAGLINES[old_page.lang]}\2",
        content,
    )
    return replace_langlist(content, group, old_page.lang, old_page.path)


def refresh_indic_pages(groups: dict[str, dict[str, str]], dry_run: bool) -> list[Path]:
    changed: list[Path] = []
    for group in groups.values():
        source = group.get("en")
        if not source:
            continue
        source_path = REPO_ROOT / source
        if not source_path.exists():
            continue
        source_html = read_text(source_path)
        for lang in INDIC_LANGS:
            target = group.get(lang)
            if not target:
                continue
            target_path = REPO_ROOT / target
            if not target_path.exists():
                continue
            current_html = read_text(target_path)
            if "#sidebar" not in current_html:
                continue
            old_page = parse_old_page(target_path, lang)
            refreshed = update_indic_page(source_html, old_page, group, source_path)
            if refreshed != current_html:
                write_text(target_path, refreshed, dry_run)
                changed.append(target_path)
    return changed


def refresh_language_selectors(groups: dict[str, dict[str, str]], dry_run: bool) -> list[Path]:
    changed: list[Path] = []
    for group in groups.values():
        for lang in REFRESH_SELECTOR_LANGS:
            target = group.get(lang)
            if not target:
                continue
            path = REPO_ROOT / target
            if not path.exists():
                continue
            content = read_text(path)
            updated = update_common_language_bits(content, lang)
            updated = repair_orphan_footer(updated)
            if is_country_detail_path(path) or is_city_detail_path(path):
                updated = translate_image_descriptions(updated, lang)
            if is_country_detail_path(path):
                updated = ensure_country_langlist_css(updated)
            if is_city_detail_path(path):
                source = group.get("en")
                if source:
                    source_path = Path(source)
                    updated = update_city_detail_names(updated, source_path.parent.name, source_path.stem, lang, group)
                updated = rewrite_local_city_hrefs(updated, lang)
            if 'id="langlist"' in updated:
                updated = replace_langlist(updated, group, lang, path)
                updated = move_langlist_into_footer(updated)
            else:
                updated = replace_footer_language_block(updated, group, lang, path)
            updated = ensure_country_langlist_css(updated)
            if updated != content:
                write_text(path, updated, dry_run)
                changed.append(path)
    return changed


def missing_static_translations(groups: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = {}
    for group in expected_translation_groups():
        source = group.get("en")
        if not source:
            continue
        absent = [lang for lang in LANGUAGE_ORDER if lang not in group or not (REPO_ROOT / group[lang]).exists()]
        if absent:
            missing[source] = absent
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    parser.add_argument(
        "--links-only",
        action="store_true",
        help="Only rebuild travel language selectors and lang metadata",
    )
    parser.add_argument(
        "--skip-country-generation",
        action="store_true",
        help="Do not generate missing translated country detail pages",
    )
    parser.add_argument(
        "--skip-city-generation",
        action="store_true",
        help="Do not generate missing translated city detail pages",
    )
    parser.add_argument(
        "--missing-report",
        action="store_true",
        help="Report missing translated pages from the shared travel mapping",
    )
    args = parser.parse_args()

    groups = collect_page_groups()
    if not groups:
        raise SystemExit("No travel page language groups found")

    changed: list[Path] = []
    if not args.links_only and not args.skip_country_generation:
        changed.extend(generate_missing_country_pages(groups, args.dry_run))
    if not args.links_only and not args.skip_city_generation:
        changed.extend(generate_missing_city_pages(groups, args.dry_run))

    changed.extend(refresh_language_selectors(groups, args.dry_run))
    if not args.links_only:
        changed.extend(refresh_indic_pages(groups, args.dry_run))

    action = "Would update" if args.dry_run else "Updated"
    print(f"{action} {len(set(changed))} travel pages")
    for path in sorted(set(changed)):
        print(f"  {repo_rel(path)}")
    if args.missing_report:
        missing = missing_static_translations(groups)
        if missing:
            print("\nMissing translated equivalents:")
            for source, langs in sorted(missing.items()):
                print(f"  {source}: {', '.join(langs)}")
        else:
            print("\nNo missing translated equivalents found in the shared travel mapping")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
