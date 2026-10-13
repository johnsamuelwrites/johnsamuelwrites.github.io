#!/usr/bin/env python3
"""Generate the tiny teaching datasets used by the IA-DeepLearning course pages.

Everything is synthetic and deterministic (fixed seeds), needs only numpy and
the standard library, and is written next to this script:

    formes_16x16.png   300 grey 16x16 shapes (cercle, carre, triangle) as one sprite sheet
    formes_labels.csv  label and train/val/test split of each sprite
    sons/*.wav         120 clips of 0.5 s @ 8 kHz (son_pur, glissando, bips)
    sons_labels.csv    label and split of each clip
    avis.csv           500 short film reviews (250 fr + 250 en), positif/negatif/mitige

Run:  python3 data/teaching/ia-deeplearning/generate.py
"""

import csv
import itertools
import struct
import wave
import zlib
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
SEED = 42


def rng_for(name):
    """One independent generator per dataset, so editing one leaves the others unchanged."""
    return np.random.default_rng([SEED, zlib.crc32(name.encode())])


def split_labels(n, rng, val=0.15, test=0.15):
    """Return a shuffled list of 'train'/'val'/'test' of length n."""
    n_val, n_test = round(n * val), round(n * test)
    splits = ["val"] * n_val + ["test"] * n_test + ["train"] * (n - n_val - n_test)
    rng.shuffle(splits)
    return splits


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


# ---------------------------------------------------------------- images

SHAPE_SIZE = 16
SHAPES_PER_CLASS = 100
SHEET_COLUMNS = 30
SHAPE_CLASSES = ["cercle", "carre", "triangle"]
IMAGE_NOISE = 25.0  # std of the Gaussian pixel noise (0-255 scale); raise it to make the task harder


