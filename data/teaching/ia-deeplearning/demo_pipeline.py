#!/usr/bin/env python3
"""Run the 10-step deep-learning pipeline on the three teaching datasets (numpy only).

Every step (preprocessing, models, backpropagation, Adam, quantisation, export,
drift monitoring) is written out in numpy so that nothing is a black box.

Usage: python3 data/teaching/ia-deeplearning/demo_pipeline.py [image|audio|texte] [--json]

Exported models (step 09) go to a temporary directory, never into the repository.
With --json, the results of every step and the trained weights are written to
demo_results.json, which the interactive pipeline pages load. Timings are left
out so that the file only changes when the data or the code changes.
"""
import csv
import json
import re
import struct
import sys
import tempfile
import time
import wave
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
ONLY = ARGS[0] if ARGS else None
WRITE_JSON = "--json" in sys.argv
OUT = Path(tempfile.mkdtemp(prefix="demo_pipeline_"))
SPARK = "▁▂▃▄▅▆▇█"
RESULTS = {}


def rec(modality, **values):
    """Record values for demo_results.json."""
    RESULTS.setdefault(modality, {}).update(values)


def tidy(obj, digits=4):
    """numpy → plain JSON values, rounded so the file is stable and small."""
    if isinstance(obj, dict):
        return {str(k): tidy(v, digits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [tidy(v, digits) for v in obj]
    if isinstance(obj, np.ndarray):
        return tidy(obj.tolist(), digits)
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return round(float(obj), digits)
    return obj


def confusion_matrix(y_true, y_pred, n):
    return [[int(((y_true == i) & (y_pred == j)).sum()) for j in range(n)] for i in range(n)]


def step(n, title):
    print(f"\n  ── Étape {n:02d} · {title}")


def say(*lines):
    for line in lines:
        print(f"     {line}")


def spark(values):
    v = np.asarray(values, float)
    if len(v) > 40:  # resample long histories to 40 characters
        v = np.interp(np.linspace(0, len(v) - 1, 40), np.arange(len(v)), v)
    lo, hi = v.min(), v.max()
    idx = ((v - lo) / (hi - lo + 1e-12) * (len(SPARK) - 1)).round().astype(int)
    return "".join(SPARK[i] for i in idx)


def confusion(y_true, y_pred, classes):
    width = max(len(c) for c in classes) + 2
    say("confusion (lignes = vrai, colonnes = prédit)")
    say(" " * width + "".join(f"{c[:8]:>9}" for c in classes))
    for i, c in enumerate(classes):
        say(f"{c:<{width}}" + "".join(f"{int(((y_true == i) & (y_pred == j)).sum()):>9}"
                                       for j in range(len(classes))))


# ------------------------------------------------------------------ models

class Dense:
    """Softmax classifier with an optional ReLU hidden layer."""

    def __init__(self, n_in, n_out, hidden=0, seed=0):
        r = np.random.default_rng(seed)
        if hidden:
            self.p = {"W1": r.normal(0, np.sqrt(2 / n_in), (n_in, hidden)), "b1": np.zeros(hidden),
                      "W2": r.normal(0, np.sqrt(2 / hidden), (hidden, n_out)), "b2": np.zeros(n_out)}
        else:
            self.p = {"W2": r.normal(0, 0.01, (n_in, n_out)), "b2": np.zeros(n_out)}

    def forward(self, X):
        if "W1" in self.p:
            h = np.maximum(0, X @ self.p["W1"] + self.p["b1"])
        else:
            h = X
        return h @ self.p["W2"] + self.p["b2"], (X, h)

    def backward(self, d, cache):
        X, h = cache
        g = {"W2": h.T @ d, "b2": d.sum(0)}
        dh = d @ self.p["W2"].T
        if "W1" in self.p:
            dh = dh * (h > 0)
            g["W1"], g["b1"] = X.T @ dh, dh.sum(0)
            dh = dh @ self.p["W1"].T
        return g, dh  # dh = gradient w.r.t. the input


class TinyCNN:
    """conv 3×3 (F filtres, padding 1) → ReLU → max-pool 2×2 → dense. Input [N,S,S]."""

    def __init__(self, size, n_out, filters=8, seed=0):
        r = np.random.default_rng(seed)
        self.S, self.F = size, filters
        flat = (size // 2) ** 2 * filters
        self.p = {"K": r.normal(0, np.sqrt(2 / 9), (9, filters)), "bk": np.zeros(filters),
                  "W": r.normal(0, np.sqrt(2 / flat), (flat, n_out)), "b": np.zeros(n_out)}

    def patches(self, X):
        P = np.pad(X, ((0, 0), (1, 1), (1, 1)))
        S = self.S
        return np.stack([P[:, dy:dy + S, dx:dx + S] for dy in range(3) for dx in range(3)], -1)

    def forward(self, X):
        N, S, F = len(X), self.S, self.F
        pat = self.patches(X)                                   # [N,S,S,9]
        a = np.maximum(0, pat @ self.p["K"] + self.p["bk"])     # [N,S,S,F]
        blocks = a.reshape(N, S // 2, 2, S // 2, 2, F)
        pooled = blocks.max((2, 4))                             # [N,S/2,S/2,F]
        flat = pooled.reshape(N, -1)
        return flat @ self.p["W"] + self.p["b"], (pat, a, blocks, pooled, flat)

    def backward(self, d, cache):
        pat, a, blocks, pooled, flat = cache
        N, S, F = len(d), self.S, self.F
        g = {"W": flat.T @ d, "b": d.sum(0)}
        dpool = (d @ self.p["W"].T).reshape(pooled.shape)
        mask = blocks == pooled[:, :, None, :, None, :]
        da = (mask * dpool[:, :, None, :, None, :]).reshape(N, S, S, F) * (a > 0)
        g["K"] = pat.reshape(-1, 9).T @ da.reshape(-1, F)
        g["bk"] = da.sum((0, 1, 2))
        dpat = da @ self.p["K"].T                               # [N,S,S,9]
        dX = np.zeros((N, S + 2, S + 2))
        for k, (dy, dx) in enumerate((dy, dx) for dy in range(3) for dx in range(3)):
            dX[:, dy:dy + S, dx:dx + S] += dpat[..., k]
        return g, dX[:, 1:-1, 1:-1]


def softmax(z):
    e = np.exp(z - z.max(1, keepdims=True))
    return e / e.sum(1, keepdims=True)


def loss_and_grad(model, X, y, l2):
    logits, cache = model.forward(X)
    p = softmax(logits)
    loss = -np.log(p[np.arange(len(y)), y] + 1e-12).mean()
    d = p.copy()
    d[np.arange(len(y)), y] -= 1
    g, _ = model.backward(d / len(y), cache)
    for k in g:
        if k.startswith(("W", "K")):
            g[k] += l2 * model.p[k]
    return loss, g


def predict(model, X):
    return model.forward(X)[0].argmax(1)


def train(model, Xtr, ytr, Xva, yva, lr=0.01, epochs=150, batch=32, l2=1e-4, patience=15,
          augment=None, seed=0):
    """Adam + mini-batches + early stopping on the validation loss (best weights restored)."""
    r = np.random.default_rng(seed)
    m = {k: np.zeros_like(v) for k, v in model.p.items()}
    v2 = {k: np.zeros_like(v) for k, v in model.p.items()}
    t, best, best_p, wait, hist = 0, np.inf, None, 0, {"train": [], "val": []}
    for epoch in range(epochs):
        order = r.permutation(len(Xtr))
        losses = []
        for i in range(0, len(order), batch):
            idx = order[i:i + batch]
            xb = augment(Xtr[idx], r) if augment else Xtr[idx]
            loss, g = loss_and_grad(model, xb, ytr[idx], l2)
            losses.append(loss)
            t += 1
            for k in model.p:
                m[k] = 0.9 * m[k] + 0.1 * g[k]
                v2[k] = 0.999 * v2[k] + 0.001 * g[k] ** 2
                model.p[k] -= lr * (m[k] / (1 - 0.9 ** t)) / (np.sqrt(v2[k] / (1 - 0.999 ** t)) + 1e-8)
        val, _ = loss_and_grad(model, Xva, yva, 0)
        hist["train"].append(np.mean(losses))
        hist["val"].append(val)
        if val < best - 1e-4:
            best, best_p, wait = val, {k: v.copy() for k, v in model.p.items()}, 0
        else:
            wait += 1
            if wait >= patience:
                break
    model.p = best_p
    return hist, int(np.argmin(hist["val"])) + 1


def curve(hist, best):
    return {"train": hist["train"], "val": hist["val"], "best": best}


def report_training(hist, best_epoch):
    say(f"perte entraînement {spark(hist['train'])}  {hist['train'][0]:.2f} → {hist['train'][-1]:.3f}",
        f"perte validation   {spark(hist['val'])}  {hist['val'][0]:.2f} → {min(hist['val']):.3f}",
        f"{len(hist['val'])} époques, arrêt anticipé : meilleurs poids à l'époque {best_epoch}")


def quantize(model):
    """int8 symmetric per-tensor quantisation of the weight matrices; returns bytes before/after."""
    before = after = 0
    for k, w in model.p.items():
        before += w.size * 4
        if w.ndim == 2:
            scale = np.abs(w).max() / 127
            model.p[k] = np.round(w / scale).clip(-127, 127) * scale
            after += w.size + 4
        else:
            after += w.size * 4
    return before, after


def n_params(model):
    return sum(v.size for v in model.p.values())


def export(model, extra, path):
    blob = {"poids": {k: np.round(v, 5).tolist() for k, v in model.p.items()}, **extra}
    path.write_text(json.dumps(blob))
    return path.stat().st_size


def split_idx(splits):
    s = np.array(splits)
    return s == "train", s == "val", s == "test"


# ------------------------------------------------------------------ image

def load_png(path):
    data, i, idat = path.read_bytes(), 8, b""
    while i < len(data):
        length = struct.unpack(">I", data[i:i + 4])[0]
        kind = data[i + 4:i + 8]
        if kind == b"IHDR":
            w, h = struct.unpack(">II", data[i + 8:i + 16])
        elif kind == b"IDAT":
            idat += data[i + 8:i + 8 + length]
        i += 12 + length
    return np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, w + 1)[:, 1:]


def ascii_img(a, chars=" .:-=+*#%@"):
    a = (a - a.min()) / (a.max() - a.min() + 1e-12)
    return ["".join(chars[int(v * (len(chars) - 1))] * 2 for v in row) for row in a]


def demo_image():
    print("\n" + "═" * 78 + "\n  🖼️  IMAGE · formes 16×16\n" + "═" * 78)
    rows = list(csv.DictReader(open(DATA / "formes_labels.csv")))
    sheet = load_png(DATA / "formes_16x16.png")
    X = np.array([sheet[int(r["ligne"]) * 16:(int(r["ligne"]) + 1) * 16,
                        int(r["colonne"]) * 16:(int(r["colonne"]) + 1) * 16] for r in rows], float)
    classes = sorted({r["label"] for r in rows})
    y = np.array([classes.index(r["label"]) for r in rows])
    tr, va, te = split_idx([r["split"] for r in rows])

    step(1, "Définition du problème")
    say(f"classification à {len(classes)} classes : {', '.join(classes)}",
        f"métrique : exactitude (classes équilibrées : {dict(Counter(r['label'] for r in rows))})",
        "référence naïve : 33 % (hasard)")

    step(2, "Données et prétraitement")
    say(f"tenseur brut : {X.shape} uint8  → train {tr.sum()} / val {va.sum()} / test {te.sum()}")
    mean, std = X[tr].mean(), X[tr].std()
    say(f"normalisation (statistiques du train uniquement) : moyenne {mean:.1f}, écart-type {std:.1f}")
    Xn = (X - mean) / std
    rec("image", classes=classes, split={"train": tr.sum(), "val": va.sum(), "test": te.sum()},
        mean=mean, std=std, test_indices=np.where(te)[0])

    def shift(xb, r):  # augmentation: random translation of up to ±2 pixels + horizontal flip
        out = np.empty_like(xb)
        for i, img in enumerate(xb):
            img = np.roll(img, tuple(r.integers(-2, 3, 2)), (0, 1))
            out[i] = img[:, ::-1] if r.random() < 0.5 else img
        return out
    say("augmentation : translation aléatoire ±2 px, miroir horizontal")
    say("exemple (triangle, après normalisation) :")
    for line in ascii_img(Xn[np.where(y == classes.index("triangle"))[0][0]]):
        say("   " + line)

    step(3, "Conception du modèle")
    centroids = np.array([Xn[tr & (y == c)].mean(0) for c in range(len(classes))])
    base = ((Xn[te][:, None] - centroids) ** 2).sum((2, 3)).argmin(1)
    say(f"référence : centroïde par classe sur les pixels → {(base == y[te]).mean():.0%} (test)")
    mlp = Dense(256, 3, hidden=32, seed=1)
    cnn = TinyCNN(16, 3, filters=8, seed=1)
    rec("image", baseline=(base == y[te]).mean(), params={"mlp": n_params(mlp), "cnn": n_params(cnn)})
    say(f"modèle A · MLP 256 → 32 → 3            {n_params(mlp):>6} paramètres",
        f"modèle B · CNN conv3×3(8) → pool → 3     {n_params(cnn):>6} paramètres")

    step(4, "Compilation")
    say("perte : entropie croisée · optimiseur : Adam (lr 0,01) · L2 1e-4 · lots de 32",
        "callback : arrêt anticipé (patience 15) sur la perte de validation")

    step(5, "Entraînement")
    flat = lambda a: a.reshape(len(a), -1)
    say("modèle A · MLP (sans augmentation)")
    h_mlp = train(mlp, flat(Xn[tr]), y[tr], flat(Xn[va]), y[va])
    report_training(*h_mlp)
    say("modèle B · CNN (avec augmentation)")
    h_cnn = train(cnn, Xn[tr], y[tr], Xn[va], y[va], augment=shift)
    report_training(*h_cnn)
    rec("image", curves={"mlp": curve(*h_mlp), "cnn": curve(*h_cnn)})

    step(6, "Évaluation")
    acc_mlp = (predict(mlp, flat(Xn[te])) == y[te]).mean()
    pred = predict(cnn, Xn[te])
    acc_cnn = (pred == y[te]).mean()
    say(f"exactitude test : centroïde {(base == y[te]).mean():.0%} · MLP {acc_mlp:.0%} · CNN {acc_cnn:.0%}")
    confusion(y[te], pred, classes)
    shifted = np.roll(Xn[te], 3, axis=2)
    say(f"robustesse — test décalé de 3 px : MLP {(predict(mlp, flat(shifted)) == y[te]).mean():.0%}"
        f" · CNN {(predict(cnn, shifted) == y[te]).mean():.0%}")
    rec("image", accuracy={"mlp": acc_mlp, "cnn": acc_cnn}, confusion=confusion_matrix(y[te], pred, 3),
        shifted={"mlp": (predict(mlp, flat(shifted)) == y[te]).mean(),
                 "cnn": (predict(cnn, shifted) == y[te]).mean()},
        mlp_weights=mlp.p)

    step(7, "Explicabilité (carte de saillance |∂score/∂pixel|)")
    i = np.where(te & (y == classes.index("triangle")))[0][0]
    logits, cache = cnn.forward(Xn[i:i + 1])
    d = np.zeros_like(logits)
    d[0, logits.argmax()] = 1
    sal = np.abs(cnn.backward(d, cache)[1][0])
    rec("image", saliency={"index": i, "predicted": classes[logits.argmax()], "map": sal / sal.max()})
    say(f"image test n°{i} (vrai : triangle, prédit : {classes[logits.argmax()]})"
        "   image | saillance")
    for a, b in zip(ascii_img(Xn[i]), ascii_img(sal)):
        say(f"   {a} | {b}")

    step(8, "Optimisation et compression")
    before, after = quantize(cnn)
    acc_q = (predict(cnn, Xn[te]) == y[te]).mean()
    rec("image", quantization={"before": before, "after": after, "accuracy": acc_q}, cnn_weights=cnn.p)
    say(f"quantification int8 : {before / 1024:.1f} Ko → {after / 1024:.1f} Ko"
        f"   exactitude {acc_cnn:.0%} → {acc_q:.0%}")

    step(9, "Déploiement")
    size = export(cnn, {"classes": classes, "moyenne": mean, "ecart_type": std}, OUT / "formes_cnn.json")
    rec("image", export_bytes=size)
    blob = json.loads((OUT / "formes_cnn.json").read_text())
    served = TinyCNN(16, 3)
    served.p = {k: np.array(v) for k, v in blob["poids"].items()}

    def serve(raw):  # raw uint8 16×16 → label, with the preprocessing shipped alongside the weights
        return blob["classes"][predict(served, ((raw - blob["moyenne"]) / blob["ecart_type"])[None])[0]]
    t0 = time.perf_counter()
    answers = [serve(X[k]) for k in np.where(te)[0]]
    ms = (time.perf_counter() - t0) / te.sum() * 1000
    say(f"export JSON (poids + classes + normalisation) : {size / 1024:.1f} Ko",
        f"rechargé et servi : {np.mean([a == classes[k] for a, k in zip(answers, y[te])]):.0%}"
        f" correct, {ms:.2f} ms / image")

    step(10, "Surveillance (dérive)")
    r = np.random.default_rng(7)
    grain = lambda a: np.abs(np.diff(a, axis=2)).mean()  # mean jump between neighbouring pixels
    ref_mean, ref_std, ref_grain = X[tr].mean(), X[tr].std(), grain(X[tr])
    say(f"référence train : moyenne {ref_mean:.0f} · écart-type {ref_std:.0f} · grain {ref_grain:.0f}"
        "  (alerte si écart > 20 %)")
    drift_rows = []
    for key, name, drift in [("normal", "normal", X[te]),
                             ("noisy", "caméra bruitée (σ +60)",
                              np.clip(X[te] + r.normal(0, 60, X[te].shape), 0, 255)),
                             ("dark", "exposition sombre (×0,5)", X[te] * 0.5)]:
        stats = {"moyenne": drift.mean() / ref_mean, "écart-type": drift.std() / ref_std,
                 "grain": grain(drift) / ref_grain}
        flagged = [k for k, v in stats.items() if abs(v - 1) > 0.2]
        acc = np.mean([serve(img) == classes[k] for img, k in zip(drift, y[te])])
        drift_rows.append({"key": key, "mean": stats["moyenne"], "std": stats["écart-type"],
                           "grain": stats["grain"], "flagged": len(flagged) > 0, "accuracy": acc})
        verdict = f"⚠ ALERTE ({', '.join(flagged)})" if flagged else "ok"
        say(f"{name:<26} " + " ".join(f"{k} ×{v:.2f}" for k, v in stats.items())
            + f"  → exactitude {acc:>4.0%}  {verdict}")
    say("sans la statistique de grain, la caméra bruitée passerait inaperçue (dérive silencieuse)")
    rec("image", drift={"reference": {"mean": ref_mean, "std": ref_std, "grain": ref_grain},
                        "rows": drift_rows})


# ------------------------------------------------------------------ audio

def load_wav(path):
    with wave.open(str(path)) as f:
        return np.frombuffer(f.readframes(f.getnframes()), np.uint8) / 127.5 - 1, f.getframerate()


def spectrogram(x, frame=256, hop=128, bands=32):
    frames = np.stack([x[i:i + frame] * np.hanning(frame) for i in range(0, len(x) - frame + 1, hop)])
    mag = np.abs(np.fft.rfft(frames))[:, :bands * 4]               # [T, 128 bins]
    return np.log1p(mag.reshape(len(frames), bands, 4).mean(2))   # [T, 32 bands]


def audio_features(x):
    S = spectrogram(x)
    return np.concatenate([S.mean(0), S.std(0)])


def demo_audio():
    print("\n" + "═" * 78 + "\n  🔊  AUDIO · sons synthétiques\n" + "═" * 78)
    rows = list(csv.DictReader(open(DATA / "sons_labels.csv")))
    waves = [load_wav(DATA / r["fichier"]) for r in rows]
    sr = waves[0][1]
    W = np.array([w for w, _ in waves])
    classes = sorted({r["label"] for r in rows})
    y = np.array([classes.index(r["label"]) for r in rows])
    tr, va, te = split_idx([r["split"] for r in rows])

    step(1, "Définition du problème")
    say(f"classification à {len(classes)} classes : {', '.join(classes)} · métrique : exactitude",
        "contrainte imaginée : détection embarquée, < 1 ms par clip")

    step(2, "Données et prétraitement")
    say(f"forme d'onde : {W.shape} à {sr} Hz ({W.shape[1] / sr:.1f} s)  → "
        f"train {tr.sum()} / val {va.sum()} / test {te.sum()}")
    S = spectrogram(W[0])
    say(f"STFT (fenêtre 256 = 32 ms, pas 128 = 16 ms) → spectrogramme log {S.shape} [trames, bandes]",
        f"caractéristiques : moyenne + écart-type par bande → {audio_features(W[0]).shape}")
    for label in classes:
        S = spectrogram(W[np.where(y == classes.index(label))[0][0]]).T[::-1]
        say(f"{label} (fréquence ↑, temps →) :")
        for line in ascii_img(S[::4])[:8]:
            say("   " + line[::2])

    def augment_wave(x, r):
        return np.roll(x, r.integers(-800, 800)) + r.normal(0, r.uniform(0, 0.1), x.shape)
    r = np.random.default_rng(3)
    Wtr = np.concatenate([W[tr]] + [np.array([augment_wave(x, r) for x in W[tr]]) for _ in range(3)])
    ytr = np.tile(y[tr], 4)
    say(f"augmentation : décalage temporel ±100 ms + bruit → train ×4 = {len(Wtr)} clips")
    F = np.array([audio_features(x) for x in W])
    Ftr = np.array([audio_features(x) for x in Wtr])
    mu, sd = Ftr.mean(0), Ftr.std(0) + 1e-8
    norm = lambda f: (f - mu) / sd
    rec("audio", classes=classes, sample_rate=sr, samples=W.shape[1],
        split={"train": tr.sum(), "val": va.sum(), "test": te.sum()}, augmented=len(Wtr),
        spectrogram_shape=spectrogram(W[0]).shape, mu=mu, sd=sd)

    step(3, "Conception du modèle")
    model = Dense(64, 3, hidden=16, seed=2)
    say(f"MLP 64 → 16 → 3 : {n_params(model)} paramètres (sur caractéristiques spectrales)")
    rec("audio", params=n_params(model))

    step(4, "Compilation")
    say("entropie croisée · Adam (lr 0,01) · L2 1e-4 · arrêt anticipé (patience 15)")

    step(5, "Entraînement")
    h = train(model, norm(Ftr), ytr, norm(F[va]), y[va])
    report_training(*h)
    rec("audio", curve=curve(*h))

    step(6, "Évaluation")
    pred = predict(model, norm(F[te]))
    acc = (pred == y[te]).mean()
    say(f"exactitude test : {acc:.0%}")
    confusion(y[te], pred, classes)
    rec("audio", accuracy=acc, confusion=confusion_matrix(y[te], pred, 3))

    step(7, "Explicabilité (importance des bandes, |∂score/∂caractéristique| moyen)")
    logits, cache = model.forward(norm(F[te]))
    d = np.zeros_like(logits)
    d[np.arange(len(d)), logits.argmax(1)] = 1
    imp = np.abs(model.backward(d, cache)[1]).mean(0)
    hz = (np.arange(32) * 4 + 2) * sr / 256
    rec("audio", importance={"mean": imp[:32] / imp.max(), "std": imp[32:] / imp.max(), "hz": hz})
    say(f"moyenne par bande  {spark(imp[:32])}  (0 → {hz[-1]:.0f} Hz)",
        f"écart-type par bande {spark(imp[32:])}",
        f"bandes les plus utiles : {', '.join(f'{hz[i % 32]:.0f} Hz ({'moy' if i < 32 else 'σ'})' for i in imp.argsort()[::-1][:3])}")

    step(8, "Optimisation et compression")
    before, after = quantize(model)
    say(f"quantification int8 : {before} o → {after} o   exactitude {acc:.0%} → "
        f"{(predict(model, norm(F[te])) == y[te]).mean():.0%}")
    rec("audio", quantization={"before": before, "after": after,
                               "accuracy": (predict(model, norm(F[te])) == y[te]).mean()},
        weights=model.p)

    step(9, "Déploiement")
    size = export(model, {"classes": classes, "mu": mu.tolist(), "sd": sd.tolist()}, OUT / "sons_mlp.json")
    rec("audio", export_bytes=size)

    def serve(x):
        return classes[predict(model, norm(audio_features(x))[None])[0]]
    t0 = time.perf_counter()
    for x in W[te]:
        serve(x)
    say(f"export JSON : {size / 1024:.1f} Ko · inférence (STFT comprise) : "
        f"{(time.perf_counter() - t0) / te.sum() * 1000:.2f} ms / clip")

    step(10, "Surveillance (dérive)")
    r = np.random.default_rng(8)
    rms = lambda w: np.sqrt((w ** 2).mean(1))
    floor = lambda w: np.array([np.percentile(spectrogram(x), 10) for x in w])  # background noise level
    ref = {"énergie": rms(W[tr]), "bruit de fond": floor(W[tr])}
    say("référence train (min–max par clip) : "
        + " · ".join(f"{k} {v.min():.2f}–{v.max():.2f}" for k, v in ref.items()))
    drift_rows = []
    for key, name, drift in [("normal", "normal", W[te]),
                             ("noisy", "micro bruyant (σ 0,4)", W[te] + r.normal(0, 0.4, W[te].shape)),
                             ("quiet", "gain faible (×0,1)", W[te] * 0.1)]:
        stats = {"énergie": np.median(rms(drift)), "bruit de fond": np.median(floor(drift))}
        flagged = [k for k, v in stats.items() if not ref[k].min() <= v <= ref[k].max()]
        acc = np.mean([serve(x) == classes[k] for x, k in zip(drift, y[te])])
        drift_rows.append({"key": key, "energy": stats["énergie"], "floor": stats["bruit de fond"],
                           "flagged": len(flagged) > 0, "accuracy": acc})
        verdict = f"⚠ ALERTE ({', '.join(flagged)})" if flagged else "ok"
        say(f"{name:<24} " + " ".join(f"{k} {v:.2f}" for k, v in stats.items())
            + f"  → exactitude {acc:>4.0%}  {verdict}")
    rec("audio", drift={"reference": {"energy": [ref["énergie"].min(), ref["énergie"].max()],
                                      "floor": [ref["bruit de fond"].min(), ref["bruit de fond"].max()]},
                        "rows": drift_rows})


# ------------------------------------------------------------------ text

def normalise(text, lang):
    text = text.lower().replace("’", "'")
    if lang == "en":
        text = text.replace("n't", " not")
    else:
        text = re.sub(r"\bn'", "ne ", text).replace("l'", "le ")
    return text


def tokenize(text, lang):
    # punctuation is dropped: kept, it creates spurious pairs such as « médiocre_. »
    return re.findall(r"\w+", normalise(text, lang))


def bag(tokens, vocab, bigrams):
    v = np.zeros(len(vocab))
    feats = tokens + ([f"{a}_{b}" for a, b in zip(tokens, tokens[1:])] if bigrams else [])
    for f in feats:
        v[vocab.get(f, 0)] += 1
    return v


def demo_text():
    print("\n" + "═" * 78 + "\n  📝  TEXTE · avis de films (fr + en)\n" + "═" * 78)
    rows = list(csv.DictReader(open(DATA / "avis.csv", encoding="utf-8")))
    classes = ["negatif", "mitige", "positif"]
    y = np.array([classes.index(r["label"]) for r in rows])
    tr, va, te = split_idx([r["split"] for r in rows])
    phen = np.array([r["phenomene"] for r in rows])

    step(1, "Définition du problème")
    say("classification de sentiment à 3 classes, deux langues dans un même modèle",
        f"répartition : {dict(Counter(r['label'] for r in rows))} · métrique : exactitude par phénomène",
        f"référence naïve (classe majoritaire) : {np.mean(y[te] == np.bincount(y[tr]).argmax()):.0%}")
    rec("texte", classes=classes, counts=dict(Counter(r["label"] for r in rows)),
        split={"train": tr.sum(), "val": va.sum(), "test": te.sum()},
        majority=np.mean(y[te] == np.bincount(y[tr]).argmax()))

    step(2, "Données et prétraitement")
    toks = [tokenize(r["texte"], r["langue"]) for r in rows]
    ex = next(i for i, r in enumerate(rows) if r["phenomene"] == "negation" and r["langue"] == "fr")
    say(f"texte       : {rows[ex]['texte']}",
        f"normalisé   : {normalise(rows[ex]['texte'], 'fr')}",
        f"jetons      : {toks[ex]}")
    vocab = {"<inc>": 0}
    for t, keep in zip(toks, tr):
        if keep:
            for w in t:
                vocab.setdefault(w, len(vocab))
    max_len = max(len(t) for t in toks)
    ids = [vocab.get(w, 0) for w in toks[ex]] + [0] * (max_len - len(toks[ex]))
    say(f"vocabulaire (train uniquement) : {len(vocab)} jetons · longueur max {max_len}",
        f"identifiants (complétés) : {ids}  → tenseur [{len(rows)}, {max_len}]")
    rec("texte", example={"text": rows[ex]["texte"], "normalised": normalise(rows[ex]["texte"], "fr"),
                          "tokens": toks[ex], "ids": ids},
        vocab_size=len(vocab), max_len=max_len, n_reviews=len(rows))

    step(3, "Conception du modèle")
    vocab2 = dict(vocab)
    for t, keep in zip(toks, tr):
        if keep:
            for a, b in zip(t, t[1:]):
                vocab2.setdefault(f"{a}_{b}", len(vocab2))
    X1 = np.array([bag(t, vocab, False) for t in toks])
    X2 = np.array([bag(t, vocab2, True) for t in toks])
    m1, m2 = Dense(len(vocab), 3, seed=4), Dense(len(vocab2), 3, seed=4)
    say(f"modèle A · sac de mots (unigrammes) → softmax   {n_params(m1):>5} paramètres",
        f"modèle B · unigrammes + bigrammes  → softmax   {n_params(m2):>5} paramètres",
        "(B voit l'ordre local : « pas_ennuyeux » ≠ « ennuyeux »)")
    rec("texte", params={"A": n_params(m1), "B": n_params(m2)})

    step(4, "Compilation")
    say("entropie croisée · Adam (lr 0,05) · L2 1e-3 · arrêt anticipé (patience 15)")

    step(5, "Entraînement")
    curves = {}
    for name, m, X in [("A", m1, X1), ("B", m2, X2)]:
        say(f"modèle {name}")
        h = train(m, X[tr], y[tr], X[va], y[va], lr=0.05, l2=1e-3)
        report_training(*h)
        curves[name] = curve(*h)
    rec("texte", curves=curves, model_a={"vocab": list(vocab), "W": m1.p["W2"], "b": m1.p["b2"]})

    step(6, "Évaluation (test, par phénomène)")
    pA, pB = predict(m1, X1[te]), predict(m2, X2[te])
    say(f"{'phénomène':<12}{'n':>4}{'A unigr.':>11}{'B +bigr.':>11}")
    table = {}
    for ph in ["simple", "contraste", "negation", "tous"]:
        sel = np.ones(te.sum(), bool) if ph == "tous" else phen[te] == ph
        table[ph] = {"n": sel.sum(), "A": (pA[sel] == y[te][sel]).mean(), "B": (pB[sel] == y[te][sel]).mean()}
        say(f"{ph:<12}{sel.sum():>4}{(pA[sel] == y[te][sel]).mean():>11.0%}{(pB[sel] == y[te][sel]).mean():>11.0%}")
    confusion(y[te], pB, classes)
    rec("texte", phenomena=table, confusion=confusion_matrix(y[te], pB, 3))

    step(7, "Explicabilité (contribution de chaque jeton au score de la classe prédite)")
    inv1 = {i: w for w, i in vocab.items()}
    inv2 = {i: w for w, i in vocab2.items()}
    explained = []
    for i in np.where(te & (phen == "negation"))[0][:2]:
        say(f"« {rows[i]['texte']} »  vrai : {rows[i]['label']}")
        entry = {"text": rows[i]["texte"], "label": rows[i]["label"]}
        for name, m, X, inv in [("A", m1, X1, inv1), ("B", m2, X2, inv2)]:
            c = predict(m, X[i:i + 1])[0]
            contrib = X[i] * m.p["W2"][:, c]
            order = [j for j in np.argsort(-np.abs(contrib)) if X[i, j]]
            top = [f"{inv[j]} {contrib[j]:+.1f}" for j in order[:3]]
            entry[name] = {"predicted": classes[c], "top": [[inv[j], contrib[j]] for j in order[:3]]}
            say(f"   {name} → {classes[c]:<8} principaux jetons : {', '.join(top)}")
        explained.append(entry)
    rec("texte", explained=explained)

    step(8, "Optimisation et compression")
    acc_b = (pB == y[te]).mean()
    keep = np.abs(m2.p["W2"]).max(1) > 0.05 * np.abs(m2.p["W2"]).max()
    m2.p["W2"] = m2.p["W2"] * keep[:, None]
    acc_pruned = (predict(m2, X2[te]) == y[te]).mean()
    before, after = quantize(m2)
    say(f"élagage du vocabulaire : {keep.sum()}/{len(keep)} entrées gardées · "
        f"exactitude {acc_b:.0%} → {acc_pruned:.0%}",
        f"quantification int8 : {before / 1024:.1f} Ko → {after / 1024:.1f} Ko · "
        f"exactitude → {(predict(m2, X2[te]) == y[te]).mean():.0%}")
    rec("texte", pruning={"kept": keep.sum(), "total": len(keep), "before": acc_b, "after": acc_pruned},
        quantization={"before": before, "after": after, "accuracy": (predict(m2, X2[te]) == y[te]).mean()},
        model_b={"vocab": list(vocab2), "W": m2.p["W2"], "b": m2.p["b2"]})

    step(9, "Déploiement")
    size = export(m2, {"classes": classes, "vocabulaire": vocab2}, OUT / "avis_bigrammes.json")

    def serve(text, lang):
        return classes[predict(m2, bag(tokenize(text, lang), vocab2, True)[None])[0]]
    say(f"export JSON (poids + vocabulaire + normalisation à reproduire) : {size / 1024:.1f} Ko")
    rec("texte", export_bytes=size)
    for text, lang in [("La musique n'est pas médiocre.", "fr"), ("The script is superb, but the pacing is dull.", "en")]:
        say(f"API → « {text} » : {serve(text, lang)}")

    step(10, "Surveillance (dérive du vocabulaire)")
    new = [("Le film est génial !", "fr", "positif"), ("La musique est nulle.", "fr", "negatif"),
           ("Un vrai chef-d'œuvre.", "fr", "positif"), ("Le scénario est bof.", "fr", "negatif"),
           ("The film is awesome!", "en", "positif"), ("The acting is cringe.", "en", "negatif"),
           ("Total masterpiece.", "en", "positif"), ("The plot is meh.", "en", "negatif")]
    ref_oov = np.mean([vocab.get(w, 0) == 0 for t in np.array(toks, object)[te] for w in t])
    drift_rows = []
    for key, name, batch in [("test", "avis du test",
                              [(r["texte"], r["langue"], r["label"]) for r, k in zip(rows, te) if k]),
                             ("slang", "nouveaux avis (argot)", new)]:
        oov = np.mean([vocab.get(w, 0) == 0 for t, l, _ in batch for w in tokenize(t, l)])
        acc = np.mean([serve(t, l) == lab for t, l, lab in batch])
        alert = "⚠ ALERTE" if oov > ref_oov + 0.05 else "ok"
        drift_rows.append({"key": key, "oov": oov, "accuracy": acc, "flagged": alert != "ok"})
        say(f"{name:<24} mots inconnus {oov:5.1%} (réf. {ref_oov:.1%}) → {alert:<9} exactitude {acc:.0%}")
    rec("texte", drift={"reference": ref_oov, "rows": drift_rows,
                        "new": [{"text": t, "lang": l, "label": lab, "predicted": serve(t, l)}
                                for t, l, lab in new]})


if __name__ == "__main__":
    if ONLY not in (None, "image", "audio", "texte"):
        sys.exit(__doc__)
    for name, fn in [("image", demo_image), ("audio", demo_audio), ("texte", demo_text)]:
        if ONLY in (None, name):
            fn()
    print(f"\n  modèles exportés dans {OUT}")
    if WRITE_JSON:
        target = DATA / "demo_results.json"
        target.write_text(json.dumps(tidy(RESULTS), ensure_ascii=False, separators=(",", ":")) + "\n",
                          encoding="utf-8")
        print(f"  résultats écrits dans {target} ({target.stat().st_size / 1024:.0f} Ko)")
