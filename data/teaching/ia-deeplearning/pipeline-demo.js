/* Interactive deep-learning pipeline demo, shared by
 *   fr/enseignement/cours/2026/IA-DeepLearning/pipeline.html
 *   en/teaching/courses/2026/AI-DeepLearning/pipeline.html
 *
 * Loads the tiny synthetic datasets of this folder and demo_results.json
 * (written by `demo_pipeline.py --json`), then walks through the 10 pipeline
 * steps for each modality. Plain browser JavaScript, no dependencies, no build
 * step; needs demo-core.js loaded first. The host page needs
 * <div id="pipeline-demo"></div>; the language comes from <html lang>.
 */
(function () {
    "use strict";

    const {
        core, BASE, LANG, tr, COLON, label, pct, num, int, bytes, h, paint, stats, box, probBars,
        confusionTable, lossChart, barChart, arch, slider, fetchOk, loadWav, loadShapes,
    } = window.DLDemo;

    const STEP_NAMES = tr({
        fr: ["Problème", "Données", "Architecture", "Compilation", "Entraînement", "Évaluation",
            "Explicabilité", "Compression", "Déploiement", "Surveillance"],
        en: ["Problem", "Data", "Architecture", "Compilation", "Training", "Evaluation",
            "Explainability", "Compression", "Deployment", "Monitoring"],
    });

    const MODALITIES = [
        { key: "image", icon: "🖼️", name: tr({ fr: "Image", en: "Image" }), sub: tr({ fr: "formes 16×16 · CNN", en: "16×16 shapes · CNN" }) },
        { key: "audio", icon: "🔊", name: "Audio", sub: tr({ fr: "sons de 0,5 s · spectrogramme", en: "0.5 s sounds · spectrogram" }) },
        { key: "texte", icon: "📝", name: tr({ fr: "Texte", en: "Text" }), sub: tr({ fr: "avis fr/en · sac de mots", en: "fr/en reviews · bag of words" }) },
    ];


    // ---------------------------------------------------------------- data

    const D = {};

    async function loadAll() {
        const [results, shapes, sounds, reviews] = await Promise.all([
            fetchOk("demo_results.json").then((r) => r.json()),
            loadShapes(),
            fetchOk("sons_labels.csv").then((r) => r.text()).then(core.parseCSV),
            fetchOk("avis.csv").then((r) => r.text()).then(core.parseCSV),
        ]);
        D.r = results;
        D.shapes = shapes;
        D.sounds = sounds;
        D.reviews = reviews;
        D.vocabA = new Map(results.texte.model_a.vocab.map((w, i) => [w, i]));
        D.vocabB = new Map(results.texte.model_b.vocab.map((w, i) => [w, i]));
    }

    // image helpers
    const imgNorm = (px) => Float64Array.from(px, (v) => (v - D.r.image.mean) / D.r.image.std);
    const cnnProbs = (x) => core.softmax(core.cnn(D.r.image.cnn_weights, x));
    const mlpProbs = (x) => core.softmax(core.dense(D.r.image.mlp_weights, x));
    const testShapes = () => D.r.image.test_indices.map((i) => ({ index: i, ...D.shapes[i] }));
    const shapeCanvas = (px, size = 40) => paint(h("canvas", { "aria-hidden": "true" }), px, 16, 16, "grey", size);

    // audio helpers
    const audioPredict = (x) => {
        const a = D.r.audio;
        const f = core.audioFeatures(core.spectrogram(x));
        return core.softmax(core.dense(a.weights, Array.from(f, (v, i) => (v - a.mu[i]) / a.sd[i])));
    };
    const testSounds = () => D.sounds.filter((s) => s.split === "test");

    // text helpers
    function textModel(which) {
        const t = D.r.texte;
        return which === "A" ? { ...t.model_a, index: D.vocabA, bigrams: false } : { ...t.model_b, index: D.vocabB, bigrams: true };
    }
    function textPredict(text, lang, which) {
        const m = textModel(which);
        const toks = core.tokenize(text, lang);
        const { feats, counts } = core.bag(toks, m.index, m.bigrams);
        const z = core.linear(m, counts);
        return { toks, feats, counts, probs: core.softmax(z), model: m };
    }

    // ---------------------------------------------------------------- state & frame

    const state = {
        modality: "image",
        step: 1,
        image: { selected: null, shifted: false, augSeed: 1 },
        audio: { clip: null },
        text: { value: null, lang: LANG },
    };

    let root;

    function render() {
        root.replaceChildren();
        root.append(h("div", { class: "pd-tabs", role: "tablist", "aria-label": tr({ fr: "Modalité", en: "Modality" }) },
            MODALITIES.map((m) => h("button", {
                class: "pd-tab", role: "tab", "aria-selected": String(state.modality === m.key),
                onclick: () => { state.modality = m.key; render(); },
            }, h("strong", {}, `${m.icon} ${m.name}`), h("span", {}, m.sub)))));

        root.append(h("div", { class: "pd-steps", role: "list" }, STEP_NAMES.map((name, i) => h("button", {
            class: "pd-step", role: "listitem", "aria-current": state.step === i + 1 ? "step" : false,
            title: `${tr({ fr: "Étape", en: "Step" })} ${String(i + 1).padStart(2, "0")} · ${name}`,
            onclick: () => { state.step = i + 1; render(); },
        }, h("b", {}, String(i + 1).padStart(2, "0")), h("span", { class: "pd-step-name" }, name)))));

        const view = VIEWS[state.modality][state.step - 1]();
        const text = h("div", { class: "pd-text" },
            h("h3", {}, `${tr({ fr: "Étape", en: "Step" })} ${String(state.step).padStart(2, "0")} · ${view.title}`),
            (view.body || []).map((p) => h("p", { html: p })),
            view.stats ? stats(view.stats) : null,
            view.takeaway ? h("div", { class: "pd-takeaway", html: view.takeaway }) : null);
        const visual = h("div", { class: "pd-visual" });
        root.append(h("div", { class: "pd-panel", "aria-live": "polite" }, text, visual));
        if (view.visual) view.visual(visual);

        root.append(h("div", { class: "pd-nav" },
            h("button", { class: "pd-btn", disabled: state.step === 1, onclick: () => go(-1) }, "← " + tr({ fr: "Précédent", en: "Previous" })),
            h("button", { class: "pd-btn pd-primary", disabled: state.step === 10, onclick: () => go(1) }, tr({ fr: "Suivant", en: "Next" }) + " →")));
    }

    function go(delta) {
        state.step = Math.min(10, Math.max(1, state.step + delta));
        render();
        root.querySelector(".pd-step[aria-current]")?.focus({ preventScroll: true });
    }

    // ---------------------------------------------------------------- shared step 04

    function compileView(hyper) {
        return {
            title: tr({ fr: "Perte, optimiseur et garde-fous", en: "Loss, optimiser and safeguards" }),
            body: [
                tr({
                    fr: "Perte : <b>entropie croisée</b> <code>L = −log p(classe vraie)</code>. Elle est faible quand le modèle donne une forte probabilité à la bonne classe, et explose quand il se trompe avec assurance.",
                    en: "Loss: <b>cross-entropy</b> <code>L = −log p(true class)</code>. It is small when the model gives a high probability to the right class, and blows up when it is confidently wrong.",
                }),
                tr({
                    fr: `Optimiseur : <b>Adam</b> (taux d'apprentissage ${hyper.lr}), régularisation L2 ${hyper.l2}, lots de 32 exemples, au plus 150 époques.`,
                    en: `Optimiser: <b>Adam</b> (learning rate ${hyper.lr}), L2 regularisation ${hyper.l2}, batches of 32 examples, at most 150 epochs.`,
                }),
                tr({
                    fr: "<b>Arrêt anticipé</b> : après chaque époque on mesure la perte de validation ; si elle ne s'améliore plus pendant 15 époques, on s'arrête et on restaure les meilleurs poids.",
                    en: "<b>Early stopping</b>: after each epoch we measure the validation loss; if it has not improved for 15 epochs, training stops and the best weights are restored.",
                }),
            ],
            takeaway: tr({
                fr: "Le gradient de cette perte par rapport aux scores est simplement <code>p − y</code> : la correction est proportionnelle à l'erreur de probabilité.",
                en: "The gradient of this loss with respect to the scores is simply <code>p − y</code>: the correction is proportional to the probability error.",
            }),
            visual(el) {
                const out = h("div", { class: "pd-stats" });
                const W = 360, H = 140, P = 24;
                const pts = [];
                for (let i = 1; i <= 100; i++) {
                    const p = i / 100;
                    pts.push(`${(P + (W - 2 * P) * p).toFixed(1)},${(H - P - ((H - 2 * P) * Math.min(-Math.log(p), 4.6)) / 4.6).toFixed(1)}`);
                }
                const chart = h("div");
                const update = (p) => {
                    const L = -Math.log(p);
                    const cx = P + (W - 2 * P) * p, cy = H - P - ((H - 2 * P) * Math.min(L, 4.6)) / 4.6;
                    chart.innerHTML = `<svg class="pd-chart" viewBox="0 0 ${W} ${H}" aria-hidden="true">
                        <line x1="${P}" y1="${H - P}" x2="${W - P}" y2="${H - P}" stroke="#bbb"/>
                        <polyline points="${pts.join(" ")}" fill="none" stroke="#6b8cff" stroke-width="2"/>
                        <circle cx="${cx}" cy="${cy}" r="5" fill="#2d4a8e"/>
                        <text x="${W - P}" y="${H - 6}" font-size="10" text-anchor="end" fill="#666">p(${tr({ fr: "classe vraie", en: "true class" })}) → 1</text>
                        <text x="${P}" y="${P - 8}" font-size="10" fill="#666">L</text></svg>`;
                    out.replaceChildren(...stats([
                        ["p", num(p, 2)], ["L = −log p", num(L, 3)], ["∂L/∂z", num(p - 1, 2)],
                    ]).children);
                };
                el.append(box(tr({ fr: "Essayez : probabilité donnée à la bonne classe", en: "Try it: probability given to the right class" }),
                    slider("p", 0.01, 0.99, 0.01, 0.7, (v) => num(v, 2), update), chart, out));
                update(0.7);
            },
        };
    }

    function quantText() {
        return tr({
            fr: "<b>Quantification int8</b> : chaque matrice de poids <code>w</code> est remplacée par <code>q = round(w / s)</code> avec <code>s = max|w| / 127</code>, stockée sur 1 octet au lieu de 4.",
            en: "<b>int8 quantisation</b>: each weight matrix <code>w</code> is replaced by <code>q = round(w / s)</code> with <code>s = max|w| / 127</code>, stored in 1 byte instead of 4.",
        });
    }

    async function timeInference(button, out, items, predict, unit) {
        button.disabled = true;
        out.replaceChildren(tr({ fr: "calcul…", en: "running…" }));
        const inputs = await Promise.all(items.map((it) => it.input()));
        const t0 = performance.now();
        let correct = 0;
        inputs.forEach((x, i) => { if (core.argmax(predict(x)) === items[i].y) correct++; });
        const ms = (performance.now() - t0) / items.length;
        out.replaceChildren(stats([
            [tr({ fr: "exactitude", en: "accuracy" }), pct(correct / items.length)],
            [tr({ fr: "temps", en: "time" }), `${num(ms, ms < 1 ? 2 : 1)} ms / ${unit}`],
            [tr({ fr: "exemples", en: "examples" }), items.length],
        ]));
        button.disabled = false;
    }

    // ================================================================ IMAGE

    const IMAGE = [
        () => {
            const r = D.r.image;
            return {
                title: tr({ fr: "Reconnaître une forme", en: "Recognise a shape" }),
                body: [tr({
                    fr: "Chaque exemple est une image 16×16 en niveaux de gris, bruitée, contenant un <b>cercle</b>, un <b>carré</b> ou un <b>triangle</b> de taille et de position variables. Tâche : prédire la forme.",
                    en: "Each example is a noisy 16×16 greyscale image containing a <b>circle</b>, a <b>square</b> or a <b>triangle</b> of varying size and position. Task: predict the shape.",
                }), tr({
                    fr: "Les classes sont équilibrées (100 images chacune), donc l'<b>exactitude</b> suffit comme métrique. Le hasard donne 33 % : tout modèle doit faire mieux.",
                    en: "Classes are balanced (100 images each), so <b>accuracy</b> is a sufficient metric. Chance gives 33%: any model must do better.",
                })],
                stats: [[tr({ fr: "classes", en: "classes" }), r.classes.length], ["images", D.shapes.length],
                    [tr({ fr: "taille", en: "size" }), "16×16"], [tr({ fr: "hasard", en: "chance" }), pct(1 / 3)]],
                takeaway: tr({
                    fr: "Avant tout modèle : fixer la tâche, la métrique et une <b>référence</b> à battre.",
                    en: "Before any model: fix the task, the metric and a <b>baseline</b> to beat.",
                }),
                visual(el) {
                    for (const c of ["cercle", "carre", "triangle"]) {
                        const ex = D.shapes.filter((s) => s.label === c && s.split === "train").slice(0, 8);
                        el.append(box(label(c), h("div", { class: "pd-row" }, ex.map((s) => shapeCanvas(s.px, 40)))));
                    }
                },
            };
        },
        () => {
            const r = D.r.image;
            return {
                title: tr({ fr: "Des pixels au tenseur", en: "From pixels to a tensor" }),
                body: [tr({
                    fr: `Les 300 images forment un tenseur <code>[300, 16, 16]</code> d'entiers 0–255, découpé en ${r.split.train} / ${r.split.val} / ${r.split.test} (entraînement / validation / test, stratifié par classe).`,
                    en: `The 300 images form a <code>[300, 16, 16]</code> tensor of integers 0–255, split into ${r.split.train} / ${r.split.val} / ${r.split.test} (train / validation / test, stratified by class).`,
                }), tr({
                    fr: `<b>Normalisation</b> : <code>x' = (x − ${num(r.mean, 1)}) / ${num(r.std, 1)}</code>, moyenne et écart-type calculés <em>sur l'entraînement seulement</em>, pour ne rien laisser fuir du test.`,
                    en: `<b>Normalisation</b>: <code>x' = (x − ${num(r.mean, 1)}) / ${num(r.std, 1)}</code>, with mean and standard deviation computed <em>on the training set only</em>, so nothing leaks from the test set.`,
                }), tr({
                    fr: "<b>Augmentation</b> : à chaque lot, translation aléatoire de ±2 pixels et miroir horizontal. Le modèle voit des variantes sans nouvelles données.",
                    en: "<b>Augmentation</b>: in every batch, a random shift of ±2 pixels and a horizontal flip. The model sees variants without new data.",
                })],
                takeaway: tr({
                    fr: "Les statistiques de normalisation font partie du modèle : il faudra les livrer avec lui (étape 09).",
                    en: "Normalisation statistics are part of the model: they must ship with it (step 09).",
                }),
                visual(el) {
                    const s = D.shapes.find((x) => x.label === "triangle");
                    const matrix = [];
                    for (let y = 0; y < 16; y++) matrix.push(Array.from(s.px.slice(y * 16, y * 16 + 16), (v) => String(v).padStart(3)).join(" "));
                    el.append(box(tr({ fr: "Une image, vue par l'humain et par la machine", en: "One image, as a human and a machine see it" }),
                        h("div", { class: "pd-row", style: "align-items:flex-start" }, shapeCanvas(s.px, 128),
                            h("div", { class: "pd-mono", style: "font-size:0.6rem;flex:1;min-width:0" }, matrix.join("\n")))));
                    const gallery = h("div", { class: "pd-row" });
                    const draw = () => {
                        const rand = core.rng(state.image.augSeed);
                        const x = Float64Array.from(s.px);
                        gallery.replaceChildren(...Array.from({ length: 6 }, () => {
                            let v = core.roll(x, Math.floor(rand() * 5) - 2, Math.floor(rand() * 5) - 2);
                            if (rand() < 0.5) v = core.flip(v);
                            return shapeCanvas(v, 56);
                        }));
                    };
                    el.append(box(tr({ fr: "Augmentation : 6 variantes du même triangle", en: "Augmentation: 6 variants of the same triangle" }), gallery,
                        h("button", { class: "pd-btn", style: "margin-top:0.6rem", onclick: () => { state.image.augSeed++; draw(); } },
                            tr({ fr: "Nouvelles variantes", en: "New variants" }))));
                    draw();
                },
            };
        },
        () => {
            const r = D.r.image;
            return {
                title: tr({ fr: "Trois modèles, du plus naïf au plus adapté", en: "Three models, from naive to well-suited" }),
                body: [tr({
                    fr: `<b>Centroïde</b> : on moyenne les images de chaque classe et on choisit la plus proche. Aucun paramètre appris : <b>${pct(r.baseline)}</b> en test.`,
                    en: `<b>Centroid</b>: average the images of each class and pick the closest. No learnt parameters: <b>${pct(r.baseline)}</b> on test.`,
                }), tr({
                    fr: `<b>MLP</b> : l'image aplatie (256 valeurs) → 32 neurones ReLU → 3 sorties, soit ${int(r.params.mlp)} paramètres. Chaque pixel a son propre poids : une forme décalée est une entrée entièrement nouvelle.`,
                    en: `<b>MLP</b>: the flattened image (256 values) → 32 ReLU neurons → 3 outputs, ${int(r.params.mlp)} parameters. Each pixel has its own weight: a shifted shape is an entirely new input.`,
                }), tr({
                    fr: `<b>CNN</b> : 8 filtres 3×3 glissent sur l'image avec les mêmes poids partout, puis max-pooling 2×2 et une couche dense : ${int(r.params.cnn)} paramètres seulement.`,
                    en: `<b>CNN</b>: 8 filters of 3×3 slide over the image with the same weights everywhere, then 2×2 max-pooling and a dense layer: only ${int(r.params.cnn)} parameters.`,
                })],
                takeaway: tr({
                    fr: "Une architecture encode une hypothèse : le CNN suppose qu'un motif reste le même, où qu'il soit dans l'image.",
                    en: "An architecture encodes an assumption: the CNN assumes a pattern is the same wherever it appears in the image.",
                }),
                visual(el) {
                    el.append(box(`MLP · ${int(r.params.mlp)} ${tr({ fr: "paramètres", en: "parameters" })}`,
                        arch([[tr({ fr: "image", en: "image" }), "16×16"], ["flatten", "256"], ["dense + ReLU", "32"], ["softmax", "3"]])));
                    el.append(box(`CNN · ${int(r.params.cnn)} ${tr({ fr: "paramètres", en: "parameters" })}`,
                        arch([[tr({ fr: "image", en: "image" }), "16×16"], ["conv 3×3 + ReLU", "16×16×8"], ["max-pool 2×2", "8×8×8"],
                            ["flatten", "512"], ["softmax", "3"]])));
                    el.append(box(tr({ fr: "Centroïdes : la « forme moyenne » de chaque classe", en: "Centroids: the 'average shape' of each class" }),
                        h("div", { class: "pd-row" }, ["cercle", "carre", "triangle"].map((c) => {
                            const ex = D.shapes.filter((s) => s.label === c && s.split === "train");
                            const m = new Float64Array(256);
                            ex.forEach((s) => s.px.forEach((v, i) => { m[i] += v / ex.length; }));
                            return h("div", {}, shapeCanvas(m, 72), h("div", { class: "pd-caption" }, label(c)));
                        })),
                        h("div", { class: "pd-caption" }, tr({
                            fr: "Les formes changent de place : les moyennes sont floues, d'où l'exactitude modeste.",
                            en: "Shapes move around, so the averages are blurry, hence the modest accuracy.",
                        }))));
                },
            };
        },
        () => compileView({ lr: "0,01", l2: "10⁻⁴" }),
        () => {
            const c = D.r.image.curves;
            return {
                title: tr({ fr: "Courbes d'apprentissage", en: "Learning curves" }),
                body: [tr({
                    fr: `Le <b>MLP</b> (sans augmentation) fait chuter sa perte d'entraînement presque à zéro, mais sa perte de validation cesse de baisser : il apprend les exemples par cœur (<b>surapprentissage</b>). L'arrêt anticipé garde les poids de l'époque ${c.mlp.best}.`,
                    en: `The <b>MLP</b> (no augmentation) drives its training loss almost to zero, but its validation loss stops improving: it memorises the examples (<b>overfitting</b>). Early stopping keeps the weights from epoch ${c.mlp.best}.`,
                }), tr({
                    fr: `Le <b>CNN</b>, aidé par l'augmentation, continue de progresser en validation jusqu'à l'époque ${c.cnn.best} sur ${c.cnn.val.length}.`,
                    en: `The <b>CNN</b>, helped by augmentation, keeps improving on validation until epoch ${c.cnn.best} of ${c.cnn.val.length}.`,
                })],
                takeaway: tr({
                    fr: "C'est l'écart entre les deux courbes, pas la perte d'entraînement seule, qui révèle le surapprentissage.",
                    en: "It is the gap between the two curves, not the training loss alone, that reveals overfitting.",
                }),
                visual(el) {
                    el.append(lossChart(c.mlp, "MLP"), lossChart(c.cnn, tr({ fr: "CNN (avec augmentation)", en: "CNN (with augmentation)" })));
                },
            };
        },
        () => {
            const r = D.r.image;
            return {
                title: tr({ fr: "Évaluation et robustesse", en: "Evaluation and robustness" }),
                body: [tr({
                    fr: `Exactitude en test : centroïde <b>${pct(r.baseline)}</b>, MLP <b>${pct(r.accuracy.mlp)}</b>, CNN <b>${pct(r.accuracy.cnn)}</b>.`,
                    en: `Test accuracy: centroid <b>${pct(r.baseline)}</b>, MLP <b>${pct(r.accuracy.mlp)}</b>, CNN <b>${pct(r.accuracy.cnn)}</b>.`,
                }), tr({
                    fr: `<b>Test de robustesse</b> : décalons toutes les images de test de 3 pixels vers la droite. Le MLP tombe à <b>${pct(r.shifted.mlp)}</b>, le CNN reste à <b>${pct(r.shifted.cnn)}</b>.`,
                    en: `<b>Robustness test</b>: shift every test image 3 pixels to the right. The MLP drops to <b>${pct(r.shifted.mlp)}</b>, the CNN stays at <b>${pct(r.shifted.cnn)}</b>.`,
                }), tr({
                    fr: "Cliquez sur une image de test pour voir les probabilités des deux modèles, puis activez le décalage.",
                    en: "Click a test image to see both models' probabilities, then turn on the shift.",
                })],
                takeaway: tr({
                    fr: "Une bonne exactitude ne suffit pas : on teste aussi le modèle sur des données légèrement différentes.",
                    en: "Good accuracy is not enough: also test the model on slightly different data.",
                }),
                visual(el) {
                    const tests = testShapes();
                    if (state.image.selected == null) state.image.selected = tests[0].index;
                    const gallery = h("div", { class: "pd-gallery" });
                    const detail = h("div");
                    const score = h("div", { class: "pd-caption" });
                    const input = (s) => {
                        const x = imgNorm(s.px);
                        return state.image.shifted ? core.roll(x, 0, 3) : x;
                    };
                    const draw = () => {
                        let okM = 0, okC = 0;
                        gallery.replaceChildren(...tests.map((s) => {
                            const x = input(s);
                            const y = r.classes.indexOf(s.label);
                            const pc = core.argmax(cnnProbs(x)), pm = core.argmax(mlpProbs(x));
                            okC += pc === y;
                            okM += pm === y;
                            const shown = state.image.shifted ? core.roll(Float64Array.from(s.px), 0, 3) : s.px;
                            return h("button", {
                                class: pm !== y ? "pd-wrong" : "", "aria-pressed": String(s.index === state.image.selected),
                                "aria-label": `${label(s.label)} n° ${s.index}`,
                                onclick: () => { state.image.selected = s.index; draw(); },
                            }, shapeCanvas(shown, 40));
                        }));
                        score.textContent = tr({
                            fr: `Correct : MLP ${okM}/${tests.length} · CNN ${okC}/${tests.length}. Contour rouge : erreur du MLP.`,
                            en: `Correct: MLP ${okM}/${tests.length} · CNN ${okC}/${tests.length}. Red outline: MLP error.`,
                        });
                        const s = D.shapes[state.image.selected];
                        const x = input(s);
                        detail.replaceChildren(h("div", { class: "pd-row", style: "align-items:flex-start" },
                            shapeCanvas(state.image.shifted ? core.roll(Float64Array.from(s.px), 0, 3) : s.px, 96),
                            h("div", { style: "flex:1;min-width:12rem" },
                                h("div", { class: "pd-caption" }, `${tr({ fr: "vraie classe", en: "true class" })}${COLON}${label(s.label)}`),
                                h("h4", {}, "MLP"), probBars(r.classes, mlpProbs(x)),
                                h("h4", { style: "margin-top:0.5rem" }, "CNN"), probBars(r.classes, cnnProbs(x)))));
                    };
                    const toggle = h("label", { class: "pd-row", style: "font-size:0.9rem" },
                        h("input", { type: "checkbox", checked: state.image.shifted, onchange: (e) => { state.image.shifted = e.target.checked; draw(); } }),
                        tr({ fr: "Décaler les images de 3 px", en: "Shift images by 3 px" }));
                    el.append(box(tr({ fr: `Les ${tests.length} images de test`, en: `The ${tests.length} test images` }), toggle, gallery, score));
                    el.append(box(tr({ fr: "Image sélectionnée", en: "Selected image" }), detail));
                    el.append(box(tr({ fr: "Matrice de confusion du CNN (test)", en: "CNN confusion matrix (test)" }), confusionTable(r.classes, r.confusion)));
                    draw();
                },
            };
        },
        () => {
            const r = D.r.image;
            const s = D.shapes[r.saliency.index];
            return {
                title: tr({ fr: "Où regarde le modèle ?", en: "Where does the model look?" }),
                body: [tr({
                    fr: "<b>Carte de saillance</b> : on dérive le score de la classe prédite par rapport à chaque pixel d'entrée, <code>|∂score/∂pixel|</code>. Plus la couleur est chaude, plus une petite variation de ce pixel changerait la décision.",
                    en: "<b>Saliency map</b>: differentiate the predicted class score with respect to each input pixel, <code>|∂score/∂pixel|</code>. The warmer the colour, the more a small change to that pixel would change the decision.",
                }), tr({
                    fr: `Image de test n° ${r.saliency.index}, vraie classe « ${label(s.label)} », prédite « ${label(r.saliency.predicted)} ». Les pixels influents sont-ils sur la forme et ses bords, ou dans le bruit du fond ?`,
                    en: `Test image no. ${r.saliency.index}, true class '${label(s.label)}', predicted '${label(r.saliency.predicted)}'. Are the influential pixels on the shape and its edges, or in the background noise?`,
                })],
                takeaway: tr({
                    fr: "L'explicabilité sert à vérifier que le modèle a raison <em>pour de bonnes raisons</em>.",
                    en: "Explainability checks that the model is right <em>for the right reasons</em>.",
                }),
                visual(el) {
                    const sal = r.saliency.map.flat();
                    const overlay = Array.from(s.px, (v, i) => v * 0.45 + 255 * 0.55 * sal[i]);
                    el.append(box(tr({ fr: "Image · saillance · superposition", en: "Image · saliency · overlay" }),
                        h("div", { class: "pd-row" }, shapeCanvas(s.px, 128), paint(h("canvas"), sal, 16, 16, "heat", 128),
                            paint(h("canvas"), overlay, 16, 16, "heat", 128))));
                },
            };
        },
        () => {
            const r = D.r.image;
            const q = r.quantization;
            return {
                title: tr({ fr: "Plus petit, aussi juste", en: "Smaller, just as accurate" }),
                body: [quantText(), tr({
                    fr: `Le CNN passe de ${bytes(q.before)} à ${bytes(q.after)}, et son exactitude de ${pct(r.accuracy.cnn)} à ${pct(q.accuracy)}.`,
                    en: `The CNN goes from ${bytes(q.before)} to ${bytes(q.after)}, and its accuracy from ${pct(r.accuracy.cnn)} to ${pct(q.accuracy)}.`,
                })],
                stats: [[tr({ fr: "avant", en: "before" }), bytes(q.before)], [tr({ fr: "après", en: "after" }), bytes(q.after)],
                    [tr({ fr: "gain", en: "ratio" }), `÷${num(q.before / q.after, 1)}`], [tr({ fr: "exactitude", en: "accuracy" }), pct(q.accuracy)]],
                takeaway: tr({
                    fr: "Sur un microcontrôleur ou un téléphone, diviser la taille par 4 sans perte compte plus que quelques dixièmes de point.",
                    en: "On a microcontroller or a phone, a 4× smaller model with no loss matters more than a few tenths of a point.",
                }),
                visual(el) {
                    const K = r.cnn_weights.K;
                    el.append(box(tr({ fr: "Les 8 filtres 3×3 appris (après quantification)", en: "The 8 learnt 3×3 filters (after quantisation)" }),
                        h("div", { class: "pd-row" }, K[0].map((_, f) => paint(h("canvas"), K.map((row) => row[f]), 3, 3, "diverging", 56))),
                        h("div", { class: "pd-caption" }, tr({
                            fr: "Rouge : poids positif, bleu : négatif. Plusieurs filtres ressemblent à des détecteurs de bords.",
                            en: "Red: positive weight, blue: negative. Several filters look like edge detectors.",
                        }))));
                },
            };
        },
        () => {
            const r = D.r.image;
            return {
                title: tr({ fr: "Servir le modèle", en: "Serving the model" }),
                body: [tr({
                    fr: `On exporte les poids, les noms de classes <em>et</em> la normalisation (${bytes(r.export_bytes)} en JSON ; en production : ONNX, TorchScript, TFLite…). Sans la normalisation, le modèle servi recevrait des entrées qu'il n'a jamais vues.`,
                    en: `We export the weights, the class names <em>and</em> the normalisation (${bytes(r.export_bytes)} as JSON; in production: ONNX, TorchScript, TFLite…). Without the normalisation, the served model would receive inputs it has never seen.`,
                }), tr({
                    fr: "Ici, c'est <b>votre navigateur</b> qui sert le modèle : le CNN est réimplémenté en JavaScript à partir de ces poids.",
                    en: "Here, <b>your browser</b> serves the model: the CNN is re-implemented in JavaScript from those weights.",
                })],
                takeaway: tr({
                    fr: "Le modèle déployé = poids + prétraitement + post-traitement. Un écart entre entraînement et service est un bug classique.",
                    en: "The deployed model = weights + preprocessing + postprocessing. A mismatch between training and serving is a classic bug.",
                }),
                visual(el) {
                    const out = h("div");
                    const tests = testShapes();
                    const button = h("button", {
                        class: "pd-btn pd-primary",
                        onclick: () => timeInference(button, out, tests.map((s) => ({ input: async () => imgNorm(s.px), y: r.classes.indexOf(s.label) })),
                            cnnProbs, "image"),
                    }, tr({ fr: `Classer les ${tests.length} images de test`, en: `Classify the ${tests.length} test images` }));
                    el.append(box(tr({ fr: "Inférence dans le navigateur", en: "Inference in the browser" }), button, out));
                    el.append(box(tr({ fr: "Contenu de l'export", en: "Export contents" }), h("div", { class: "pd-mono" },
                        `{\n  "classes": ${JSON.stringify(r.classes)},\n  "moyenne": ${num(r.mean, 1).replace(",", ".")}, "ecart_type": ${num(r.std, 1).replace(",", ".")},\n  "poids": { "K": [9×8], "bk": [8], "W": [512×3], "b": [3] }\n}`)));
                },
            };
        },
        () => {
            const r = D.r.image;
            const ref = r.drift.reference;
            const names = { normal: tr({ fr: "normal", en: "normal" }), noisy: tr({ fr: "caméra bruitée (σ +60)", en: "noisy camera (σ +60)" }), dark: tr({ fr: "exposition sombre (×0,5)", en: "dark exposure (×0.5)" }) };
            return {
                title: tr({ fr: "Surveiller la dérive", en: "Monitoring drift" }),
                body: [tr({
                    fr: "En production, les images changent : capteur bruité, mauvaise exposition… On ne connaît pas les vraies classes, mais on peut comparer des <b>statistiques d'entrée</b> à celles de l'entraînement : moyenne, écart-type et « grain » (écart moyen entre pixels voisins). Alerte si l'une s'écarte de plus de 20 %.",
                    en: "In production, images change: noisy sensor, bad exposure… We don't know the true classes, but we can compare <b>input statistics</b> to the training ones: mean, standard deviation and 'grain' (mean jump between neighbouring pixels). Alert if one moves by more than 20%.",
                }), tr({
                    fr: "Bougez les curseurs. Trouvez un réglage où l'exactitude chute <em>sans</em> alerte sur la moyenne ni l'écart-type : c'est une dérive silencieuse.",
                    en: "Move the sliders. Find a setting where accuracy drops <em>without</em> an alert on the mean or standard deviation: that is silent drift.",
                })],
                takeaway: tr({
                    fr: "Une seule statistique ne suffit pas : surveillez plusieurs indicateurs, et réétiquetez un échantillon régulièrement.",
                    en: "One statistic is not enough: monitor several indicators, and relabel a sample regularly.",
                }),
                visual(el) {
                    const tests = testShapes();
                    let noise = 0, gain = 1;
                    const out = h("div");
                    const preview = h("div", { class: "pd-row" });
                    const update = () => {
                        const rand = core.rng(7);
                        let s1 = 0, s2 = 0, g = 0, n = 0, gn = 0, ok = 0;
                        const imgs = tests.map((s) => {
                            const px = Float64Array.from(s.px, (v) => Math.min(255, Math.max(0, v * gain + noise * rand.gauss())));
                            for (let y = 0; y < 16; y++) {
                                for (let x = 0; x < 16; x++) {
                                    const v = px[y * 16 + x];
                                    s1 += v; s2 += v * v; n++;
                                    if (x) { g += Math.abs(v - px[y * 16 + x - 1]); gn++; }
                                }
                            }
                            ok += core.argmax(cnnProbs(imgNorm(px))) === r.classes.indexOf(s.label);
                            return px;
                        });
                        const mean = s1 / n, std = Math.sqrt(s2 / n - mean * mean);
                        const ratios = [[tr({ fr: "moyenne", en: "mean" }), mean / ref.mean], [tr({ fr: "écart-type", en: "std" }), std / ref.std], ["grain", g / gn / ref.grain]];
                        preview.replaceChildren(...imgs.slice(0, 6).map((px) => shapeCanvas(px, 44)));
                        out.replaceChildren(h("table", { class: "pd-table" },
                            h("tbody", {}, ratios.map(([k, v]) => h("tr", {}, h("td", {}, k), h("td", {}, `×${num(v, 2)}`),
                                h("td", { class: Math.abs(v - 1) > 0.2 ? "pd-flag" : "pd-ok" }, Math.abs(v - 1) > 0.2 ? tr({ fr: "⚠ alerte", en: "⚠ alert" }) : "ok"))),
                            h("tr", {}, h("th", {}, tr({ fr: "exactitude (cachée en production)", en: "accuracy (hidden in production)" })), h("th", {}, pct(ok / tests.length)), h("th", {})))));
                    };
                    el.append(box(tr({ fr: "Simulez la production", en: "Simulate production" }),
                        slider(tr({ fr: "bruit σ", en: "noise σ" }), 0, 100, 5, 0, (v) => int(v), (v) => { noise = v; update(); }),
                        slider(tr({ fr: "exposition", en: "exposure" }), 0.3, 1.5, 0.05, 1, (v) => "×" + num(v, 2), (v) => { gain = v; update(); }),
                        preview, out));
                    el.append(box(tr({ fr: "Scénarios calculés par demo_pipeline.py", en: "Scenarios computed by demo_pipeline.py" }),
                        h("table", { class: "pd-table" },
                            h("thead", {}, h("tr", {}, h("th", {}, tr({ fr: "scénario", en: "scenario" })), h("th", {}, tr({ fr: "moy.", en: "mean" })), h("th", {}, tr({ fr: "é.-t.", en: "std" })), h("th", {}, "grain"), h("th", {}, tr({ fr: "exactitude", en: "accuracy" })), h("th", {}, ""))),
                            h("tbody", {}, r.drift.rows.map((row) => h("tr", {}, h("td", {}, names[row.key]), h("td", {}, `×${num(row.mean, 2)}`), h("td", {}, `×${num(row.std, 2)}`),
                                h("td", {}, `×${num(row.grain, 2)}`), h("td", {}, pct(row.accuracy)), h("td", { class: row.flagged ? "pd-flag" : "pd-ok" }, row.flagged ? "⚠" : "ok")))))));
                    update();
                },
            };
        },
    ];

    // ================================================================ AUDIO

    function waveCanvas(x, w = 360, hgt = 70) {
        const c = h("canvas", { width: w, height: hgt, style: "width:100%;height:auto;display:block", "aria-hidden": "true" });
        const ctx = c.getContext("2d");
        ctx.strokeStyle = "#4a6edb";
        ctx.beginPath();
        for (let i = 0; i < x.length; i++) {
            const px = (i / (x.length - 1)) * w, py = hgt / 2 - (x[i] * hgt) / 2.2;
            if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py);
        }
        ctx.stroke();
        return c;
    }

    function specCanvas(spec, width = 300) {
        const { T, bands, data } = spec;
        const v = new Float64Array(T * bands);
        for (let t = 0; t < T; t++) for (let b = 0; b < bands; b++) v[(bands - 1 - b) * T + t] = data[t * bands + b];
        const c = paint(h("canvas", { "aria-hidden": "true" }), v, T, bands, "heat");
        c.style.width = "100%";
        c.style.maxWidth = width + "px";
        c.style.height = "auto";
        c.style.aspectRatio = `${T} / ${bands * 0.7}`;
        return c;
    }

    function clipPicker(onPick) {
        const a = D.r.audio;
        const row = h("div", { class: "pd-row" });
        a.classes.forEach((c) => {
            const clips = D.sounds.filter((s) => s.label === c);
            row.append(h("button", {
                class: "pd-btn",
                onclick: () => {
                    const cur = D.sounds.indexOf(state.audio.clip);
                    const next = clips.find((s) => D.sounds.indexOf(s) > cur) || clips[0];
                    state.audio.clip = state.audio.clip && state.audio.clip.label === c ? next : clips[0];
                    onPick();
                },
            }, label(c) + " ↻"));
        });
        return row;
    }

    const AUDIO = [
        () => {
            const a = D.r.audio;
            return {
                title: tr({ fr: "Reconnaître un type de son", en: "Recognise a kind of sound" }),
                body: [tr({
                    fr: `${D.sounds.length} clips de 0,5 s à ${int(a.sample_rate)} Hz : <b>son pur</b> (fréquence fixe), <b>glissando</b> (fréquence qui monte), <b>bips</b> (2 à 4 impulsions). Le niveau de bruit de fond varie d'un clip à l'autre.`,
                    en: `${D.sounds.length} clips of 0.5 s at ${int(a.sample_rate)} Hz: <b>pure tone</b> (fixed frequency), <b>chirp</b> (rising frequency), <b>beeps</b> (2 to 4 pulses). The background noise level varies from clip to clip.`,
                }), tr({
                    fr: "Contrainte imaginée : un détecteur embarqué qui doit répondre en moins d'une milliseconde.",
                    en: "Imagined constraint: an embedded detector that must answer in under a millisecond.",
                })],
                stats: [[tr({ fr: "classes", en: "classes" }), 3], ["clips", D.sounds.length], [tr({ fr: "durée", en: "length" }), "0,5 s".replace(",", tr({ fr: ",", en: "." }))],
                    [tr({ fr: "échantillons", en: "samples" }), int(a.samples)]],
                takeaway: tr({
                    fr: "Écoutez d'abord les données : c'est la meilleure façon de comprendre ce qui sera facile ou difficile.",
                    en: "Listen to the data first: it is the best way to understand what will be easy or hard.",
                }),
                visual(el) {
                    a.classes.forEach((c) => {
                        const s = D.sounds.find((x) => x.label === c);
                        const holder = h("div");
                        el.append(box(label(c), h("audio", { controls: true, preload: "none", src: BASE + s.fichier, style: "width:100%" }), holder));
                        loadWav(s.fichier).then((x) => holder.append(waveCanvas(x)));
                    });
                },
            };
        },
        () => {
            const a = D.r.audio;
            const [T, B] = a.spectrogram_shape;
            return {
                title: tr({ fr: "De l'onde au spectrogramme", en: "From waveform to spectrogram" }),
                body: [tr({
                    fr: `Un clip = ${int(a.samples)} nombres dans [−1, 1]. La <b>transformée de Fourier à court terme</b> (fenêtres de 256 échantillons = 32 ms, pas de 16 ms) donne un spectrogramme <code>[${T} trames × ${B} bandes]</code> : l'audio devient une image.`,
                    en: `A clip = ${int(a.samples)} numbers in [−1, 1]. The <b>short-time Fourier transform</b> (windows of 256 samples = 32 ms, hop 16 ms) gives a <code>[${T} frames × ${B} bands]</code> spectrogram: audio becomes an image.`,
                }), tr({
                    fr: "On résume chaque bande par sa moyenne et son écart-type dans le temps : <b>64 caractéristiques</b>, standardisées avec les statistiques de l'entraînement.",
                    en: "Each band is summarised by its mean and standard deviation over time: <b>64 features</b>, standardised with the training statistics.",
                }), tr({
                    fr: `<b>Augmentation</b> : décalage temporel de ±100 ms et bruit ajouté, l'entraînement passe de ${a.split.train} à ${a.augmented} clips.`,
                    en: `<b>Augmentation</b>: a time shift of ±100 ms and added noise; training grows from ${a.split.train} to ${a.augmented} clips.`,
                })],
                takeaway: tr({
                    fr: "Son pur = ligne horizontale, glissando = diagonale, bips = tirets. Le bon prétraitement rend le problème presque visuel.",
                    en: "Pure tone = horizontal line, chirp = diagonal, beeps = dashes. The right preprocessing makes the problem almost visual.",
                }),
                visual(el) {
                    const holder = h("div", { class: "pd-visual" });
                    const draw = async () => {
                        const s = state.audio.clip || (state.audio.clip = D.sounds[0]);
                        const x = await loadWav(s.fichier);
                        const spec = core.spectrogram(x);
                        const f = core.audioFeatures(spec);
                        holder.replaceChildren(
                            box(`${label(s.label)} · ${s.fichier.split("/").pop()}`, h("audio", { controls: true, src: BASE + s.fichier, style: "width:100%" }), waveCanvas(x)),
                            box(tr({ fr: "Spectrogramme (fréquence ↑, temps →)", en: "Spectrogram (frequency ↑, time →)" }), specCanvas(spec)),
                            box(tr({ fr: "64 caractéristiques : moyenne puis écart-type par bande", en: "64 features: mean then standard deviation per band" }),
                                barChart(Array.from(f), "#6b8cff", tr({ fr: "bandes 0 → 4 000 Hz, deux fois", en: "bands 0 → 4,000 Hz, twice" }))));
                    };
                    el.append(box(tr({ fr: "Choisissez un clip", en: "Pick a clip" }), clipPicker(draw)), holder);
                    draw();
                },
            };
        },
        () => {
            const a = D.r.audio;
            return {
                title: tr({ fr: "Un petit réseau dense", en: "A small dense network" }),
                body: [tr({
                    fr: `<b>MLP 64 → 16 → 3</b> : ${int(a.params)} paramètres. Le gros du travail est fait par le prétraitement : le spectrogramme sépare déjà bien les classes.`,
                    en: `<b>MLP 64 → 16 → 3</b>: ${int(a.params)} parameters. Most of the work is done by the preprocessing: the spectrogram already separates the classes well.`,
                }), tr({
                    fr: "Avec plus de données, on donnerait directement le spectrogramme à un CNN (comme une image) ou l'onde brute à un réseau convolutif 1D.",
                    en: "With more data, we would feed the spectrogram straight to a CNN (like an image), or the raw waveform to a 1D convolutional network.",
                })],
                takeaway: tr({
                    fr: "Peu de données → caractéristiques choisies à la main + petit modèle. Beaucoup de données → le modèle apprend ses propres caractéristiques.",
                    en: "Little data → hand-picked features + small model. Lots of data → the model learns its own features.",
                }),
                visual(el) {
                    el.append(box(`MLP · ${int(a.params)} ${tr({ fr: "paramètres", en: "parameters" })}`,
                        arch([[tr({ fr: "onde", en: "wave" }), "4000"], ["STFT", `${a.spectrogram_shape[0]}×${a.spectrogram_shape[1]}`],
                            [tr({ fr: "moy. + é.-t.", en: "mean + std" }), "64"], [tr({ fr: "standardisation", en: "standardise" }), "64"],
                            ["dense + ReLU", "16"], ["softmax", "3"]])));
                },
            };
        },
        () => compileView({ lr: "0,01", l2: "10⁻⁴" }),
        () => {
            const c = D.r.audio.curve;
            return {
                title: tr({ fr: "Courbe d'apprentissage", en: "Learning curve" }),
                body: [tr({
                    fr: `La perte d'entraînement tombe très vite. La validation ne compte que ${D.r.audio.split.val} clips : sa courbe est irrégulière. Meilleurs poids à l'époque ${c.best}, arrêt à l'époque ${c.val.length}.`,
                    en: `The training loss falls very fast. Validation has only ${D.r.audio.split.val} clips, so its curve is bumpy. Best weights at epoch ${c.best}, stopped at epoch ${c.val.length}.`,
                })],
                takeaway: tr({
                    fr: "Un petit jeu de validation donne une estimation bruitée : ne sur-interprétez pas chaque oscillation.",
                    en: "A small validation set gives a noisy estimate: don't over-read every wiggle.",
                }),
                visual(el) { el.append(lossChart(c, "MLP")); },
            };
        },
        () => {
            const a = D.r.audio;
            let worst = null;
            a.confusion.forEach((row, i) => row.forEach((v, j) => { if (i !== j && v && (!worst || v > worst.v)) worst = { i, j, v }; }));
            return {
                title: tr({ fr: "Évaluation", en: "Evaluation" }),
                body: [tr({
                    fr: `Exactitude en test : <b>${pct(a.accuracy)}</b> sur ${a.split.test} clips.`,
                    en: `Test accuracy: <b>${pct(a.accuracy)}</b> on ${a.split.test} clips.`,
                }), worst ? tr({
                    fr: `Erreur la plus fréquente : « ${label(a.classes[worst.i])} » prédit « ${label(a.classes[worst.j])} » (${worst.v} fois). Écoutez ces clips ci-dessous : le bruit de fond rend-il la différence difficile ?`,
                    en: `Most frequent error: '${label(a.classes[worst.i])}' predicted as '${label(a.classes[worst.j])}' (${worst.v} times). Listen to those clips below: does background noise make the difference hard to hear?`,
                }) : ""],
                takeaway: tr({
                    fr: "La matrice de confusion dit <em>quelles</em> classes se confondent, pas seulement combien d'erreurs il y a.",
                    en: "The confusion matrix tells you <em>which</em> classes get mixed up, not just how many errors there are.",
                }),
                visual(el) {
                    el.append(box(tr({ fr: "Matrice de confusion (test)", en: "Confusion matrix (test)" }), confusionTable(a.classes, a.confusion)));
                    const list = h("table", { class: "pd-table" });
                    el.append(box(tr({ fr: "Clips de test et prédictions (calculées dans le navigateur)", en: "Test clips and predictions (computed in the browser)" }), list));
                    Promise.all(testSounds().map(async (s) => ({ s, p: audioPredict(await loadWav(s.fichier)) }))).then((items) => {
                        list.append(h("thead", {}, h("tr", {}, h("th", {}, tr({ fr: "écouter", en: "listen" })), h("th", {}, tr({ fr: "vrai", en: "true" })), h("th", {}, tr({ fr: "prédit", en: "predicted" })))),
                            h("tbody", {}, items.map(({ s, p }) => {
                                const pred = a.classes[core.argmax(p)];
                                return h("tr", {}, h("td", {}, h("audio", { controls: true, preload: "none", src: BASE + s.fichier, style: "height:2rem;max-width:11rem" })),
                                    h("td", {}, label(s.label)), h("td", { class: pred === s.label ? "pd-ok" : "pd-flag" }, `${label(pred)} (${pct(Math.max(...p))})`));
                            })));
                    });
                },
            };
        },
        () => {
            const a = D.r.audio;
            const imp = a.importance;
            const all = [...imp.mean.map((v, i) => [v, i, "mean"]), ...imp.std.map((v, i) => [v, i, "std"])].sort((x, y) => y[0] - x[0]).slice(0, 3);
            return {
                title: tr({ fr: "Quelles fréquences comptent ?", en: "Which frequencies matter?" }),
                body: [tr({
                    fr: "On mesure l'importance de chaque caractéristique par la dérivée moyenne du score prédit, <code>|∂score/∂caractéristique|</code>, sur le jeu de test.",
                    en: "We measure each feature's importance as the mean derivative of the predicted score, <code>|∂score/∂feature|</code>, over the test set.",
                }), tr({
                    fr: `Les plus utiles : ${all.map(([, i, k]) => `${int(Math.round(imp.hz[i]))} Hz (${k === "mean" ? "moyenne" : "écart-type"})`).join(", ")}. Les sons purs et les bips vivent dans la zone 300–1000 Hz ; l'<em>écart-type</em> dans le temps y distingue un son continu de bips intermittents.`,
                    en: `Most useful: ${all.map(([, i, k]) => `${int(Math.round(imp.hz[i]))} Hz (${k === "mean" ? "mean" : "std"})`).join(", ")}. Pure tones and beeps live in the 300–1,000 Hz range; the <em>standard deviation</em> over time is what tells a continuous tone from intermittent beeps.`,
                })],
                takeaway: tr({
                    fr: "Une explication doit pouvoir se relier au domaine : ici, à la physique du signal.",
                    en: "An explanation should connect to the domain: here, to the physics of the signal.",
                }),
                visual(el) {
                    el.append(box(tr({ fr: "Importance : moyenne par bande", en: "Importance: mean per band" }),
                        barChart(imp.mean, "#6b8cff", `0 → ${int(Math.round(imp.hz[imp.hz.length - 1]))} Hz`)));
                    el.append(box(tr({ fr: "Importance : écart-type par bande", en: "Importance: standard deviation per band" }),
                        barChart(imp.std, "#2d4a8e", `0 → ${int(Math.round(imp.hz[imp.hz.length - 1]))} Hz`)));
                },
            };
        },
        () => {
            const a = D.r.audio;
            const q = a.quantization;
            return {
                title: tr({ fr: "Un modèle de 1 Ko", en: "A 1 KB model" }),
                body: [quantText(), tr({
                    fr: `Le modèle passe de ${bytes(q.before)} à ${bytes(q.after)} ; exactitude ${pct(a.accuracy)} → ${pct(q.accuracy)}. Il tiendrait dans la mémoire d'un microcontrôleur.`,
                    en: `The model goes from ${bytes(q.before)} to ${bytes(q.after)}; accuracy ${pct(a.accuracy)} → ${pct(q.accuracy)}. It would fit in a microcontroller's memory.`,
                })],
                stats: [[tr({ fr: "avant", en: "before" }), bytes(q.before)], [tr({ fr: "après", en: "after" }), bytes(q.after)],
                    [tr({ fr: "exactitude", en: "accuracy" }), pct(q.accuracy)]],
                takeaway: tr({
                    fr: "Attention : le calcul du spectrogramme coûte aussi. En embarqué, on optimise tout le pipeline, pas seulement les poids.",
                    en: "Careful: computing the spectrogram costs too. On a device, you optimise the whole pipeline, not just the weights.",
                }),
                visual(el) {
                    const W1 = a.weights.W1;
                    const cols = W1[0].length;
                    const flat = [];
                    for (let j = 0; j < cols; j++) for (let i = 0; i < W1.length; i++) flat.push(W1[i][j]);
                    const c = paint(h("canvas", { "aria-hidden": "true" }), flat, W1.length, cols, "diverging");
                    c.style.width = "100%";
                    c.style.height = "auto";
                    el.append(box(tr({ fr: "Première couche quantifiée : 64 entrées × 16 neurones", en: "Quantised first layer: 64 inputs × 16 neurons" }), c,
                        h("div", { class: "pd-caption" }, tr({
                            fr: "Une ligne par neurone ; à gauche les moyennes par bande, à droite les écarts-types. Rouge : poids positif, bleu : négatif. Chaque poids ne prend plus que 255 valeurs possibles.",
                            en: "One row per neuron; band means on the left, standard deviations on the right. Red: positive weight, blue: negative. Each weight now takes only 255 possible values.",
                        }))));
                },
            };
        },
        () => {
            const a = D.r.audio;
            return {
                title: tr({ fr: "Servir le modèle", en: "Serving the model" }),
                body: [tr({
                    fr: `Export : poids + moyennes et écarts-types des 64 caractéristiques (${bytes(a.export_bytes)} en JSON). Le service doit refaire <em>exactement</em> la même STFT qu'à l'entraînement : même fenêtre, même pas, mêmes bandes.`,
                    en: `Export: weights + means and standard deviations of the 64 features (${bytes(a.export_bytes)} as JSON). Serving must redo <em>exactly</em> the same STFT as in training: same window, same hop, same bands.`,
                }), tr({
                    fr: "Le bouton lance la chaîne complète dans votre navigateur : décodage WAV → STFT → caractéristiques → MLP.",
                    en: "The button runs the whole chain in your browser: WAV decoding → STFT → features → MLP.",
                })],
                takeaway: tr({
                    fr: "Le temps mesuré inclut le prétraitement : c'est souvent lui, et non le réseau, qui domine en audio.",
                    en: "The measured time includes preprocessing: in audio, it is often that, not the network, which dominates.",
                }),
                visual(el) {
                    const out = h("div");
                    const tests = testSounds();
                    const button = h("button", {
                        class: "pd-btn pd-primary",
                        onclick: () => timeInference(button, out, tests.map((s) => ({ input: () => loadWav(s.fichier), y: a.classes.indexOf(s.label) })), audioPredict, "clip"),
                    }, tr({ fr: `Classer les ${tests.length} clips de test`, en: `Classify the ${tests.length} test clips` }));
                    el.append(box(tr({ fr: "Inférence dans le navigateur", en: "Inference in the browser" }), button, out));
                },
            };
        },
        () => {
            const a = D.r.audio;
            const ref = a.drift.reference;
            const names = { normal: "normal", noisy: tr({ fr: "micro bruyant (σ 0,4)", en: "noisy mic (σ 0.4)" }), quiet: tr({ fr: "gain faible (×0,1)", en: "low gain (×0.1)" }) };
            return {
                title: tr({ fr: "Surveiller la dérive", en: "Monitoring drift" }),
                body: [tr({
                    fr: `Deux indicateurs sans étiquette : l'<b>énergie</b> (RMS) et le <b>bruit de fond</b> (10<sup>e</sup> centile du spectrogramme). Plages vues à l'entraînement : énergie ${num(ref.energy[0])}–${num(ref.energy[1])}, bruit de fond ${num(ref.floor[0])}–${num(ref.floor[1])}. Alerte si la médiane sort de la plage.`,
                    en: `Two label-free indicators: <b>energy</b> (RMS) and <b>background noise</b> (10th percentile of the spectrogram). Ranges seen in training: energy ${num(ref.energy[0])}–${num(ref.energy[1])}, background noise ${num(ref.floor[0])}–${num(ref.floor[1])}. Alert if the median leaves the range.`,
                }), tr({
                    fr: "Le micro bruyant ne déclenche pas l'alerte d'énergie : seul le bruit de fond le trahit.",
                    en: "The noisy mic does not trigger the energy alert: only the background noise gives it away.",
                })],
                takeaway: tr({
                    fr: "Choisir les indicateurs de surveillance demande de comprendre comment les données peuvent se dégrader.",
                    en: "Choosing monitoring indicators requires understanding how the data can degrade.",
                }),
                visual(el) {
                    let noise = 0, gain = 1;
                    const out = h("div");
                    let token = 0;
                    const update = async () => {
                        const mine = ++token;
                        const tests = testSounds();
                        const waves = await Promise.all(tests.map((s) => loadWav(s.fichier)));
                        if (mine !== token) return;
                        const rand = core.rng(8);
                        const energies = [], floors = [];
                        let ok = 0;
                        waves.forEach((w, k) => {
                            const x = Float64Array.from(w, (v) => v * gain + noise * rand.gauss());
                            const spec = core.spectrogram(x);
                            energies.push(core.rms(x));
                            floors.push(core.percentile(spec.data, 10));
                            const f = core.audioFeatures(spec);
                            ok += core.argmax(core.dense(a.weights, Array.from(f, (v, i) => (v - a.mu[i]) / a.sd[i]))) === a.classes.indexOf(tests[k].label);
                        });
                        const med = (arr) => core.percentile(arr, 50);
                        const rows = [[tr({ fr: "énergie", en: "energy" }), med(energies), ref.energy], [tr({ fr: "bruit de fond", en: "background noise" }), med(floors), ref.floor]];
                        out.replaceChildren(h("table", { class: "pd-table" }, h("tbody", {},
                            rows.map(([k, v, range]) => {
                                const bad = v < range[0] || v > range[1];
                                return h("tr", {}, h("td", {}, k), h("td", {}, num(v)), h("td", { class: bad ? "pd-flag" : "pd-ok" }, bad ? tr({ fr: "⚠ alerte", en: "⚠ alert" }) : "ok"));
                            }),
                            h("tr", {}, h("th", {}, tr({ fr: "exactitude (cachée en production)", en: "accuracy (hidden in production)" })), h("th", {}, pct(ok / tests.length)), h("th", {})))));
                    };
                    el.append(box(tr({ fr: "Simulez la production", en: "Simulate production" }),
                        slider(tr({ fr: "bruit σ", en: "noise σ" }), 0, 0.6, 0.05, 0, (v) => num(v), (v) => { noise = v; update(); }),
                        slider("gain", 0.05, 2, 0.05, 1, (v) => "×" + num(v), (v) => { gain = v; update(); }), out));
                    el.append(box(tr({ fr: "Scénarios calculés par demo_pipeline.py", en: "Scenarios computed by demo_pipeline.py" }),
                        h("table", { class: "pd-table" },
                            h("thead", {}, h("tr", {}, h("th", {}, tr({ fr: "scénario", en: "scenario" })), h("th", {}, tr({ fr: "énergie", en: "energy" })), h("th", {}, tr({ fr: "bruit", en: "noise" })), h("th", {}, tr({ fr: "exactitude", en: "accuracy" })), h("th", {}, ""))),
                            h("tbody", {}, a.drift.rows.map((row) => h("tr", {}, h("td", {}, names[row.key]), h("td", {}, num(row.energy)), h("td", {}, num(row.floor)),
                                h("td", {}, pct(row.accuracy)), h("td", { class: row.flagged ? "pd-flag" : "pd-ok" }, row.flagged ? "⚠" : "ok")))))));
                    update();
                },
            };
        },
    ];

    // ================================================================ TEXT

    function textInput(onChange) {
        const t = D.r.texte;
        if (state.text.value == null) {
            state.text.value = LANG === "fr" ? t.example.text : "The film isn't dull, but the pacing is weak.";
        }
        const input = h("input", { class: "pd-input", type: "text", value: state.text.value, "aria-label": tr({ fr: "Votre avis", en: "Your review" }) });
        const select = h("select", { class: "pd-input", "aria-label": tr({ fr: "Langue", en: "Language" }) },
            h("option", { value: "fr", selected: state.text.lang === "fr" }, "fr"), h("option", { value: "en", selected: state.text.lang === "en" }, "en"));
        input.addEventListener("input", () => { state.text.value = input.value; onChange(); });
        select.addEventListener("change", () => { state.text.lang = select.value; onChange(); });
        return h("div", { class: "pd-row", style: "flex-wrap:nowrap" }, input, select);
    }

    function presets(onPick) {
        const items = LANG === "fr"
            ? [["La musique n'est pas médiocre.", "fr"], ["Le scénario est brillant, mais le rythme est faible.", "fr"], ["Le film est génial !", "fr"], ["The film isn't dull.", "en"]]
            : [["The film isn't dull.", "en"], ["The script is superb, but the pacing is weak.", "en"], ["The film is awesome!", "en"], ["La musique n'est pas médiocre.", "fr"]];
        return h("div", { class: "pd-row", style: "margin-top:0.5rem" }, items.map(([text, lang]) => h("button", {
            class: "pd-btn", style: "font-size:0.8rem;padding:0.25rem 0.6rem;font-weight:500",
            onclick: () => { state.text.value = text; state.text.lang = lang; onPick(); },
        }, text)));
    }

    function tokenChips(items) {
        return h("div", { class: "pd-tokens" }, items.map(([text, note, unknown]) => h("span", { class: "pd-token" + (unknown ? " pd-unknown" : "") }, text, note != null ? h("small", {}, note) : null)));
    }

    function contributionChips(res) {
        const c = core.argmax(res.probs);
        const inv = res.model.vocab;
        const contrib = [...res.counts].map(([idx, n]) => [idx, n * res.model.W[idx][c]]).sort((x, y) => Math.abs(y[1]) - Math.abs(x[1]));
        const max = Math.max(...contrib.map(([, v]) => Math.abs(v))) || 1;
        return h("div", { class: "pd-tokens" }, contrib.map(([idx, v]) => h("span", {
            class: "pd-token" + (idx === 0 ? " pd-unknown" : ""),
            style: `background:${v >= 0 ? `rgba(46,139,87,${(0.12 + (0.5 * Math.abs(v)) / max).toFixed(2)})` : `rgba(192,57,43,${(0.12 + (0.5 * Math.abs(v)) / max).toFixed(2)})`}`,
        }, idx === 0 ? tr({ fr: "‹inconnu›", en: "‹unknown›" }) : inv[idx], h("small", {}, (v >= 0 ? "+" : "") + num(v, 2)))));
    }

    const TEXT = [
        () => {
            const t = D.r.texte;
            return {
                title: tr({ fr: "Classer un avis de film", en: "Classify a film review" }),
                body: [tr({
                    fr: `${int(t.n_reviews)} avis courts, en français et en anglais, générés à partir de modèles de phrases : <b>positif</b>, <b>négatif</b> ou <b>mitigé</b>.`,
                    en: `${int(t.n_reviews)} short reviews, in French and English, generated from sentence templates: <b>positive</b>, <b>negative</b> or <b>mixed</b>.`,
                }), tr({
                    fr: "Trois phénomènes, notés dans les données : <b>simple</b>, <b>négation</b> (« n'est pas ennuyeux » est positif) et <b>contraste</b> (« …, mais … » est mitigé).",
                    en: "Three phenomena, recorded in the data: <b>simple</b>, <b>negation</b> ('isn't dull' is positive) and <b>contrast</b> ('…, but …' is mixed).",
                }), tr({
                    fr: `Référence : toujours prédire la classe majoritaire donne <b>${pct(t.majority)}</b>. On mesurera l'exactitude <em>par phénomène</em>.`,
                    en: `Baseline: always predicting the majority class gives <b>${pct(t.majority)}</b>. We will measure accuracy <em>per phenomenon</em>.`,
                })],
                stats: [[tr({ fr: "avis", en: "reviews" }), t.n_reviews], [tr({ fr: "langues", en: "languages" }), "fr, en"], [tr({ fr: "classes", en: "classes" }), 3],
                    [tr({ fr: "référence", en: "baseline" }), pct(t.majority)]],
                takeaway: tr({
                    fr: "Annoter les cas difficiles dès le départ permet une analyse d'erreurs précise plus tard (étape 06).",
                    en: "Tagging the hard cases from the start enables precise error analysis later (step 06).",
                }),
                visual(el) {
                    const pick = [];
                    for (const lang of [LANG, LANG === "fr" ? "en" : "fr"]) {
                        for (const ph of ["simple", "negation", "contraste"]) {
                            const r = D.reviews.find((x) => x.langue === lang && x.phenomene === ph && x.split === "train");
                            if (r) pick.push(r);
                        }
                    }
                    el.append(box(tr({ fr: "Exemples d'entraînement", en: "Training examples" }), h("table", { class: "pd-table" },
                        h("thead", {}, h("tr", {}, h("th", {}, tr({ fr: "avis", en: "review" })), h("th", {}, tr({ fr: "phénomène", en: "phenomenon" })), h("th", {}, "label"))),
                        h("tbody", {}, pick.map((r) => h("tr", {}, h("td", {}, r.texte), h("td", {}, label(r.phenomene)), h("td", {}, label(r.label))))))));
                    const counts = D.r.texte.counts;
                    el.append(box(tr({ fr: "Répartition", en: "Distribution" }), stats(Object.keys(counts).map((k) => [label(k), counts[k]]))));
                },
            };
        },
        () => {
            const t = D.r.texte;
            return {
                title: tr({ fr: "Du texte aux identifiants", en: "From text to IDs" }),
                body: [tr({
                    fr: "<b>Normalisation</b> : minuscules, « n' » → « ne », « l' » → « le », « n't » → « not ». <b>Découpage en jetons</b> : on garde les mots, on retire la ponctuation.",
                    en: "<b>Normalisation</b>: lower case, French « n' » → « ne », « l' » → « le », English « n't » → « not ». <b>Tokenisation</b>: keep the words, drop the punctuation.",
                }), tr({
                    fr: `Chaque jeton reçoit un <b>identifiant</b> dans un vocabulaire construit sur l'entraînement seulement (${t.vocab_size} jetons ; 0 = inconnu). Les séquences sont complétées par des 0 jusqu'à ${t.max_len} jetons.`,
                    en: `Each token gets an <b>ID</b> in a vocabulary built from the training set only (${t.vocab_size} tokens; 0 = unknown). Sequences are padded with 0s up to ${t.max_len} tokens.`,
                }), tr({
                    fr: "Pourquoi retirer la ponctuation ? Dans une première version, le modèle avait appris la paire « médiocre_. » au lieu du sens de la phrase.",
                    en: "Why drop punctuation? In a first version, the model learnt the pair « médiocre_. » instead of the meaning of the sentence.",
                })],
                takeaway: tr({
                    fr: "Tapez une phrase avec un mot jamais vu : il devient « inconnu » (0). Le modèle ne peut rien en faire.",
                    en: "Type a sentence with a word never seen before: it becomes 'unknown' (0). The model can do nothing with it.",
                }),
                visual(el) {
                    const out = h("div");
                    const draw = () => {
                        const toks = core.tokenize(state.text.value, state.text.lang);
                        const ids = toks.map((w) => (D.vocabA.has(w) ? D.vocabA.get(w) : 0));
                        const padded = ids.concat(Array(Math.max(0, t.max_len - ids.length)).fill(0));
                        out.replaceChildren(
                            h("h4", {}, tr({ fr: "Normalisé", en: "Normalised" })), h("div", { class: "pd-mono" }, core.normalise(state.text.value, state.text.lang)),
                            h("h4", { style: "margin-top:0.6rem" }, tr({ fr: "Jetons et identifiants", en: "Tokens and IDs" })),
                            tokenChips(toks.map((w, i) => [w, ids[i], ids[i] === 0])),
                            h("h4", { style: "margin-top:0.6rem" }, tr({ fr: "Tenseur d'entrée", en: "Input tensor" })), h("div", { class: "pd-mono" }, `[${padded.join(", ")}]`));
                    };
                    const wrap = h("div");
                    const reset = () => { wrap.replaceChildren(textInput(draw), presets(reset)); draw(); };
                    el.append(box(tr({ fr: "Tapez un avis", en: "Type a review" }), wrap, out));
                    reset();
                },
            };
        },
        () => {
            const t = D.r.texte;
            return {
                title: tr({ fr: "Sac de mots ou paires de mots ?", en: "Bag of words or word pairs?" }),
                body: [tr({
                    fr: `<b>Modèle A</b> : on compte les mots (sac de mots), puis régression softmax : ${int(t.params.A)} paramètres. L'ordre est perdu : « n'est pas ennuyeux » contient « ennuyeux », mot négatif.`,
                    en: `<b>Model A</b>: count the words (bag of words), then softmax regression: ${int(t.params.A)} parameters. Order is lost: 'isn't dull' contains 'dull', a negative word.`,
                }), tr({
                    fr: `<b>Modèle B</b> : on ajoute les paires de mots consécutifs (bigrammes). « pas_ennuyeux » devient une caractéristique à part entière : ${int(t.params.B)} paramètres.`,
                    en: `<b>Model B</b>: add pairs of consecutive words (bigrams). 'not_dull' becomes a feature of its own: ${int(t.params.B)} parameters.`,
                })],
                takeaway: tr({
                    fr: "Les bigrammes sont un premier pas vers le contexte. Les réseaux récurrents et les Transformers vont beaucoup plus loin.",
                    en: "Bigrams are a first step towards context. Recurrent networks and Transformers go much further.",
                }),
                visual(el) {
                    const out = h("div");
                    const draw = () => {
                        const a = textPredict(state.text.value, state.text.lang, "A");
                        const b = textPredict(state.text.value, state.text.lang, "B");
                        const chips = (res) => tokenChips([...res.counts].map(([idx, n]) => [idx === 0 ? tr({ fr: "‹inconnu›", en: "‹unknown›" }) : res.model.vocab[idx], `×${n}`, idx === 0]));
                        out.replaceChildren(h("h4", {}, tr({ fr: "Caractéristiques du modèle A", en: "Model A features" })), chips(a),
                            h("h4", { style: "margin-top:0.6rem" }, tr({ fr: "Caractéristiques du modèle B", en: "Model B features" })), chips(b));
                    };
                    const wrap = h("div");
                    const reset = () => { wrap.replaceChildren(textInput(draw), presets(reset)); draw(); };
                    el.append(box(tr({ fr: "Ce que voit chaque modèle", en: "What each model sees" }), wrap, out));
                    reset();
                },
            };
        },
        () => compileView({ lr: "0,05", l2: "10⁻³" }),
        () => {
            const c = D.r.texte.curves;
            return {
                title: tr({ fr: "Courbes d'apprentissage", en: "Learning curves" }),
                body: [tr({
                    fr: `Le modèle A plafonne vite : sa perte de validation reste élevée (meilleure époque ${c.A.best}), car il ne peut pas représenter les négations. Le modèle B descend plus bas (meilleure époque ${c.B.best}).`,
                    en: `Model A plateaus quickly: its validation loss stays high (best epoch ${c.A.best}) because it cannot represent negations. Model B goes lower (best epoch ${c.B.best}).`,
                })],
                takeaway: tr({
                    fr: "Une perte qui plafonne haut en entraînement <em>et</em> en validation signale un modèle trop simple (sous-apprentissage).",
                    en: "A loss that plateaus high in training <em>and</em> validation signals a model that is too simple (underfitting).",
                }),
                visual(el) {
                    el.append(lossChart(c.A, tr({ fr: "Modèle A · sac de mots", en: "Model A · bag of words" })), lossChart(c.B, tr({ fr: "Modèle B · + bigrammes", en: "Model B · + bigrams" })));
                },
            };
        },
        () => {
            const t = D.r.texte;
            const ph = t.phenomena;
            return {
                title: tr({ fr: "Évaluation par phénomène", en: "Evaluation per phenomenon" }),
                body: [tr({
                    fr: `Au global, A obtient ${pct(ph.tous.A)} et B ${pct(ph.tous.B)}. Mais c'est sur les <b>négations</b> que tout se joue : ${pct(ph.negation.A)} pour A, ${pct(ph.negation.B)} pour B.`,
                    en: `Overall, A gets ${pct(ph.tous.A)} and B ${pct(ph.tous.B)}. But <b>negations</b> are where it all happens: ${pct(ph.negation.A)} for A, ${pct(ph.negation.B)} for B.`,
                }), tr({
                    fr: "Une moyenne globale cache les sous-groupes où le modèle échoue : c'est le même raisonnement que pour l'analyse d'équité.",
                    en: "An overall average hides the subgroups where the model fails: the same reasoning applies to fairness analysis.",
                })],
                takeaway: tr({
                    fr: "Toujours découper l'évaluation selon les cas qui comptent.",
                    en: "Always slice the evaluation by the cases that matter.",
                }),
                visual(el) {
                    el.append(box(tr({ fr: "Exactitude en test", en: "Test accuracy" }), h("table", { class: "pd-table" },
                        h("thead", {}, h("tr", {}, h("th", {}, tr({ fr: "phénomène", en: "phenomenon" })), h("th", {}, "n"), h("th", {}, "A"), h("th", {}, "B"))),
                        h("tbody", {}, Object.entries(ph).map(([k, v]) => h("tr", {}, h(k === "tous" ? "th" : "td", {}, label(k)), h("td", {}, v.n),
                            h("td", { class: v.A < 0.7 ? "pd-flag" : "" }, pct(v.A)), h("td", { class: v.B >= 0.9 ? "pd-ok" : "" }, pct(v.B))))))));
                    el.append(box(tr({ fr: "Matrice de confusion du modèle B", en: "Model B confusion matrix" }), confusionTable(t.classes, t.confusion)));
                },
            };
        },
        () => {
            const t = D.r.texte;
            return {
                title: tr({ fr: "Pourquoi cette prédiction ?", en: "Why this prediction?" }),
                body: [tr({
                    fr: "Pour un modèle linéaire, l'explication est exacte : la contribution d'une caractéristique au score de la classe prédite = nombre d'occurrences × poids. Vert : pousse vers la classe prédite ; rouge : l'en éloigne.",
                    en: "For a linear model the explanation is exact: a feature's contribution to the predicted class score = count × weight. Green: pushes towards the predicted class; red: pushes away.",
                }), tr({
                    fr: "Essayez une négation : le modèle A s'appuie sur l'adjectif, le modèle B sur la paire « pas_adjectif ».",
                    en: "Try a negation: model A relies on the adjective, model B on the 'not_adjective' pair.",
                })],
                takeaway: tr({
                    fr: "Pour les grands réseaux, on approxime ces contributions (SHAP, LIME, gradients intégrés) ; le principe reste le même.",
                    en: "For large networks we approximate these contributions (SHAP, LIME, integrated gradients); the principle is the same.",
                }),
                visual(el) {
                    const out = h("div");
                    const draw = () => {
                        out.replaceChildren(...["A", "B"].map((m) => {
                            const res = textPredict(state.text.value, state.text.lang, m);
                            return h("div", { style: "margin-top:0.8rem" }, h("h4", {}, `${tr({ fr: "Modèle", en: "Model" })} ${m}`),
                                probBars(t.classes, res.probs), h("div", { style: "margin-top:0.4rem" }, contributionChips(res)));
                        }));
                    };
                    const wrap = h("div");
                    const reset = () => { wrap.replaceChildren(textInput(draw), presets(reset)); draw(); };
                    el.append(box(tr({ fr: "Tapez un avis", en: "Type a review" }), wrap, out));
                    reset();
                },
            };
        },
        () => {
            const t = D.r.texte;
            const p = t.pruning, q = t.quantization;
            return {
                title: tr({ fr: "Élaguer et quantifier", en: "Prune and quantise" }),
                body: [tr({
                    fr: `<b>Élagage</b> : on supprime les entrées du vocabulaire dont les poids sont quasi nuls. ${p.kept} sur ${p.total} sont gardées ; exactitude ${pct(p.before)} → ${pct(p.after)}.`,
                    en: `<b>Pruning</b>: remove vocabulary entries whose weights are almost zero. ${p.kept} of ${p.total} are kept; accuracy ${pct(p.before)} → ${pct(p.after)}.`,
                }), quantText(), tr({
                    fr: `Poids : ${bytes(q.before)} → ${bytes(q.after)}, exactitude ${pct(q.accuracy)}.`,
                    en: `Weights: ${bytes(q.before)} → ${bytes(q.after)}, accuracy ${pct(q.accuracy)}.`,
                })],
                stats: [[tr({ fr: "vocabulaire gardé", en: "vocabulary kept" }), `${p.kept}/${p.total}`], [tr({ fr: "poids", en: "weights" }), `${bytes(q.before)} → ${bytes(q.after)}`],
                    [tr({ fr: "exactitude", en: "accuracy" }), pct(q.accuracy)]],
                takeaway: tr({
                    fr: "Ici, le vocabulaire est petit. Pour un vrai modèle de langue, la table d'embeddings représente souvent l'essentiel de la taille.",
                    en: "Here the vocabulary is small. In a real language model, the embedding table is often most of the size.",
                }),
                visual(el) {
                    const m = t.model_b;
                    const zero = m.W.filter((row) => row.every((v) => v === 0)).length;
                    el.append(box(tr({ fr: "Les caractéristiques les plus fortes de chaque classe (modèle B)", en: "The strongest features of each class (model B)" }),
                        ...t.classes.map((c, j) => {
                            const top = m.vocab.map((w, i) => [w, m.W[i][j]]).filter(([w]) => w !== "<inc>").sort((x, y) => y[1] - x[1]).slice(0, 6);
                            return h("div", { style: "margin-bottom:0.6rem" }, h("h4", {}, label(c)), tokenChips(top.map(([w, v]) => [w, "+" + num(v, 2), false])));
                        }),
                        h("div", { class: "pd-caption" }, tr({
                            fr: `${zero} entrées élaguées ont tous leurs poids à zéro : on peut les retirer du vocabulaire servi.`,
                            en: `${zero} pruned entries have all their weights at zero: they can be dropped from the served vocabulary.`,
                        }))));
                },
            };
        },
        () => {
            const t = D.r.texte;
            return {
                title: tr({ fr: "Une API de sentiment", en: "A sentiment API" }),
                body: [tr({
                    fr: `L'export contient les poids, le vocabulaire et les classes (${bytes(t.export_bytes)}). La normalisation et le découpage en jetons, eux, sont du <em>code</em> : le service doit les reproduire à l'identique.`,
                    en: `The export contains the weights, the vocabulary and the classes (${bytes(t.export_bytes)}). Normalisation and tokenisation, on the other hand, are <em>code</em>: the service must reproduce them exactly.`,
                }), tr({
                    fr: "Ci-contre, votre navigateur joue le rôle du serveur : chaque frappe envoie une « requête » au modèle B.",
                    en: "Opposite, your browser plays the server: every keystroke sends a 'request' to model B.",
                })],
                takeaway: tr({
                    fr: "Versionnez ensemble le modèle, le vocabulaire et le code de prétraitement.",
                    en: "Version the model, the vocabulary and the preprocessing code together.",
                }),
                visual(el) {
                    const out = h("div", { class: "pd-mono" });
                    const draw = () => {
                        const t0 = performance.now();
                        const res = textPredict(state.text.value, state.text.lang, "B");
                        const ms = performance.now() - t0;
                        out.textContent = `POST /predict\n${JSON.stringify({ text: state.text.value, lang: state.text.lang })}\n\n200 OK\n` + JSON.stringify({
                            label: t.classes[core.argmax(res.probs)],
                            probabilities: Object.fromEntries(t.classes.map((c, i) => [c, Math.round(res.probs[i] * 1000) / 1000])),
                            unknown_tokens: res.toks.filter((w) => !D.vocabB.has(w)),
                            latency_ms: Math.round(ms * 1000) / 1000,
                        }, null, 2);
                    };
                    const wrap = h("div");
                    const reset = () => { wrap.replaceChildren(textInput(draw), presets(reset)); draw(); };
                    el.append(box(tr({ fr: "Requête", en: "Request" }), wrap), box(tr({ fr: "Réponse", en: "Response" }), out));
                    reset();
                },
            };
        },
        () => {
            const t = D.r.texte;
            const d = t.drift;
            const slang = d.rows.find((r) => r.key === "slang");
            return {
                title: tr({ fr: "Surveiller le vocabulaire", en: "Monitoring the vocabulary" }),
                body: [tr({
                    fr: `Indicateur sans étiquette : le <b>taux de mots inconnus</b>. Sur le test, il vaut ${pct(d.reference)}. Sur de nouveaux avis en argot (« génial », « bof », « awesome »…), il monte à <b>${pct(slang.oov)}</b> et l'exactitude tombe à <b>${pct(slang.accuracy)}</b>.`,
                    en: `A label-free indicator: the <b>unknown-word rate</b>. On the test set it is ${pct(d.reference)}. On new slang reviews ('génial', 'bof', 'awesome'…) it rises to <b>${pct(slang.oov)}</b> and accuracy falls to <b>${pct(slang.accuracy)}</b>.`,
                }), tr({
                    fr: "La réponse : collecter et annoter ces nouveaux avis, puis réentraîner (retour à l'étape 02).",
                    en: "The fix: collect and label these new reviews, then retrain (back to step 02).",
                })],
                takeaway: tr({
                    fr: "Le pipeline est une boucle : la surveillance alimente la collecte de données suivante.",
                    en: "The pipeline is a loop: monitoring feeds the next round of data collection.",
                }),
                visual(el) {
                    el.append(box(tr({ fr: "Nouveaux avis en production", en: "New reviews in production" }), h("table", { class: "pd-table" },
                        h("thead", {}, h("tr", {}, h("th", {}, tr({ fr: "avis", en: "review" })), h("th", {}, tr({ fr: "attendu", en: "expected" })), h("th", {}, tr({ fr: "prédit", en: "predicted" })))),
                        h("tbody", {}, d.new.map((r) => h("tr", {}, h("td", {}, r.text), h("td", {}, label(r.label)),
                            h("td", { class: r.label === r.predicted ? "pd-ok" : "pd-flag" }, label(r.predicted))))))));
                    const out = h("div");
                    const draw = () => {
                        const toks = core.tokenize(state.text.value, state.text.lang);
                        const unknown = toks.filter((w) => !D.vocabA.has(w));
                        const rate = toks.length ? unknown.length / toks.length : 0;
                        const bad = rate > d.reference + 0.05;
                        out.replaceChildren(stats([[tr({ fr: "mots inconnus", en: "unknown words" }), pct(rate)], [tr({ fr: "référence", en: "reference" }), pct(d.reference)],
                            [tr({ fr: "état", en: "status" }), bad ? tr({ fr: "⚠ alerte", en: "⚠ alert" }) : "ok"]]), tokenChips(toks.map((w) => [w, null, !D.vocabA.has(w)])));
                    };
                    const wrap = h("div");
                    const reset = () => { wrap.replaceChildren(textInput(draw), presets(reset)); draw(); };
                    el.append(box(tr({ fr: "Testez le détecteur", en: "Try the detector" }), wrap, out));
                    reset();
                },
            };
        },
    ];

    const VIEWS = { image: IMAGE, audio: AUDIO, texte: TEXT };

    // ---------------------------------------------------------------- start

    function linkCards() {
        document.querySelectorAll(".pipeline-card").forEach((card) => {
            const m = (card.querySelector(".card-badge")?.textContent || "").match(/(\d+)/);
            if (!m) return;
            const n = +m[1];
            card.append(h("a", {
                class: "pd-card-link", href: "#" + root.id,
                onclick: () => { state.step = n; render(); },
            }, tr({ fr: "▶ Voir sur un exemple", en: "▶ See it on an example" })));
        });
    }

    async function start() {
        root = document.getElementById("pipeline-demo");
        if (!root) return;
        root.classList.add("pd-root");
        root.replaceChildren(h("div", { class: "pd-loading" }, tr({ fr: "Chargement des données…", en: "Loading the data…" })));
        try {
            await loadAll();
        } catch (err) {
            root.replaceChildren(h("div", { class: "pd-error" }, tr({ fr: "Impossible de charger les données de la démonstration : ", en: "Could not load the demo data: " }) + err.message));
            return;
        }
        render();
        linkCards();
        root.addEventListener("keydown", (e) => {
            if (e.target.matches("input, select, textarea")) return;
            if (e.key === "ArrowRight") go(1);
            else if (e.key === "ArrowLeft") go(-1);
        });
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
    else start();
})();