def write_png_grey(path, pixels):
    """Write an 8-bit greyscale PNG with zlib only (no Pillow needed)."""
    height, width = pixels.shape
    raw = b"".join(b"\0" + pixels[y].tobytes() for y in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def shape_mask(label, cx, cy, r, yy, xx):
    if label == "cercle":
        return (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    if label == "carre":
        return (abs(xx - cx) <= r) & (abs(yy - cy) <= r)
    # triangle pointing up: half-width grows from 0 at the apex to r at the base
    return (yy >= cy - r) & (yy <= cy + r) & (abs(xx - cx) <= (yy - (cy - r)) / 2)


def generate_shapes():
    rng = rng_for("formes")
    yy, xx = np.mgrid[0:SHAPE_SIZE, 0:SHAPE_SIZE]
    images, rows = [], []
    for label in SHAPE_CLASSES:
        splits = split_labels(SHAPES_PER_CLASS, rng)
        for i in range(SHAPES_PER_CLASS):
            r = int(rng.integers(3, 7))
            cx, cy = (int(v) for v in rng.integers(r + 1, SHAPE_SIZE - r - 1, 2))
            mask = shape_mask(label, cx, cy, r, yy, xx)
            pixels = mask * 255.0 + rng.normal(0, IMAGE_NOISE, (SHAPE_SIZE, SHAPE_SIZE))
            index = len(images)
            images.append(np.clip(pixels, 0, 255).astype(np.uint8))
            rows.append([index, index // SHEET_COLUMNS, index % SHEET_COLUMNS, label, splits[i]])

    sheet_rows = [np.hstack(images[k:k + SHEET_COLUMNS]) for k in range(0, len(images), SHEET_COLUMNS)]
    write_png_grey(OUT / "formes_16x16.png", np.vstack(sheet_rows))
    write_csv(OUT / "formes_labels.csv", ["index", "ligne", "colonne", "label", "split"], rows)


# ---------------------------------------------------------------- audio

SAMPLE_RATE = 8000
CLIP_SECONDS = 0.5
CLIPS_PER_CLASS = 40


def generate_sounds():
    rng = rng_for("sons")
    n = int(SAMPLE_RATE * CLIP_SECONDS)
    t = np.arange(n) / SAMPLE_RATE

    def son_pur():  # constant frequency: a horizontal line in the spectrogram
        return np.sin(2 * np.pi * rng.uniform(300, 900) * t)

    def glissando():  # linear chirp: a diagonal line
        f0, f1 = rng.uniform(200, 400), rng.uniform(1200, 2000)
        return np.sin(2 * np.pi * (f0 * t + (f1 - f0) * t ** 2 / (2 * t[-1])))

    def bips():  # 2 to 4 short beeps: dashes
        beeps = int(rng.integers(2, 5))
        envelope = np.sin(2 * np.pi * beeps * t / t[-1]) > 0.3
        return envelope * np.sin(2 * np.pi * rng.uniform(500, 1000) * t)

    folder = OUT / "sons"
    folder.mkdir(exist_ok=True)
    rows = []
    for label, make in [("son_pur", son_pur), ("glissando", glissando), ("bips", bips)]:
        splits = split_labels(CLIPS_PER_CLASS, rng)
        for i in range(CLIPS_PER_CLASS):
            signal = make() * rng.uniform(0.4, 0.9) + rng.normal(0, rng.uniform(0.05, 0.35), n)
            samples = ((np.clip(signal, -1, 1) + 1) * 127.5).astype(np.uint8)  # 8-bit WAV is unsigned
            name = f"{label}_{i:02d}.wav"
            with wave.open(str(folder / name), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(1)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(samples.tobytes())
            rows.append([f"sons/{name}", label, splits[i]])
    write_csv(OUT / "sons_labels.csv", ["fichier", "label", "split"], rows)


# ---------------------------------------------------------------- text

REVIEWS_PER_LABEL = {"positif": 90, "negatif": 90, "mitige": 70}  # per language
NEGATION_SHARE = 1 / 3  # of positif and negatif reviews

# French subjects: (capitalised, lower-case, gender/number key)
FR_SUBJECTS = [
    ("Le film", "le film", "m"), ("Le scénario", "le scénario", "m"),
    ("Le rythme", "le rythme", "m"), ("Le casting", "le casting", "m"),
    ("La mise en scène", "la mise en scène", "f"), ("La musique", "la musique", "f"),
    ("La photographie", "la photographie", "f"), ("L'interprétation", "l'interprétation", "f"),
    ("Les dialogues", "les dialogues", "mp"), ("Les décors", "les décors", "mp"),
]
FR_VERB = {"m": ("est", "n'est pas"), "f": ("est", "n'est pas"), "mp": ("sont", "ne sont pas")}
# adjective forms: masculine, feminine, masculine plural
FR_POS = [
    ("magnifique", "magnifique", "magnifiques"), ("excellent", "excellente", "excellents"),
    ("réussi", "réussie", "réussis"), ("brillant", "brillante", "brillants"),
    ("superbe", "superbe", "superbes"), ("remarquable", "remarquable", "remarquables"),
]
FR_NEG = [
    ("décevant", "décevante", "décevants"), ("médiocre", "médiocre", "médiocres"),
    ("raté", "ratée", "ratés"), ("ennuyeux", "ennuyeuse", "ennuyeux"),
    ("faible", "faible", "faibles"), ("banal", "banale", "banals"),
]

EN_SUBJECTS = [
    ("The film", "the film", "s"), ("The script", "the script", "s"),
    ("The pacing", "the pacing", "s"), ("The cast", "the cast", "s"),
    ("The direction", "the direction", "s"), ("The soundtrack", "the soundtrack", "s"),
    ("The cinematography", "the cinematography", "s"), ("The acting", "the acting", "s"),
    ("The dialogues", "the dialogues", "p"), ("The sets", "the sets", "p"),
]
EN_VERB = {"s": ("is", "isn't"), "p": ("are", "aren't")}
EN_POS = ["magnificent", "excellent", "brilliant", "superb", "remarkable", "well made"]
EN_NEG = ["disappointing", "mediocre", "dull", "boring", "weak", "bland"]


def fr_adjective(forms, key):
    return forms[{"m": 0, "f": 1, "mp": 2}[key]]


def fr_clause(subject, forms, negated=False, lower=False):
    cap, low, key = subject
    verb = FR_VERB[key][1 if negated else 0]
    return f"{low if lower else cap} {verb} {fr_adjective(forms, key)}"


def en_clause(subject, adjective, negated=False, lower=False):
    cap, low, key = subject
    verb = EN_VERB[key][1 if negated else 0]
    return f"{low if lower else cap} {verb} {adjective}"


def candidate_reviews(lang):
    """Yield every (texte, label, phenomene, forme) the templates can produce for one language.

    `forme` is the negated adjective form for negation reviews ("" otherwise). Every
    phenomenon shares the same openers and punctuation, so punctuation is not a shortcut.
    """
    if lang == "fr":
        subjects, pos, neg, clause = FR_SUBJECTS, FR_POS, FR_NEG, fr_clause
        wrappers = [("{}.", False), ("{} !", False), ("Franchement, {}.", True), ("Honnêtement, {}.", True)]
        connectors = ["mais", "en revanche"]
        form = lambda subject, adjective: fr_adjective(adjective, subject[2])
    else:
        subjects, pos, neg, clause = EN_SUBJECTS, EN_POS, EN_NEG, en_clause
        wrappers = [("{}.", False), ("{}!", False), ("Honestly, {}.", True), ("Frankly, {}.", True)]
        connectors = ["but", "whereas"]
        form = lambda subject, adjective: adjective

    for template, lower in wrappers:
        for subject in subjects:
            for adjective in pos:
                yield template.format(clause(subject, adjective, lower=lower)), "positif", "simple", ""
            for adjective in neg:
                yield template.format(clause(subject, adjective, lower=lower)), "negatif", "simple", ""
            # negating a word flips the polarity: the classic trap for bag-of-words models
            for adjective in pos:
                yield (template.format(clause(subject, adjective, negated=True, lower=lower)),
                       "negatif", "negation", form(subject, adjective))
            for adjective in neg:
                yield (template.format(clause(subject, adjective, negated=True, lower=lower)),
                       "positif", "negation", form(subject, adjective))

        # "X is good, but Y is bad": both polarities in one review
        for first, second in itertools.permutations(subjects, 2):
            for connector in connectors:
                for good, bad in itertools.product(pos, neg):
                    for a, b in [(good, bad), (bad, good)]:
                        text = (f"{clause(first, a, lower=lower)}, {connector} "
                                f"{clause(second, b, lower=True)}")
                        yield template.format(text), "mitige", "contraste", ""


def pick(pool, n, rng):
    return [pool[i] for i in rng.choice(len(pool), n, replace=False)]


def generate_reviews():
    rng = rng_for("avis")
    rows = []
    for lang in ["fr", "en"]:
        candidates = sorted(set(candidate_reviews(lang)))
        for label, count in REVIEWS_PER_LABEL.items():
            pool = [c for c in candidates if c[1] == label]
            forced = []
            if label != "mitige":
                negations = [c for c in pool if c[2] == "negation"]
                # one review per negated adjective form goes to train, so that a model can
                # learn every "pas + adjectif" pair; the rest are drawn at random
                for form in sorted({c[3] for c in negations}):
                    forced += pick([c for c in negations if c[3] == form], 1, rng)
                rest = [c for c in negations if c not in forced]
                n_neg = round(count * NEGATION_SHARE)
                picked = (forced + pick(rest, n_neg - len(forced), rng)
                          + pick([c for c in pool if c[2] == "simple"], count - n_neg, rng))
            else:
                picked = pick(pool, count, rng)

            splits = split_labels(count, rng)
            for i in range(len(forced)):  # swap forced reviews into train
                if splits[i] != "train":
                    j = next(k for k in range(len(forced), count) if splits[k] == "train")
                    splits[i], splits[j] = splits[j], splits[i]
            for (text, lab, phenomenon, _), split in zip(picked, splits):
                rows.append([text, lang, lab, phenomenon, split])

    order = rng.permutation(len(rows))
    rows = [[k + 1] + rows[i] for k, i in enumerate(order)]
    write_csv(OUT / "avis.csv", ["id", "texte", "langue", "label", "phenomene", "split"], rows)


if __name__ == "__main__":
    generate_shapes()
    generate_sounds()
    generate_reviews()
    print(f"Datasets written to {OUT}")
