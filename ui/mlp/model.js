/* Shared, deterministic teaching model. No browser dependencies. */
(function (root) {
    'use strict';
    const data = [
        { input: [.2, .3, .1], target: [.8, .2] },
        { input: [.8, .7, .9], target: [.2, .8] },
        { input: [.1, .8, .2], target: [.7, .3] },
        { input: [.9, .2, .8], target: [.3, .7] }
    ];
    const sizes = [3, 4, 2];
    function create(seed = 42) {
        let state = seed >>> 0;
        const random = () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296; };
        return sizes.slice(1).map((n, l) => Array.from({ length: n }, () => Array.from({ length: sizes[l] }, () => random() - .5)));
    }
    const zeros = w => w.map(layer => layer.map(row => row.map(() => 0)));
    const clone = w => w.map(layer => layer.map(row => [...row]));
    function forward(w, input) {
        const activations = [[...input]], sums = [[...input]];
        w.forEach((layer, l) => {
            const z = layer.map(row => row.reduce((s, v, i) => s + v * activations[l][i], 0));
            sums.push(z); activations.push(z.map(v => 1 / (1 + Math.exp(-v))));
        });
        return { activations, sums, output: activations[2] };
    }
    const loss = (output, target) => output.reduce((s, v, i) => s + (v - target[i]) ** 2, 0) / output.length;
    function gradient(w, pass, target) {
        const a = pass.activations;
        const delta = [];
        delta[2] = a[2].map((v, i) => 2 / a[2].length * (v - target[i]) * v * (1 - v));
        delta[1] = a[1].map((v, i) => w[1].reduce((s, row, j) => s + row[i] * delta[2][j], 0) * v * (1 - v));
        return w.map((layer, l) => layer.map((row, j) => row.map((v, i) => a[l][i] * delta[l + 1][j])));
    }
    function accumulate(sum, g) { sum.forEach((layer, l) => layer.forEach((row, j) => row.forEach((v, i) => { row[i] += g[l][j][i]; }))); }
    function update(w, g, rate, count = 1) { w.forEach((layer, l) => layer.forEach((row, j) => row.forEach((v, i) => { row[i] -= rate * g[l][j][i] / count; }))); }
    const evaluate = w => data.reduce((s, sample) => s + loss(forward(w, sample.input).output, sample.target), 0) / data.length;
    const model = { data, sizes, create, clone, zeros, forward, loss, gradient, accumulate, update, evaluate };
    if (typeof module !== 'undefined' && module.exports) module.exports = model;
    else root.MLPModel = model;
})(typeof globalThis !== 'undefined' ? globalThis : this);
