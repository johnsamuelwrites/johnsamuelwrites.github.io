/* CNN and layers labs, shared by
 *   fr/enseignement/cours/2026/IA-DeepLearning/cnn.html
 *   en/teaching/courses/2026/AI-DeepLearning/cnn.html
 *
 * Every element with a data-lab attribute is filled with an interactive widget:
 *   cnn, convolution, activation, pooling, receptive, dropout, batchnorm, softmax.
 * Uses the 16×16 shapes and the CNN trained by demo_pipeline.py
 * (demo_results.json). Plain browser JavaScript; needs demo-core.js loaded first.
 */
(function () {
    "use strict";

    const { core, matvec, LANG, tr, COLON, label, pct, num, h, plasma, stats, probBars, slider, fetchOk, loadShapes } = window.DLDemo;

    const S = 16;
    const D = {};
    const listeners = {};
    const on = (k, f) => (listeners[k] = listeners[k] || []).push(f);
    const emit = (k, v) => (listeners[k] || []).forEach((f) => f(v));
    const shared = {};

    // ---------------------------------------------------------------- drawing

    /** Draw a w×hh array as coloured cells.
     *  mode: "grey" (0–1), "div" (blue < 0 < red), "heat" (plasma, min–max). */
    function gridCanvas(values, w, hh, opts = {}) {
        const cell = opts.cell || 12;
        const pad = opts.pad || 0;
        const c = opts.canvas || h("canvas");
        c.width = (w + 2 * pad) * cell;
        c.height = (hh + 2 * pad) * cell;
        c.classList.add("cnn-grid");
        const ctx = c.getContext("2d");
        let lo = Infinity, hi = -Infinity, amax = 0;
        for (const v of values) { lo = Math.min(lo, v); hi = Math.max(hi, v); amax = Math.max(amax, Math.abs(v)); }
        if (opts.range) { [lo, hi] = opts.range; amax = Math.max(Math.abs(lo), Math.abs(hi)); }
        const colour = (v) => {
            if (opts.mode === "div") {
                const t = Math.max(-1, Math.min(1, v / (amax || 1)));
                const k = Math.round(255 * (1 - Math.abs(t)));
                return t >= 0 ? `rgb(255,${k},${k})` : `rgb(${k},${k},255)`;
            }
            if (opts.mode === "heat") {
                const [r, g, b] = plasma((v - lo) / (hi - lo || 1));
                return `rgb(${r},${g},${b})`;
            }
            const g = Math.round(255 * Math.max(0, Math.min(1, (v - (opts.range ? lo : 0)) / ((opts.range ? hi - lo : 1) || 1))));
            return `rgb(${g},${g},${g})`;
        };
        if (pad) {
            ctx.fillStyle = "#3a3f4b";
            ctx.fillRect(0, 0, c.width, c.height);
        }
        for (let y = 0; y < hh; y++) {
            for (let x = 0; x < w; x++) {
                ctx.fillStyle = colour(values[y * w + x]);
                ctx.fillRect((x + pad) * cell, (y + pad) * cell, cell, cell);
            }
        }
        if (opts.lines && cell >= 8) {
            ctx.strokeStyle = "rgba(128,128,128,0.25)";
            ctx.lineWidth = 1;
            for (let i = 0; i <= w + 2 * pad; i++) { ctx.beginPath(); ctx.moveTo(i * cell + 0.5, 0); ctx.lineTo(i * cell + 0.5, c.height); ctx.stroke(); }
            for (let i = 0; i <= hh + 2 * pad; i++) { ctx.beginPath(); ctx.moveTo(0, i * cell + 0.5); ctx.lineTo(c.width, i * cell + 0.5); ctx.stroke(); }
        }
        for (const m of opts.marks || []) {
            ctx.strokeStyle = m.color || "#ffb000";
            ctx.lineWidth = m.width || 2;
            ctx.strokeRect(m.x * cell + 1, m.y * cell + 1, m.w * cell - 2, m.h * cell - 2);
        }
        if (opts.size) c.style.width = opts.size + "px";
        return c;
    }

    /** Cell coordinates of a pointer event on a grid canvas. */
    function cellAt(canvas, e, w, hh) {
        const r = canvas.getBoundingClientRect();
        return {
            x: Math.min(w - 1, Math.max(0, Math.floor(((e.clientX - r.left) / r.width) * w))),
            y: Math.min(hh - 1, Math.max(0, Math.floor(((e.clientY - r.top) / r.height) * hh))),
        };
    }

    function figure(canvas, caption) {
        return h("figure", { class: "cnn-figure" }, canvas, h("figcaption", {}, caption));
    }

    function choices(items, current, onPick) {
        const row = h("div", { class: "cnn-choices", role: "group" });
        const draw = (cur) => row.replaceChildren(...items.map(([key, text]) => h("button", {
            type: "button", "aria-pressed": String(key === cur),
            onclick: () => { draw(key); onPick(key); },
        }, text)));
        draw(current);
        return row;
    }

    function histogram(values, bins, range, colour) {
        const [lo, hi] = range;
        const counts = new Array(bins).fill(0);
        for (const v of values) {
            const i = Math.floor(((v - lo) / (hi - lo)) * bins);
            if (i >= 0 && i < bins) counts[i]++;
        }
        const max = Math.max(...counts) || 1;
        const W = 360, H = 90, bw = W / bins;
        const bars = counts.map((n, i) => `<rect x="${(i * bw + 0.5).toFixed(1)}" y="${(H - 14 - ((H - 18) * n) / max).toFixed(1)}" width="${(bw - 1).toFixed(1)}" height="${(((H - 18) * n) / max).toFixed(1)}" fill="${colour}"/>`).join("");
        const zero = lo < 0 && hi > 0 ? `<line x1="${((-lo / (hi - lo)) * W).toFixed(1)}" y1="0" x2="${((-lo / (hi - lo)) * W).toFixed(1)}" y2="${H - 14}" stroke="#999" stroke-dasharray="3 3"/>` : "";
        return h("div", {
            html: `<svg class="pd-chart" viewBox="0 0 ${W} ${H}" aria-hidden="true">${bars}${zero}
                <text x="0" y="${H - 2}" font-size="10" fill="#666">${num(lo, 1)}</text>
                <text x="${W}" y="${H - 2}" font-size="10" fill="#666" text-anchor="end">${num(hi, 1)}</text></svg>`,
        });
    }

    // ---------------------------------------------------------------- data

    const norm01 = (px) => Float64Array.from(px, (v) => v / 255);
    const normCNN = (px) => Float64Array.from(px, (v) => (v - D.r.image.mean) / D.r.image.std);
    const W = () => D.r.image.cnn_weights;

    async function loadAll() {
        const [results, shapes] = await Promise.all([fetchOk("demo_results.json").then((r) => r.json()), loadShapes()]);
        D.r = results;
        D.shapes = shapes;
        const tests = results.image.test_indices.map((i) => shapes[i]);
        D.examples = ["cercle", "carre", "triangle"].flatMap((c) => tests.filter((s) => s.label === c).slice(0, 3));
    }

    function thumbs(current, onPick, list = D.examples) {
        const row = h("div", { class: "cnn-choices cnn-thumbs", role: "group", "aria-label": tr({ fr: "Images", en: "Images" }) });
        const draw = (cur) => row.replaceChildren(...list.map((s, i) => h("button", {
            type: "button", "aria-pressed": String(i === cur), title: label(s.label), "aria-label": label(s.label),
            onclick: () => { draw(i); onPick(i); },
        }, gridCanvas(norm01(s.px), S, S, { cell: 2, size: 34 }))));
        draw(current);
        return row;
    }

    // ================================================================ CNN, end to end

    function labCNN(root) {
        const px = Float64Array.from(D.examples[6].px);
        let erase = false;
        const draw = gridCanvas(norm01(px), S, S, { cell: 18, lines: true });
        draw.classList.add("cnn-draw");
        draw.setAttribute("aria-label", tr({ fr: "Grille de dessin 16×16", en: "16×16 drawing grid" }));
        const flow = h("div", { class: "cnn-flow" });
        const probs = h("div");

        const paintAt = (e) => {
            const { x, y } = cellAt(draw, e, S, S);
            px[y * S + x] = erase ? 0 : 255;
            update();
        };
        let down = false;
        draw.addEventListener("pointerdown", (e) => { down = true; draw.setPointerCapture(e.pointerId); paintAt(e); });
        draw.addEventListener("pointermove", (e) => { if (down) paintAt(e); });
        draw.addEventListener("pointerup", () => { down = false; });
        draw.addEventListener("contextmenu", (e) => e.preventDefault());

        const roll = (dy, dx) => { const r = core.roll(px, dy, dx); px.set(r); update(); };
        const tools = h("div", { class: "cnn-choices" },
            h("button", { type: "button", onclick: () => { px.fill(0); update(); } }, tr({ fr: "Effacer tout", en: "Clear" })),
            h("button", { type: "button", onclick: () => { const rand = core.rng(Math.floor(Math.random() * 1e9)); for (let i = 0; i < px.length; i++) px[i] = Math.min(255, Math.max(0, px[i] + 25 * rand.gauss())); update(); } },
                tr({ fr: "Ajouter du bruit", en: "Add noise" })),
            h("button", { type: "button", "aria-label": tr({ fr: "Décaler à gauche", en: "Shift left" }), onclick: () => roll(0, -1) }, "←"),
            h("button", { type: "button", "aria-label": tr({ fr: "Décaler à droite", en: "Shift right" }), onclick: () => roll(0, 1) }, "→"),
            h("button", { type: "button", "aria-label": tr({ fr: "Décaler en haut", en: "Shift up" }), onclick: () => roll(-1, 0) }, "↑"),
            h("button", { type: "button", "aria-label": tr({ fr: "Décaler en bas", en: "Shift down" }), onclick: () => roll(1, 0) }, "↓"));
        const mode = choices([["pen", tr({ fr: "✏️ Crayon", en: "✏️ Pen" })], ["erase", tr({ fr: "🧽 Gomme", en: "🧽 Eraser" })]], "pen", (k) => { erase = k === "erase"; });

        function update() {
            gridCanvas(norm01(px), S, S, { cell: 18, lines: true, canvas: draw });
            const x = normCNN(px);
            const t = core.cnnTrace(W(), x);
            const p = core.softmax(t.logits);
            probs.replaceChildren(h("h4", {}, tr({ fr: "Prédiction", en: "Prediction" })), probBars(D.r.image.classes, p));
            const F = t.F;
            const maps = (tensor, n, mode, caption) => h("div", { class: "cnn-maps" }, Array.from({ length: F }, (_, f) => h("figure", {},
                gridCanvas(core.channel(tensor, n, F, f), n, n, { cell: n === S ? 4 : 8, mode, range: mode === "heat" ? [0, maxOf(tensor)] : null }), `${caption} ${f + 1}`)));
            const K = W().K;
            flow.replaceChildren(
                h("div", { class: "cnn-flow-step" }, h("h4", {}, tr({ fr: "Entrée normalisée", en: "Normalised input" }), h("code", {}, "[16, 16, 1]")),
                    h("div", { class: "pd-caption" }, `x' = (x − ${num(D.r.image.mean, 1)}) / ${num(D.r.image.std, 1)}`)),
                h("div", { class: "cnn-flow-step" }, h("h4", {}, tr({ fr: "8 filtres appris (3×3)", en: "8 learnt filters (3×3)" }), h("code", {}, "conv2d · 8 × (9 + 1) = 80 param.")),
                    h("div", { class: "cnn-maps" }, K[0].map((_, f) => h("figure", {}, gridCanvas(K.map((row) => row[f]), 3, 3, { cell: 16, mode: "div" }), `${f + 1}`)))),
                h("div", { class: "cnn-flow-step" }, h("h4", {}, tr({ fr: "Cartes de caractéristiques après ReLU", en: "Feature maps after ReLU" }), h("code", {}, "[16, 16, 8]")),
                    maps(t.a, S, "heat", "")),
                h("div", { class: "cnn-flow-step" }, h("h4", {}, tr({ fr: "Après max-pooling 2×2", en: "After 2×2 max-pooling" }), h("code", {}, "[8, 8, 8]")),
                    maps(t.pooled, S / 2, "heat", "")),
                h("div", { class: "cnn-flow-step" }, h("h4", {}, tr({ fr: "Aplatissement", en: "Flatten" }), h("code", {}, "[512]")),
                    (() => { const c = gridCanvas(t.pooled, 64, 8, { cell: 4, mode: "heat" }); c.style.width = "100%"; return c; })(),
                    h("div", { class: "pd-caption" }, tr({ fr: "Les 512 valeurs, rangées 64 par ligne.", en: "The 512 values, 64 per row." }))),
                h("div", { class: "cnn-flow-step" }, h("h4", {}, tr({ fr: "Couche dense → scores", en: "Dense layer → scores" }), h("code", {}, "512 × 3 + 3 = 1 539 param.")),
                    h("div", { class: "pd-caption" }, D.r.image.classes.map((c, i) => `${label(c)}${COLON}${num(t.logits[i])}`).join(" · "))));
            shared.cnn = { px: Float64Array.from(px), trace: t };
            emit("cnn", shared.cnn);
        }

        root.replaceChildren(h("div", { class: "cnn-lab" },
            h("div", { class: "cnn-controls" },
                h("div", {}, h("h4", {}, tr({ fr: "Dessinez une forme (ou choisissez une image de test)", en: "Draw a shape (or pick a test image)" })),
                    thumbs(6, (i) => { px.set(D.examples[i].px); update(); })),
                draw, mode, tools, probs),
            h("div", { class: "cnn-out" }, flow)));
        update();
    }

    function maxOf(a) {
        let m = 0;
        for (const v of a) if (v > m) m = v;
        return m || 1;
    }

    // ================================================================ convolution

    const KERNELS = [
        ["identity", tr({ fr: "Identité", en: "Identity" }), [0, 0, 0, 0, 1, 0, 0, 0, 0]],
        ["blur", tr({ fr: "Flou (moyenne)", en: "Blur (mean)" }), Array(9).fill(1 / 9)],
        ["sobelx", tr({ fr: "Bords verticaux", en: "Vertical edges" }), [-1, 0, 1, -2, 0, 2, -1, 0, 1]],
        ["sobely", tr({ fr: "Bords horizontaux", en: "Horizontal edges" }), [-1, -2, -1, 0, 0, 0, 1, 2, 1]],
        ["diag", tr({ fr: "Diagonale", en: "Diagonal" }), [0, 1, 2, -1, 0, 1, -2, -1, 0]],
        ["laplace", tr({ fr: "Laplacien", en: "Laplacian" }), [0, 1, 0, 1, -4, 1, 0, 1, 0]],
        ["sharpen", tr({ fr: "Netteté", en: "Sharpen" }), [0, -1, 0, -1, 5, -1, 0, -1, 0]],
    ];

    function conv2d(x, k, pad, stride, dil) {
        const span = 2 * dil + 1;
        const O = Math.floor((S + 2 * pad - span) / stride) + 1;
        const out = new Float64Array(O * O);
        for (let oy = 0; oy < O; oy++) {
            for (let ox = 0; ox < O; ox++) {
                const y0 = oy * stride - pad, x0 = ox * stride - pad;
                let s = 0;
                for (let ky = 0; ky < 3; ky++) {
                    for (let kx = 0; kx < 3; kx++) {
                        const yy = y0 + ky * dil, xx = x0 + kx * dil;
                        if (yy >= 0 && yy < S && xx >= 0 && xx < S) s += x[yy * S + xx] * k[ky * 3 + kx];
                    }
                }
                out[oy * O + ox] = s;
            }
        }
        return { out, O };
    }

    function labConvolution(root) {
        const st = { img: 7, kernel: KERNELS[2][2].slice(), kernelKey: "sobelx", pad: 1, stride: 1, dil: 1, oy: 5, ox: 5 };
        const learnt = W().K[0].map((_, f) => [`learnt${f}`, `${tr({ fr: "Filtre appris", en: "Learnt filter" })} ${f + 1}`, W().K.map((row) => row[f])]);
        const all = KERNELS.concat(learnt);
        const inputs = [];
        const kernelGrid = h("div", { class: "cnn-kernel" }, Array.from({ length: 9 }, (_, i) => {
            const inp = h("input", { type: "number", step: "0.1", "aria-label": `k${Math.floor(i / 3) + 1}${(i % 3) + 1}` });
            inp.addEventListener("input", () => { st.kernel[i] = parseFloat(inp.value) || 0; select.value = ""; update(); });
            inputs.push(inp);
            return inp;
        }));
        const select = h("select", { class: "pd-input", "aria-label": tr({ fr: "Noyau", en: "Kernel" }) },
            h("option", { value: "" }, tr({ fr: "— personnalisé —", en: "— custom —" })),
            all.map(([key, name]) => h("option", { value: key, selected: key === st.kernelKey }, name)));
        select.addEventListener("change", () => {
            const k = all.find(([key]) => key === select.value);
            if (k) { st.kernel = k[2].slice(); fillKernel(); update(); }
        });
        const fillKernel = () => inputs.forEach((inp, i) => { inp.value = Math.round(st.kernel[i] * 100) / 100; });

        const inCanvas = h("canvas", { class: "cnn-clickable" });
        const outCanvas = h("canvas", { class: "cnn-clickable" });
        const detail = h("div");
        const shape = h("div", { class: "pd-caption" });
        let timer = null;
        const play = h("button", { type: "button", class: "pd-btn" }, "▶ " + tr({ fr: "Faire glisser le filtre", en: "Slide the filter" }));
        play.addEventListener("click", () => {
            if (timer) { clearInterval(timer); timer = null; play.textContent = "▶ " + tr({ fr: "Faire glisser le filtre", en: "Slide the filter" }); return; }
            st.oy = 0; st.ox = -1;
            play.textContent = "⏸ " + tr({ fr: "Arrêter", en: "Stop" });
            timer = setInterval(() => {
                const O = conv2d(new Float64Array(S * S), st.kernel, st.pad, st.stride, st.dil).O;
                st.ox++;
                if (st.ox >= O) { st.ox = 0; st.oy++; }
                if (st.oy >= O) { st.oy = O - 1; st.ox = O - 1; play.click(); return; }
                update();
            }, 70);
        });

        outCanvas.addEventListener("pointerdown", (e) => {
            const O = conv2d(new Float64Array(S * S), st.kernel, st.pad, st.stride, st.dil).O;
            const { x, y } = cellAt(outCanvas, e, O, O);
            st.ox = x; st.oy = y;
            update();
        });
        inCanvas.addEventListener("pointerdown", (e) => {
            const N = S + 2 * st.pad;
            const { x, y } = cellAt(inCanvas, e, N, N);
            const O = conv2d(new Float64Array(S * S), st.kernel, st.pad, st.stride, st.dil).O;
            st.ox = Math.max(0, Math.min(O - 1, Math.round((x - st.dil) / st.stride)));
            st.oy = Math.max(0, Math.min(O - 1, Math.round((y - st.dil) / st.stride)));
            update();
        });

        function update() {
            const x = norm01(D.examples[st.img].px);
            const { out, O } = conv2d(x, st.kernel, st.pad, st.stride, st.dil);
            st.oy = Math.min(st.oy, O - 1);
            st.ox = Math.min(st.ox, O - 1);
            const y0 = st.oy * st.stride, x0 = st.ox * st.stride;  // in padded coordinates
            const marks = [];
            for (let ky = 0; ky < 3; ky++) for (let kx = 0; kx < 3; kx++) marks.push({ x: x0 + kx * st.dil, y: y0 + ky * st.dil, w: 1, h: 1, color: "#ffb000" });
            gridCanvas(x, S, S, { cell: 14, pad: st.pad, marks, canvas: inCanvas, lines: true });
            const cell = Math.max(8, Math.floor((14 * S) / O));
            gridCanvas(out, O, O, { cell, mode: "div", canvas: outCanvas, lines: true, marks: [{ x: st.ox, y: st.oy, w: 1, h: 1, color: "#111", width: 3 }] });
            const span = 2 * st.dil + 1;
            shape.innerHTML = tr({
                fr: `Taille de sortie = ⌊(N + 2P − K<sub>eff</sub>) / S⌋ + 1 = ⌊(16 + ${2 * st.pad} − ${span}) / ${st.stride}⌋ + 1 = <b>${O}</b>`,
                en: `Output size = ⌊(N + 2P − K<sub>eff</sub>) / S⌋ + 1 = ⌊(16 + ${2 * st.pad} − ${span}) / ${st.stride}⌋ + 1 = <b>${O}</b>`,
            });
            const terms = [];
            let sum = 0;
            for (let ky = 0; ky < 3; ky++) {
                for (let kx = 0; kx < 3; kx++) {
                    const yy = y0 - st.pad + ky * st.dil, xx = x0 - st.pad + kx * st.dil;
                    const v = yy >= 0 && yy < S && xx >= 0 && xx < S ? x[yy * S + xx] : 0;
                    const k = st.kernel[ky * 3 + kx];
                    sum += v * k;
                    terms.push(h("span", {}, `${num(v)}×${num(k)}`));
                }
            }
            detail.replaceChildren(h("h4", {}, tr({ fr: `Calcul de la sortie (${st.oy}, ${st.ox})`, en: `Computing output (${st.oy}, ${st.ox})` })),
                h("div", { class: "cnn-products" }, terms), h("div", { class: "cnn-sum" }, `Σ = ${num(sum, 3)}`));
            shared.conv = { out, O, x, st: { ...st } };
            emit("conv", shared.conv);
        }

        const setting = (title, items, key) => h("div", {}, h("h4", {}, title), choices(items, st[key], (v) => { st[key] = v; update(); }));
        root.replaceChildren(h("div", { class: "cnn-lab" },
            h("div", { class: "cnn-controls" },
                h("div", {}, h("h4", {}, tr({ fr: "Image", en: "Image" })), thumbs(st.img, (i) => { st.img = i; update(); })),
                h("div", {}, h("h4", {}, tr({ fr: "Noyau 3×3 (modifiable)", en: "3×3 kernel (editable)" })), select, h("div", { style: "height:0.5rem" }), kernelGrid),
                setting(tr({ fr: "Remplissage (padding)", en: "Padding" }), [[0, "0 (valid)"], [1, "1 (same)"]], "pad"),
                setting(tr({ fr: "Pas (stride)", en: "Stride" }), [[1, "1"], [2, "2"]], "stride"),
                setting(tr({ fr: "Dilatation", en: "Dilation" }), [[1, "1"], [2, "2"]], "dil")),
            h("div", { class: "cnn-out" },
                h("div", { class: "cnn-figures" },
                    figure(inCanvas, tr({ fr: "Entrée (pixels entre 0 et 1) ; en gris foncé, le remplissage de zéros", en: "Input (pixels between 0 and 1); dark grey: zero padding" })),
                    figure(outCanvas, tr({ fr: "Carte de sortie (rouge > 0, bleu < 0) : cliquez une case", en: "Output map (red > 0, blue < 0): click a cell" }))),
                shape, play, detail)));
        fillKernel();
        update();
    }

    // ================================================================ activation

    const ACTIVATIONS = {
        none: [tr({ fr: "Aucune", en: "None" }), (v) => v],
        relu: ["ReLU", (v) => Math.max(0, v)],
        leaky: [tr({ fr: "Leaky ReLU (0,1)", en: "Leaky ReLU (0.1)" }), (v) => (v > 0 ? v : 0.1 * v)],
        sigmoid: [tr({ fr: "Sigmoïde", en: "Sigmoid" }), (v) => 1 / (1 + Math.exp(-v))],
        tanh: ["tanh", Math.tanh],
        gelu: ["GELU", (v) => 0.5 * v * (1 + Math.tanh(Math.sqrt(2 / Math.PI) * (v + 0.044715 * v ** 3)))],
    };

    function labActivation(root) {
        let fn = "relu";
        const plot = h("div");
        const figs = h("div", { class: "cnn-figures" });
        const info = h("div");
        function update() {
            const c = shared.conv;
            if (!c) return;
            const f = ACTIVATIONS[fn][1];
            const out = c.out.map(f);
            const pts = [];
            for (let i = 0; i <= 120; i++) { const v = -3 + (6 * i) / 120; pts.push([v, f(v)]); }
            const X = (v) => 20 + ((v + 3) / 6) * 320, Y = (v) => 110 - ((v + 1.5) / 4.5) * 100;
            plot.innerHTML = `<svg class="pd-chart" viewBox="0 0 360 120" aria-hidden="true">
                <line x1="20" y1="${Y(0)}" x2="340" y2="${Y(0)}" stroke="#ccc"/><line x1="${X(0)}" y1="5" x2="${X(0)}" y2="115" stroke="#ccc"/>
                <polyline points="${pts.map(([a, b]) => `${X(a).toFixed(1)},${Y(Math.max(-1.5, Math.min(3, b))).toFixed(1)}`).join(" ")}" fill="none" stroke="#2d4a8e" stroke-width="2.5"/>
                <text x="340" y="${Y(0) - 4}" font-size="10" text-anchor="end" fill="#666">x</text></svg>`;
            const cell = Math.max(6, Math.floor((12 * S) / c.O));
            figs.replaceChildren(
                figure(gridCanvas(c.out, c.O, c.O, { cell, mode: "div" }), tr({ fr: "Avant (sortie de la convolution)", en: "Before (convolution output)" })),
                figure(gridCanvas(out, c.O, c.O, { cell, mode: "div" }), `${tr({ fr: "Après", en: "After" })} ${ACTIVATIONS[fn][0]}`));
            const zeros = out.filter((v) => v === 0).length / out.length;
            const neg = c.out.filter((v) => v < 0).length / out.length;
            info.replaceChildren(stats([[tr({ fr: "valeurs < 0 avant", en: "values < 0 before" }), pct(neg)], [tr({ fr: "zéros après", en: "zeros after" }), pct(zeros)],
                [tr({ fr: "plage après", en: "range after" }), `${num(Math.min(...out), 1)} … ${num(Math.max(...out), 1)}`]]));
            shared.act = { out, O: c.O, fn: f };
            emit("act", shared.act);
        }
        root.replaceChildren(h("div", { class: "cnn-lab" },
            h("div", { class: "cnn-controls" }, h("h4", {}, tr({ fr: "Fonction d'activation", en: "Activation function" })),
                choices(Object.entries(ACTIVATIONS).map(([k, [n]]) => [k, n]), fn, (k) => { fn = k; update(); }), plot,
                h("div", { class: "pd-caption" }, tr({ fr: "Entrée : la carte produite par le laboratoire de convolution ci-dessus.", en: "Input: the map produced by the convolution lab above." }))),
            h("div", { class: "cnn-out" }, figs, info)));
        on("conv", update);
        update();
    }

    // ================================================================ pooling

    function pool(map, n, size, kind) {
        const O = Math.floor(n / size);
        const out = new Float64Array(O * O);
        for (let oy = 0; oy < O; oy++) {
            for (let ox = 0; ox < O; ox++) {
                let m = kind === "max" ? -Infinity : 0;
                for (let i = 0; i < size; i++) {
                    for (let j = 0; j < size; j++) {
                        const v = map[(oy * size + i) * n + ox * size + j];
                        m = kind === "max" ? Math.max(m, v) : m + v / (size * size);
                    }
                }
                out[oy * O + ox] = m;
            }
        }
        return { out, O };
    }

    function labPooling(root) {
        let kind = "max", size = 2;
        const figs = h("div", { class: "cnn-figures" });
        const info = h("div");
        function update() {
            const a = shared.act, c = shared.conv;
            if (!a) return;
            const sz = size === "global" ? a.O : size;
            const p = pool(a.out, a.O, sz, kind);
            const cell = Math.max(6, Math.floor((12 * S) / a.O));
            figs.replaceChildren(
                figure(gridCanvas(a.out, a.O, a.O, { cell, mode: "div", lines: true }), `${tr({ fr: "Entrée", en: "Input" })} ${a.O}×${a.O}`),
                figure(gridCanvas(p.out, p.O, p.O, { cell: Math.max(12, Math.floor((cell * a.O) / Math.max(1, p.O) / 1.5)), mode: "div", lines: true, range: [-maxAbs(a.out), maxAbs(a.out)] }),
                    `${kind === "max" ? "Max" : tr({ fr: "Moyenne", en: "Average" })} ${size === "global" ? tr({ fr: "globale", en: "global" }) : `${size}×${size}`} → ${p.O}×${p.O}`));
            // translation test: same pipeline on the image shifted by one pixel
            const shifted = core.roll(c.x, 0, 1);
            const conv = conv2d(shifted, c.st.kernel, c.st.pad, c.st.stride, c.st.dil);
            const actS = conv.out.map(a.fn);
            const pS = pool(actS, conv.O, sz, kind);
            // mean |change| relative to the mean |value|: how much a 1 px shift disturbs the layer
            const change = (u, v) => {
                let d = 0, m = 0;
                u.forEach((val, i) => { d += Math.abs(val - v[i]); m += Math.abs(val); });
                return m ? d / m : 0;
            };
            info.replaceChildren(
                stats([[tr({ fr: "valeurs", en: "values" }), `${a.out.length} → ${p.out.length}`], [tr({ fr: "paramètres", en: "parameters" }), "0"],
                    [tr({ fr: "variation si l'image bouge d'1 px : carte", en: "change after a 1 px shift: map" }), pct(change(a.out, actS))],
                    [tr({ fr: "… après pooling", en: "… after pooling" }), pct(change(p.out, pS.out))]]));
        }
        root.replaceChildren(h("div", { class: "cnn-lab" },
            h("div", { class: "cnn-controls" },
                h("div", {}, h("h4", {}, tr({ fr: "Type", en: "Type" })), choices([["max", "Max"], ["avg", tr({ fr: "Moyenne", en: "Average" })]], kind, (k) => { kind = k; update(); })),
                h("div", {}, h("h4", {}, tr({ fr: "Taille de la fenêtre (= pas)", en: "Window size (= stride)" })),
                    choices([[2, "2×2"], [4, "4×4"], ["global", tr({ fr: "globale", en: "global" })]], size, (k) => { size = k; update(); })),
                h("div", { class: "pd-caption" }, tr({ fr: "Entrée : la carte activée du laboratoire précédent.", en: "Input: the activated map from the previous lab." }))),
            h("div", { class: "cnn-out" }, figs, info)));
        on("act", update);
        update();
    }

    const maxAbs = (a) => a.reduce((m, v) => Math.max(m, Math.abs(v)), 0) || 1;

    // ================================================================ receptive field

    function labReceptive(root) {
        const st = { layers: 2, k: 3, pool: false, cy: 8, cx: 8 };
        const canvas = h("canvas", { class: "cnn-clickable" });
        const table = h("div");
        canvas.addEventListener("pointerdown", (e) => { const { x, y } = cellAt(canvas, e, S, S); st.cx = x; st.cy = y; update(); });
        function update() {
            let r = 1, j = 1;
            const rows = [[tr({ fr: "entrée", en: "input" }), "—", 1, 1]];
            for (let l = 1; l <= st.layers; l++) {
                r += (st.k - 1) * j;
                rows.push([`conv ${st.k}×${st.k} n° ${l}`, 1, j, r]);
                if (st.pool) {
                    r += (2 - 1) * j;
                    j *= 2;
                    rows.push([`max-pool 2×2 n° ${l}`, 2, j, r]);
                }
            }
            const half = Math.floor(r / 2);
            const x0 = Math.max(0, st.cx - half), y0 = Math.max(0, st.cy - half);
            const x1 = Math.min(S, st.cx - half + r), y1 = Math.min(S, st.cy - half + r);
            gridCanvas(norm01(D.examples[4].px), S, S, {
                cell: 16, canvas, lines: true,
                marks: [{ x: x0, y: y0, w: x1 - x0, h: y1 - y0, color: "#ffb000", width: 3 }, { x: st.cx, y: st.cy, w: 1, h: 1, color: "#e74c3c", width: 3 }],
            });
            table.replaceChildren(h("table", { class: "pd-table" },
                h("thead", {}, h("tr", {}, h("th", {}, tr({ fr: "couche", en: "layer" })), h("th", {}, tr({ fr: "pas", en: "stride" })),
                    h("th", {}, tr({ fr: "saut cumulé", en: "cumulative jump" })), h("th", {}, tr({ fr: "champ récepteur", en: "receptive field" })))),
                h("tbody", {}, rows.map(([n, s, jj, rr]) => h("tr", {}, h("td", {}, n), h("td", {}, s), h("td", {}, jj), h("td", {}, `${rr}×${rr}`))))),
                stats([[tr({ fr: "un neurone final voit", en: "one final neuron sees" }), `${r}×${r} px`], [tr({ fr: "soit", en: "i.e." }), pct(Math.min(1, (r * r) / (S * S)))]]));
        }
        root.replaceChildren(h("div", { class: "cnn-lab" },
            h("div", { class: "cnn-controls" },
                slider(tr({ fr: "couches de convolution", en: "convolution layers" }), 1, 4, 1, st.layers, (v) => String(v), (v) => { st.layers = v; update(); }),
                h("div", {}, h("h4", {}, tr({ fr: "Taille du noyau", en: "Kernel size" })), choices([[3, "3×3"], [5, "5×5"]], st.k, (v) => { st.k = v; update(); })),
                h("label", { class: "pd-row", style: "font-size:0.9rem" },
                    h("input", { type: "checkbox", onchange: (e) => { st.pool = e.target.checked; update(); } }),
                    tr({ fr: "max-pooling 2×2 après chaque convolution", en: "2×2 max-pooling after each convolution" })),
                table),
            h("div", { class: "cnn-out" }, figure(canvas, tr({ fr: "Cliquez un pixel : en orange, la zone de l'entrée qui influence le neurone situé à cet endroit", en: "Click a pixel: in orange, the input area that influences the neuron at that position" })))));
        update();
    }

    // ================================================================ dropout

    function labDropout(root) {
        let p = 0.5, seed = 1;
        const maps = h("div", { class: "cnn-maps" });
        const out = h("div");
        function masked(flat, rate, s) {
            const rand = core.rng(s);
            let dropped = 0;
            const out = flat.map((v) => {
                if (rand() < rate) { dropped++; return 0; }
                return v / (1 - rate);
            });
            out.dropped = dropped / flat.length;
            return out;
        }
        function update() {
            const c = shared.cnn;
            if (!c) return;
            const t = c.trace, F = t.F, n = S / 2;
            const m = masked(t.pooled, p, seed);
            const top = maxOf(t.pooled) / (1 - p || 1);
            maps.replaceChildren(...Array.from({ length: F }, (_, f) => h("figure", {}, gridCanvas(core.channel(m, n, F, f), n, n, { cell: 8, mode: "heat", range: [0, top] }), `${f + 1}`)));
            const clean = core.softmax(t.logits);
            const once = core.softmax(matvec(m, W().W, W().b));
            const avg = [0, 0, 0];
            for (let k = 0; k < 50; k++) core.softmax(matvec(masked(t.pooled, p, 1000 + k), W().W, W().b)).forEach((v, i) => { avg[i] += v / 50; });
            const alreadyZero = t.pooled.filter((v) => v === 0).length / t.pooled.length;
            out.replaceChildren(
                stats([[tr({ fr: "neurones éteints par le masque", en: "neurons dropped by the mask" }), pct(m.dropped)],
                    [tr({ fr: "déjà nuls (ReLU)", en: "already zero (ReLU)" }), pct(alreadyZero)], [tr({ fr: "facteur des survivants", en: "survivor scale" }), `×${num(1 / (1 - p || 1), 2)}`]]),
                h("h4", {}, tr({ fr: "Sans dropout (inférence)", en: "Without dropout (inference)" })), probBars(D.r.image.classes, clean),
                h("h4", { style: "margin-top:0.5rem" }, tr({ fr: "Avec ce masque", en: "With this mask" })), probBars(D.r.image.classes, once),
                h("h4", { style: "margin-top:0.5rem" }, tr({ fr: "Moyenne sur 50 masques (« MC dropout »)", en: "Average over 50 masks ('MC dropout')" })), probBars(D.r.image.classes, avg));
        }
        root.replaceChildren(h("div", { class: "cnn-lab" },
            h("div", { class: "cnn-controls" },
                slider(tr({ fr: "taux de dropout p", en: "dropout rate p" }), 0, 0.9, 0.05, p, (v) => num(v, 2), (v) => { p = v; update(); }),
                h("button", { type: "button", class: "pd-btn", onclick: () => { seed++; update(); } }, "🎲 " + tr({ fr: "Nouveau masque", en: "New mask" })),
                h("div", { class: "pd-caption" }, tr({ fr: "Entrée : les 8 cartes après pooling de l'image dessinée en haut de la page.", en: "Input: the 8 pooled maps of the image drawn at the top of the page." })),
                maps),
            h("div", { class: "cnn-out" }, out)));
        on("cnn", update);
        update();
    }

    // ================================================================ batch normalisation

    function labBatchNorm(root) {
        let f = 0, gamma = 1, beta = 0;
        const out = h("div");
        const batch = () => D.r.image.test_indices.map((i) => core.cnnTrace(W(), normCNN(D.shapes[i].px)));
        let traces = null;
        function update() {
            traces = traces || batch();
            const F = traces[0].F;
            const vals = [];
            for (const t of traces) for (let i = 0; i < S * S; i++) vals.push(t.z[i * F + f]);
            const mu = vals.reduce((a, b) => a + b, 0) / vals.length;
            const sd = Math.sqrt(vals.reduce((a, b) => a + (b - mu) ** 2, 0) / vals.length) || 1;
            const xhat = vals.map((v) => (v - mu) / sd);
            const y = xhat.map((v) => gamma * v + beta);
            const lim = (a) => [Math.min(...a), Math.max(...a)];
            const r0 = lim(vals), r2 = lim(y.concat([-3, 3]));
            out.replaceChildren(
                stats([["μ", num(mu)], ["σ", num(sd)], [tr({ fr: "valeurs", en: "values" }), vals.length.toLocaleString(LANG)]]),
                h("h4", {}, tr({ fr: "Avant : sortie brute du filtre sur le lot", en: "Before: raw filter output over the batch" })), histogram(vals, 40, [r0[0], r0[1] + 1e-9], "#6b8cff"),
                h("h4", {}, tr({ fr: "Normalisé : (x − μ) / σ", en: "Normalised: (x − μ) / σ" })), histogram(xhat, 40, [Math.min(-3, ...lim(xhat)), Math.max(3, ...lim(xhat)) + 1e-9], "#2d4a8e"),
                h("h4", {}, `${tr({ fr: "Après", en: "After" })} γ·x̂ + β (γ = ${num(gamma, 1)}, β = ${num(beta, 1)})`), histogram(y, 40, [r2[0], r2[1] + 1e-9], "#e67e22"));
        }
        root.replaceChildren(h("div", { class: "cnn-lab" },
            h("div", { class: "cnn-controls" },
                h("div", {}, h("h4", {}, tr({ fr: "Filtre", en: "Filter" })), choices(Array.from({ length: 8 }, (_, i) => [i, String(i + 1)]), f, (k) => { f = k; update(); })),
                slider("γ (" + tr({ fr: "échelle", en: "scale" }) + ")", 0.2, 3, 0.1, gamma, (v) => num(v, 1), (v) => { gamma = v; update(); }),
                slider("β (" + tr({ fr: "décalage", en: "shift" }) + ")", -2, 2, 0.1, beta, (v) => num(v, 1), (v) => { beta = v; update(); }),
                h("div", { class: "pd-caption" }, tr({
                    fr: "Lot : les 45 images de test, 256 positions chacune. γ et β sont appris pendant l'entraînement.",
                    en: "Batch: the 45 test images, 256 positions each. γ and β are learnt during training.",
                }))),
            h("div", { class: "cnn-out" }, out)));
        update();
    }

    // ================================================================ softmax

    function labSoftmax(root) {
        let T = 1;
        const out = h("div");
        function update() {
            const c = shared.cnn;
            if (!c) return;
            const z = c.trace.logits;
            const p = core.softmax(z.map((v) => v / T));
            out.replaceChildren(
                h("div", { class: "pd-mono" }, D.r.image.classes.map((k, i) => `z(${label(k)}) = ${num(z[i])}   →   e^(z/T) / Σ = ${num(p[i], 3)}`).join("\n")),
                probBars(D.r.image.classes, p),
                stats([[tr({ fr: "classe prédite", en: "predicted class" }), label(D.r.image.classes[core.argmax(p)])],
                    [tr({ fr: "confiance", en: "confidence" }), pct(Math.max(...p))],
                    [tr({ fr: "entropie", en: "entropy" }), num(-p.reduce((a, v) => a + (v > 0 ? v * Math.log(v) : 0), 0), 2)]]));
        }
        root.replaceChildren(h("div", { class: "cnn-lab" },
            h("div", { class: "cnn-controls" },
                slider(tr({ fr: "température T", en: "temperature T" }), 0.1, 5, 0.1, T, (v) => num(v, 1), (v) => { T = v; update(); }),
                h("div", { class: "pd-caption" }, tr({ fr: "Entrée : les scores du CNN pour l'image dessinée en haut de la page.", en: "Input: the CNN scores for the image drawn at the top of the page." }))),
            h("div", { class: "cnn-out" }, out)));
        on("cnn", update);
        update();
    }

    // ---------------------------------------------------------------- start

    const LABS = {
        cnn: labCNN, convolution: labConvolution, activation: labActivation, pooling: labPooling,
        receptive: labReceptive, dropout: labDropout, batchnorm: labBatchNorm, softmax: labSoftmax,
    };

    async function start() {
        const roots = [...document.querySelectorAll("[data-lab]")];
        if (!roots.length) return;
        roots.forEach((r) => { r.classList.add("pd-root"); r.replaceChildren(h("div", { class: "pd-loading" }, tr({ fr: "Chargement…", en: "Loading…" }))); });
        try {
            await loadAll();
        } catch (err) {
            roots.forEach((r) => r.replaceChildren(h("div", { class: "pd-error" }, tr({ fr: "Impossible de charger les données : ", en: "Could not load the data: " }) + err.message)));
            return;
        }
        // the CNN and convolution labs publish what the other labs consume, so they go first
        const order = ["cnn", "convolution", "activation", "pooling", "receptive", "dropout", "batchnorm", "softmax"];
        roots.sort((a, b) => order.indexOf(a.dataset.lab) - order.indexOf(b.dataset.lab));
        for (const r of roots) {
            const lab = LABS[r.dataset.lab];
            if (lab) lab(r);
        }
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
    else start();
})();
