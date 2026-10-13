# Teaching datasets: IA et Deep Learning

Three tiny **synthetic** datasets (one per modality) for the IA-DeepLearning
course pages, shared by the French and English versions, plus a numpy-only demo
that runs the 10-step deep-learning pipeline on each of them.

| File | Role |
|---|---|
| [`generate.py`](generate.py) | builds the datasets: no download, fixed seeds, `numpy` + standard library, byte-identical on every run |
| [`demo_pipeline.py`](demo_pipeline.py) | runs steps 01–10 (problem → monitoring) on the three datasets, ≈ 5 s |
| `demo_results.json` | written by `demo_pipeline.py --json`: every step's results + trained weights (≈ 110 KB, stable across runs) |
| [`demo-core.js`](demo-core.js) | shared helpers for both demos: numeric core mirroring `demo_pipeline.py` (CNN, STFT, tokeniser) and drawing helpers, as `window.DLDemo` |
| [`pipeline-demo.js`](pipeline-demo.js), [`pipeline-demo.css`](pipeline-demo.css) | the 10-step pipeline demo embedded in the `pipeline.html` pages |
| [`cnn-demo.js`](cnn-demo.js), [`cnn-demo.css`](cnn-demo.css) | the CNN and layers labs of the `cnn.html` pages (each `<div data-lab="…">` becomes a lab) |

```sh
python3 data/teaching/ia-deeplearning/generate.py
python3 data/teaching/ia-deeplearning/demo_pipeline.py          # or: image | audio | texte
python3 data/teaching/ia-deeplearning/demo_pipeline.py --json   # refresh demo_results.json for the pages
```

All the JavaScript is plain browser JavaScript with no dependencies; load
`demo-core.js` before `pipeline-demo.js` or `cnn-demo.js`. The CNN labs are on
[`fr/…/IA-DeepLearning/cnn.html`](../../../fr/enseignement/cours/2026/IA-DeepLearning/cnn.html)
and
[`en/…/AI-DeepLearning/cnn.html`](../../../en/teaching/courses/2026/AI-DeepLearning/cnn.html).
The pipeline demo is embedded (section "Le pipeline en pratique" / "The Pipeline in
Practice") in
[`fr/enseignement/cours/2026/IA-DeepLearning/pipeline.html`](../../../fr/enseignement/cours/2026/IA-DeepLearning/pipeline.html)
and
[`en/teaching/courses/2026/AI-DeepLearning/pipeline.html`](../../../en/teaching/courses/2026/AI-DeepLearning/pipeline.html):
a `<div id="pipeline-demo">`, the stylesheet and the script. The language
comes from `<html lang>`. The browser reloads the data files and runs the
trained models itself; its numeric core mirrors `demo_pipeline.py`, so it
reproduces the Python accuracies. After changing the data or the demo script,
rerun with `--json`, or the pages will show stale numbers. To preview locally,
serve the repository over HTTP (`python3 -m http.server`): browsers block
`fetch` on `file://` pages.

Each dataset has a `split` column (`train` / `val` / `test`, stratified 70/15/15
per class). Rows are **not** shuffled within the image and audio sets (they are
grouped by class), so shuffling is part of the exercise.

Licence: the data is generated and owned by the author of this site. Nothing is
taken from a third-party dataset.

## 🖼️ `formes_16x16.png` + `formes_labels.csv`: shapes

| | |
|---|---|
| Classes | `cercle` (circle), `carre` (square), `triangle` |
| Size | 3 × 100 images, 16×16, 8-bit grey, Gaussian noise σ = 25 |
| Storage | one 480×160 sprite sheet (30 images per row), 48 KB |
| Columns | `index, ligne, colonne, label, split` |

Image `i` is at pixels `[ligne*16 : ligne*16+16, colonne*16 : colonne*16+16]`.

```python
import csv, matplotlib.pyplot as plt
sheet = (plt.imread("formes_16x16.png") * 255).astype("uint8")   # (160, 480)
rows = list(csv.DictReader(open("formes_labels.csv")))
X = [sheet[int(r["ligne"])*16:(int(r["ligne"])+1)*16,
           int(r["colonne"])*16:(int(r["colonne"])+1)*16] for r in rows]   # 300 × (16, 16)
```

What the demo shows: nearest class centroid **58 %**, MLP **87 %**, small CNN
with shift augmentation **100 %**. With the test images shifted by 3 px, the MLP
drops to 44 % while the CNN stays at 100 % (translation invariance). A noisy
camera drops accuracy to 62 % without changing the mean pixel value, and only a
"grain" statistic catches it.

## 🔊 `sons/*.wav` + `sons_labels.csv`: synthetic sounds

| | |
|---|---|
| Classes | `son_pur` (pure tone 300–900 Hz), `glissando` (rising chirp), `bips` (2–4 beeps) |
| Size | 3 × 40 clips, 0.5 s, 8 kHz, mono, **8-bit unsigned** PCM, 4 KB each (480 KB) |
| Columns | `fichier, label, split` |

Each class has a distinct shape in the spectrogram (horizontal line, diagonal,
dashes), which makes this a good illustration of *waveform → spectrogram →
"image"*. Noise varies from clip to clip (σ 0.05–0.35), so some pure tones get
mistaken for beeps. The demo's small MLP on spectral features reaches **89 %**.

```python
import wave, numpy as np
with wave.open("sons/glissando_00.wav") as f:
    x = np.frombuffer(f.readframes(f.getnframes()), np.uint8) / 127.5 - 1   # [-1, 1], 4000 samples
```

## 📝 `avis.csv`: short film reviews (fr + en)

| | |
|---|---|
| Labels | `positif`, `negatif`, `mitige` (mixed) |
| Size | 500 reviews: 250 `fr` + 250 `en` (90 positif, 90 negatif, 70 mitige each) |
| Columns | `id, texte, langue, label, phenomene, split` |

Generated from templates and a small hand-written vocabulary. The `phenomene`
column tells you which kind of sentence it is, for error analysis:

| `phenomene` | Example | Why it matters |
|---|---|---|
| `simple` | *La musique est superbe.* | baseline case |
| `negation` | *Le film n'est pas ennuyeux.* → `positif` | the polarity word lies: bag-of-words models fail |
| `contraste` | *Le scénario est brillant, mais le rythme est faible.* → `mitige` | both polarities in one review |

Design choices:
- A third of the `positif`/`negatif` reviews are negations.
- Every negated adjective form ("pas ennuyeux", "pas ennuyeuse", …) appears at
  least once in `train`.
- All phenomena share the same openers and punctuation, so a model can't
  shortcut on "!" or ".".

What the demo shows: a bag of words gets **48 %** on negations against **100 %**
once word pairs (`pas_ennuyeux`) are added. A first version that kept
punctuation tokens learnt the spurious pair `médiocre_.`, which is a good
preprocessing discussion. Slang the model has never seen (*génial*, *bof*,
*awesome*) gives 45 % unknown words and 50 % accuracy, a vocabulary drift.

## Tuning the difficulty

All settings are constants at the top of each section of `generate.py`:
`IMAGE_NOISE`, `SHAPES_PER_CLASS`, `SAMPLE_RATE`, `CLIPS_PER_CLASS`,
`REVIEWS_PER_LABEL`, `NEGATION_SHARE`, and the vocabulary lists `FR_POS`,
`FR_NEG`, `EN_POS`, `EN_NEG`. Regenerate after any change, rerun
`demo_pipeline.py` to check the results above, and commit the outputs.
