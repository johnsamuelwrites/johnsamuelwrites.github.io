/* Run with node src/test/test_mlp.cjs. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const M = require('../../ui/mlp/model.js');
const w = M.create(42);
assert.deepEqual(w, M.create(42));
assert.notDeepEqual(w, M.create(43));
const sample = M.data[0], g = M.gradient(w, M.forward(w, sample.input), sample.target);
for (let l = 0; l < w.length; l++) for (let j = 0; j < w[l].length; j++) for (let i = 0; i < w[l][j].length; i++) {
    const plus = M.clone(w), minus = M.clone(w), epsilon = 1e-6;
    plus[l][j][i] += epsilon; minus[l][j][i] -= epsilon;
    const numerical = (M.loss(M.forward(plus, sample.input).output, sample.target) - M.loss(M.forward(minus, sample.input).output, sample.target)) / (2 * epsilon);
    assert.ok(Math.abs(numerical - g[l][j][i]) < 1e-8, 'Finite difference gradient');
}
function ui(lang) {
    const elements = new Map(), timers = new Map(); let timerId = 0;
    function element(id) {
        if (!elements.has(id)) elements.set(id, {value:({seed:'42',rate:'0.5',mode:'1',speed:'1'})[id] || '',textContent:'',innerHTML:'',disabled:false,checked:false,listeners:{},addEventListener(event,fn){this.listeners[event]=fn;},checkValidity(){return true;},reportValidity(){return true;}});
        return elements.get(id);
    }
    const context = { window:{MLPModel:M,matchMedia:()=>({matches:false})},document:{documentElement:{lang},getElementById:element},crypto:require('node:crypto').webcrypto,MouseEvent:class {},setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);} };
    vm.runInNewContext(fs.readFileSync(require.resolve('../../ui/mlp/mlp.js'),'utf8'),context);
    const click = id => element(id).listeners.click();
    for (const [batch, count] of [['1',4],['2',2],['4',1]]) {
        element('mode').value=batch; element('mode').listeners.change();
        const initialLoss=element('finalLoss').textContent;
        for(let n=0;n<50 && element('epochs').textContent !== 1;n++)click('step');
        assert.equal(element('epochs').textContent,1);
        assert.equal(element('updates').textContent,count);
        assert.notEqual(element('observed').textContent,'—');
        click('reset');
        assert.equal(element('finalLoss').textContent,initialLoss);
        assert.equal(element('updates').textContent,0);
    }
    click('forward'); assert.equal(element('updates').textContent,0);
    click('train'); assert.equal(element('mode').disabled,true);
    click('pause'); assert.equal(element('train').disabled,false);
    click('reset'); assert.equal(timers.size,0); assert.equal(element('mode').disabled,false);
    click('compare'); assert.ok(element('comparison').innerHTML.includes('120'));
    return element('finalLoss').textContent;
}
ui('fr'); ui('en');
console.log('Passed: all 20 numerical gradients; seeded initialization; SGD/mini-batch/batch update counts; reset; forward-only; pause; cancellation; comparison; both languages.');
