/* Shared helpers for the IA-DeepLearning interactive demos
 * (pipeline-demo.js, cnn-demo.js). Plain browser JavaScript, no dependencies.
 *
 * The numeric core mirrors demo_pipeline.py (same CNN, STFT, tokeniser), so the
 * browser reproduces the Python results. Load this file before the demo scripts:
 *   <script src=".../demo-core.js" defer></script>
 *   <script src=".../pipeline-demo.js" defer></script>
 * Everything is exposed as window.DLDemo. The language comes from <html lang>.
 */
(function () {
    "use strict";

    // ================================================================ numeric core

    const core = {};

    core.softmax = function (z) {
        const m = Math.max(...z);
        const e = z.map((v) => Math.exp(v - m));
        const s = e.reduce((a, b) => a + b, 0);
        return e.map((v) => v / s);
    };

    core.argmax = (a) => a.reduce((best, v, i) => (v > a[best] ? i : best), 0);

    function matvec(x, W, b) {
        const out = b.slice();
        for (let i = 0; i < x.length; i++) {
            const xi = x[i];
            if (!xi) continue;
            const row = W[i];
            for (let j = 0; j < out.length; j++) out[j] += xi * row[j];
        }
        return out;
    }

    /** Dense softmax classifier, optional ReLU hidden layer (W1/b1), as in demo_pipeline.Dense. */
    core.dense = function (p, x) {
        const h = p.W1 ? matvec(x, p.W1, p.b1).map((v) => (v > 0 ? v : 0)) : x;
        return matvec(h, p.W2, p.b2);
    };

    /** conv 3×3 (padding 1) → ReLU → max-pool 2×2 → dense, as in demo_pipeline.TinyCNN.
     *  Returns every intermediate tensor, channel-last: z and a [S,S,F], pooled [S/2,S/2,F]. */
    core.cnnTrace = function (p, x, S = 16) {
        const F = p.bk.length;
        const H = S / 2;
        const z = new Float64Array(S * S * F);
        const a = new Float64Array(S * S * F);
        for (let y = 0; y < S; y++) {
            for (let xx = 0; xx < S; xx++) {
                for (let f = 0; f < F; f++) {
                    let s = p.bk[f];
                    for (let dy = 0; dy < 3; dy++) {
                        const yy = y + dy - 1;
                        if (yy < 0 || yy >= S) continue;
                        for (let dx = 0; dx < 3; dx++) {
                            const xc = xx + dx - 1;
                            if (xc < 0 || xc >= S) continue;
                            s += x[yy * S + xc] * p.K[dy * 3 + dx][f];
                        }
                    }
                    z[(y * S + xx) * F + f] = s;
                    a[(y * S + xx) * F + f] = s > 0 ? s : 0;
                }
            }
        }
        const pooled = new Float64Array(H * H * F);
        for (let py = 0; py < H; py++) {
            for (let px = 0; px < H; px++) {
                for (let f = 0; f < F; f++) {
                    let m = -Infinity;
                    for (let i = 0; i < 2; i++) {
                        for (let j = 0; j < 2; j++) {
                            m = Math.max(m, a[((2 * py + i) * S + 2 * px + j) * F + f]);
                        }
                    }
                    pooled[(py * H + px) * F + f] = m;
                }
            }
        }
        return { z, a, pooled, logits: matvec(pooled, p.W, p.b), F, S };
    };

    core.cnn = (p, x, S = 16) => core.cnnTrace(p, x, S).logits;

    /** Channel f of a channel-last [n, n, F] tensor, as a flat n×n array. */
    core.channel = function (t, n, F, f) {
        const out = new Float64Array(n * n);
        for (let i = 0; i < n * n; i++) out[i] = t[i * F + f];
        return out;
    };

    /** np.roll on a S×S image. */
    core.roll = function (img, dy, dx, S = 16) {
        const out = new Float64Array(S * S);
        for (let y = 0; y < S; y++) {
            for (let x = 0; x < S; x++) {
                out[(((y + dy) % S + S) % S) * S + (((x + dx) % S + S) % S)] = img[y * S + x];
            }
        }
        return out;
    };

    core.flip = function (img, S = 16) {
        const out = new Float64Array(S * S);
        for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) out[y * S + x] = img[y * S + S - 1 - x];
        return out;
    };

    // --- audio: same STFT as demo_pipeline.spectrogram (Hann 256, hop 128, 32 bands of 4 bins)
    const FRAME = 256, HOP = 128, BANDS = 32, BINS = 128;
    let HANN = null, COS = null, SIN = null;

    function initFFT() {
        if (HANN) return;
        HANN = new Float64Array(FRAME);
        COS = new Float64Array(BINS * FRAME);
        SIN = new Float64Array(BINS * FRAME);
        for (let n = 0; n < FRAME; n++) HANN[n] = 0.5 - 0.5 * Math.cos((2 * Math.PI * n) / (FRAME - 1));
        for (let k = 0; k < BINS; k++) {
            for (let n = 0; n < FRAME; n++) {
                COS[k * FRAME + n] = Math.cos((2 * Math.PI * k * n) / FRAME);
                SIN[k * FRAME + n] = Math.sin((2 * Math.PI * k * n) / FRAME);
            }
        }
    }

    core.spectrogram = function (x) {
        initFFT();
        const T = Math.floor((x.length - FRAME) / HOP) + 1;
        const data = new Float64Array(T * BANDS);
        const frame = new Float64Array(FRAME);
        const acc = new Float64Array(BANDS);
        for (let t = 0; t < T; t++) {
            for (let n = 0; n < FRAME; n++) frame[n] = x[t * HOP + n] * HANN[n];
            acc.fill(0);
            for (let k = 0; k < BINS; k++) {
                let re = 0, im = 0;
                const off = k * FRAME;
                for (let n = 0; n < FRAME; n++) {
                    re += frame[n] * COS[off + n];
                    im += frame[n] * SIN[off + n];
                }
                acc[k >> 2] += Math.sqrt(re * re + im * im);
            }
            for (let b = 0; b < BANDS; b++) data[t * BANDS + b] = Math.log1p(acc[b] / 4);
        }
        return { T, bands: BANDS, data };
    };

    core.audioFeatures = function (spec) {
        const { T, bands, data } = spec;
        const f = new Float64Array(2 * bands);
        for (let b = 0; b < bands; b++) {
            let s = 0;
            for (let t = 0; t < T; t++) s += data[t * bands + b];
            const m = s / T;
            let v = 0;
            for (let t = 0; t < T; t++) v += (data[t * bands + b] - m) ** 2;
            f[b] = m;
            f[bands + b] = Math.sqrt(v / T);
        }
        return f;
    };

    /** numpy's default (linear) percentile. */
    core.percentile = function (values, q) {
        const s = Float64Array.from(values).sort();
        const pos = (s.length - 1) * (q / 100);
        const lo = Math.floor(pos);
        return lo + 1 < s.length ? s[lo] + (pos - lo) * (s[lo + 1] - s[lo]) : s[lo];
    };

    core.rms = (x) => Math.sqrt(x.reduce((a, v) => a + v * v, 0) / x.length);

    /** 8-bit unsigned PCM WAV → samples in [-1, 1], as demo_pipeline.load_wav. */
    core.parseWav = function (buffer) {
        const view = new DataView(buffer);
        let i = 12;
        while (i + 8 <= view.byteLength) {
            const id = String.fromCharCode(view.getUint8(i), view.getUint8(i + 1), view.getUint8(i + 2), view.getUint8(i + 3));
            const size = view.getUint32(i + 4, true);
            if (id === "data") {
                const bytes = new Uint8Array(buffer, i + 8, size);
                return Float64Array.from(bytes, (b) => b / 127.5 - 1);
            }
            i += 8 + size + (size % 2);
        }
        throw new Error("WAV: no data chunk");
    };

    // --- text: same normalisation and tokenisation as demo_pipeline.py
    core.normalise = function (text, lang) {
        let t = text.toLowerCase().replace(/’/g, "'");
        if (lang === "en") t = t.replace(/n't/g, " not");
        else t = t.replace(/(^|[^\p{L}\p{N}_])n'/gu, "$1ne ").replace(/l'/g, "le ");
        return t;
    };

    core.tokenize = (text, lang) => core.normalise(text, lang).match(/[\p{L}\p{N}_]+/gu) || [];

    /** Feature counts {index: count}; unknown features go to index 0, as demo_pipeline.bag. */
    core.bag = function (tokens, vocabIndex, bigrams) {
        const feats = tokens.slice();
        if (bigrams) for (let i = 0; i + 1 < tokens.length; i++) feats.push(tokens[i] + "_" + tokens[i + 1]);
        const counts = new Map();
        for (const f of feats) {
            const idx = vocabIndex.has(f) ? vocabIndex.get(f) : 0;
            counts.set(idx, (counts.get(idx) || 0) + 1);
        }
        return { feats, counts };
    };

    core.linear = function (model, counts) {
        const z = model.b.slice();
        for (const [idx, c] of counts) for (let j = 0; j < z.length; j++) z[j] += c * model.W[idx][j];
        return z;
    };

    core.parseCSV = function (text) {
        const rows = [];
        let row = [], field = "", quoted = false;
        for (let i = 0; i < text.length; i++) {
            const c = text[i];
            if (quoted) {
                if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
                else if (c === '"') quoted = false;
                else field += c;
            } else if (c === '"') quoted = true;
            else if (c === ",") { row.push(field); field = ""; }
            else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
            else if (c !== "\r") field += c;
        }
        if (field || row.length) { row.push(field); rows.push(row); }
        const [head, ...body] = rows;
        return body.map((r) => Object.fromEntries(head.map((k, i) => [k, r[i]])));
    };

    /** Small seeded generator + Gaussian noise, so the drift sliders are reproducible. */
    core.rng = function (seed) {
        let a = seed >>> 0;
        const next = () => {
            a = (a + 0x6d2b79f5) >>> 0;
            let t = a;
            t = Math.imul(t ^ (t >>> 15), t | 1);
            t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
        next.gauss = () => Math.sqrt(-2 * Math.log(1 - next())) * Math.cos(2 * Math.PI * next());
        return next;
    };

    // ================================================================ page helpers

    const SCRIPT = document.currentScript;
    const BASE = new URL(".", SCRIPT.src).href;
    const LANG = (document.documentElement.lang || "fr").toLowerCase().startsWith("en") ? "en" : "fr";
    const tr = (o) => o[LANG];
    const COLON = LANG === "fr" ? " : " : ": ";

    const NAMES = {
        fr: { carre: "carré", mitige: "mitigé", negatif: "négatif", negation: "négation", son_pur: "son pur" },
        en: {
            cercle: "circle", carre: "square", triangle: "triangle", son_pur: "pure tone", glissando: "chirp",
            bips: "beeps", positif: "positive", negatif: "negative", mitige: "mixed", simple: "simple",
            negation: "negation", contraste: "contrast", tous: "all",
        },
    };
    const label = (k) => NAMES[LANG][k] || k;

    const pctFmt = new Intl.NumberFormat(LANG, { style: "percent", maximumFractionDigits: 0 });
    const pct = (v) => pctFmt.format(v);
    const num = (v, d = 2) => new Intl.NumberFormat(LANG, { minimumFractionDigits: d, maximumFractionDigits: d }).format(v);
    const int = (v) => new Intl.NumberFormat(LANG).format(v);
    const bytes = (b) => (b < 2048 ? `${int(b)} ${tr({ fr: "o", en: "B" })}` : `${num(b / 1024, 1)} ${tr({ fr: "Ko", en: "KB" })}`);

    function h(tag, attrs, ...children) {
        const el = document.createElement(tag);
        for (const [k, v] of Object.entries(attrs || {})) {
            if (v === false || v == null) continue;
            if (k === "class") el.className = v;
            else if (k === "html") el.innerHTML = v;
            else if (k === "style") el.style.cssText = v;
            else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
            else el.setAttribute(k, v === true ? "" : v);
        }
        for (const c of children.flat()) {
            if (c == null || c === false) continue;
            el.append(c instanceof Node ? c : document.createTextNode(String(c)));
        }
        return el;
    }

    // ---------------------------------------------------------------- drawing helpers

    const PLASMA = [[13, 8, 135], [126, 3, 168], [204, 71, 120], [248, 149, 64], [240, 249, 33]];

    function plasma(t) {
        t = Math.min(1, Math.max(0, t)) * (PLASMA.length - 1);
        const i = Math.min(PLASMA.length - 2, Math.floor(t));
        const f = t - i;
        return PLASMA[i].map((c, k) => Math.round(c + f * (PLASMA[i + 1][k] - c)));
    }

    /** Paint a w×h array on a canvas; mode "grey" (0–255) or "heat" (min–max → plasma) or "diverging". */
    function paint(canvas, values, w, hgt, mode = "grey", size) {
        canvas.width = w;
        canvas.height = hgt;
        canvas.classList.add("pd-pixels");
        if (size) {
            canvas.style.width = size + "px";
            canvas.style.height = Math.round((size * hgt) / w) + "px";
        }
        const ctx = canvas.getContext("2d");
        const img = ctx.createImageData(w, hgt);
        let lo = Infinity, hi = -Infinity, amax = 0;
        for (const v of values) { lo = Math.min(lo, v); hi = Math.max(hi, v); amax = Math.max(amax, Math.abs(v)); }
        for (let i = 0; i < w * hgt; i++) {
            const v = values[i];
            let rgb;
            if (mode === "grey") { const g = Math.max(0, Math.min(255, Math.round(v))); rgb = [g, g, g]; }
            else if (mode === "heat") rgb = plasma((v - lo) / (hi - lo || 1));
            else {
                const t = v / (amax || 1);
                rgb = t >= 0 ? [255, Math.round(255 * (1 - t)), Math.round(255 * (1 - t))]
                    : [Math.round(255 * (1 + t)), Math.round(255 * (1 + t)), 255];
            }
            img.data.set([...rgb, 255], i * 4);
        }
        ctx.putImageData(img, 0, 0);
        return canvas;
    }

    function stats(pairs) {
        return h("div", { class: "pd-stats" }, pairs.map(([k, v]) => h("div", { class: "pd-stat" }, h("small", {}, k), h("b", {}, v))));
    }

    function box(title, ...children) {
        return h("div", { class: "pd-box" }, title ? h("h4", {}, title) : null, ...children);
    }

    function probBars(classes, probs) {
        const top = core.argmax(probs);
        return h("div", { class: "pd-bars" }, classes.map((c, i) => h("div", { class: "pd-bar" + (i === top ? " pd-top" : "") },
            h("span", {}, label(c)),
            h("div", { class: "pd-bar-track" }, h("div", { class: "pd-bar-fill", style: `width:${(probs[i] * 100).toFixed(1)}%` })),
            h("span", {}, pct(probs[i])))));
    }

    function confusionTable(classes, M) {
        return h("table", { class: "pd-table" },
            h("thead", {}, h("tr", {}, h("th", {}, tr({ fr: "vrai \\ prédit", en: "true \\ predicted" })), classes.map((c) => h("th", {}, label(c))))),
            h("tbody", {}, M.map((row, i) => h("tr", {}, h("th", {}, label(classes[i])),
                row.map((v, j) => h("td", { class: i === j ? "pd-ok" : v ? "pd-flag" : "" }, v))))));
    }

    function lossChart(c, title) {
        const W = 360, H = 170, P = { l: 40, r: 10, t: 12, b: 28 };
        const n = c.train.length;
        const max = Math.max(...c.train, ...c.val) * 1.05;
        const x = (i) => P.l + ((W - P.l - P.r) * i) / Math.max(1, n - 1);
        const y = (v) => P.t + (H - P.t - P.b) * (1 - v / max);
        const path = (arr) => arr.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
        const bx = x(c.best - 1);
        const svg = `<svg class="pd-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${title}">
            <line x1="${P.l}" y1="${H - P.b}" x2="${W - P.r}" y2="${H - P.b}" stroke="#bbb"/>
            <line x1="${P.l}" y1="${P.t}" x2="${P.l}" y2="${H - P.b}" stroke="#bbb"/>
            <text x="${P.l - 4}" y="${P.t + 8}" font-size="10" text-anchor="end" fill="#666">${num(max, 1)}</text>
            <text x="${P.l - 4}" y="${H - P.b}" font-size="10" text-anchor="end" fill="#666">0</text>
            <text x="${W - P.r}" y="${H - 8}" font-size="10" text-anchor="end" fill="#666">${tr({ fr: "époque", en: "epoch" })} ${n}</text>
            <text x="${P.l}" y="${H - 8}" font-size="10" fill="#666">1</text>
            <line x1="${bx}" y1="${P.t}" x2="${bx}" y2="${H - P.b}" stroke="#2e8b57" stroke-dasharray="4 3"/>
            <text x="${bx > W * 0.7 ? bx - 3 : bx + 3}" y="${P.t + 8}" font-size="10" fill="#2e8b57" text-anchor="${bx > W * 0.7 ? "end" : "start"}">${tr({ fr: "meilleure", en: "best" })}${COLON}${c.best}</text>
            <path d="${path(c.train)}" fill="none" stroke="#6b8cff" stroke-width="2"/>
            <path d="${path(c.val)}" fill="none" stroke="#e67e22" stroke-width="2"/>
        </svg>`;
        return box(title, h("div", { html: svg }), h("div", { class: "pd-legend" },
            h("span", {}, h("i", { style: "background:#6b8cff" }), tr({ fr: "perte d'entraînement", en: "training loss" })),
            h("span", {}, h("i", { style: "background:#e67e22" }), tr({ fr: "perte de validation", en: "validation loss" }))));
    }

    function barChart(values, color, caption, hgt = 70) {
        const W = 360, gap = 1, bw = W / values.length;
        const max = Math.max(...values.map(Math.abs)) || 1;
        const bars = values.map((v, i) => {
            const bh = (Math.abs(v) / max) * (hgt - 4);
            return `<rect x="${(i * bw + gap / 2).toFixed(1)}" y="${(hgt - bh).toFixed(1)}" width="${(bw - gap).toFixed(1)}" height="${bh.toFixed(1)}" fill="${v < 0 ? "#e67e22" : color}"/>`;
        }).join("");
        return h("div", {}, h("div", { html: `<svg class="pd-chart" viewBox="0 0 ${W} ${hgt}" aria-hidden="true">${bars}</svg>` }),
            caption ? h("div", { class: "pd-caption" }, caption) : null);
    }

    function arch(parts) {
        const el = h("div", { class: "pd-arch" });
        parts.forEach(([name, shape], i) => {
            if (i) el.append(h("i", {}, "→"));
            el.append(h("span", {}, name, shape ? h("small", {}, shape) : null));
        });
        return el;
    }

    function slider(text, min, max, stepSize, value, fmt, onInput) {
        const out = h("span", {}, fmt(value));
        const id = "pd-s-" + Math.random().toString(36).slice(2);
        const input = h("input", { type: "range", id, min, max, step: stepSize, value });
        input.addEventListener("input", () => { out.textContent = fmt(+input.value); onInput(+input.value); });
        return h("div", { class: "pd-slider" }, h("label", { for: id }, text), input, out);
    }


    // ---------------------------------------------------------------- data files

    async function fetchOk(path) {
        const res = await fetch(BASE + path);
        if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
        return res;
    }

    function loadSprite(path) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                const c = document.createElement("canvas");
                c.width = img.width;
                c.height = img.height;
                const ctx = c.getContext("2d");
                ctx.drawImage(img, 0, 0);
                const rgba = ctx.getImageData(0, 0, img.width, img.height).data;
                const grey = new Uint8Array(img.width * img.height);
                for (let i = 0; i < grey.length; i++) grey[i] = rgba[i * 4];
                resolve({ width: img.width, grey });
            };
            img.onerror = () => reject(new Error(path));
            img.src = BASE + path;
        });
    }

    const wavCache = new Map();
    function loadWav(path) {
        if (!wavCache.has(path)) {
            wavCache.set(path, fetchOk(path).then((r) => r.arrayBuffer()).then(core.parseWav));
        }
        return wavCache.get(path);
    }

    /** The 300 shapes of formes_16x16.png as {label, split, px: Uint8Array(256)}. */
    async function loadShapes() {
        const [rows, sprite] = await Promise.all([
            fetchOk("formes_labels.csv").then((r) => r.text()).then(core.parseCSV),
            loadSprite("formes_16x16.png"),
        ]);
        return rows.map((row) => {
            const px = new Uint8Array(256);
            const r0 = +row.ligne * 16, c0 = +row.colonne * 16;
            for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) px[y * 16 + x] = sprite.grey[(r0 + y) * sprite.width + c0 + x];
            return { label: row.label, split: row.split, px };
        });
    }

    window.DLDemo = {
        core, matvec, BASE, LANG, tr, COLON, label, pct, num, int, bytes, h, plasma, paint, stats, box, probBars,
        confusionTable, lossChart, barChart, arch, slider, fetchOk, loadSprite, loadWav, loadShapes,
    };
})();
