(() => {
    'use strict';
    const fr = document.documentElement.lang === 'fr';
    const t = (f, e) => fr ? f : e;
    const M = window.MLPModel, $ = id => document.getElementById(id);
    const fmt = (v, n = 4) => v.toLocaleString(fr ? 'fr-FR' : 'en-GB', {minimumFractionDigits:n, maximumFractionDigits:n});
    const vector = values => '[' + values.map(v => fmt(v, 3)).join(' ; ') + ']';
    $('app').innerHTML = `
    <main class="page">
      <nav class="topline" aria-label="${t('Navigation','Navigation')}"><a href="index.html">← ${t('IA & Deep Learning · 2026','AI & Deep Learning · 2026')}</a><a href="../../../../../${fr ? 'en/teaching/courses/2026/AI-DeepLearning' : 'fr/enseignement/cours/2026/IA-DeepLearning'}/mlp.html" lang="${fr ? 'en' : 'fr'}" hreflang="${fr ? 'en' : 'fr'}">${fr ? 'English' : 'Français'} ↗</a></nav>
      <header><h1>${t('Comment un réseau apprend-il ?','How does a network learn?')}</h1><p class="intro">${t('Explorez un perceptron multicouche : suivez une prédiction, calculez les gradients et observez quand les poids changent. Comparez les méthodes à partir des mêmes poids initiaux.','Explore a multilayer perceptron: follow a prediction, calculate gradients, and observe when weights change. Compare methods from the same initial weights.')}</p></header>
      <div class="workspace"><aside>
        <section class="panel settings"><h2>${t('Votre expérience','Your experiment')}</h2>
          <div><label for="mode">${t('Méthode','Method')}</label><select id="mode"><option value="1">${t('Stochastique · SGD','Stochastic · SGD')}</option><option value="2">${t('Mini-lot · 2 exemples','Mini-batch · 2 samples')}</option><option value="4">${t('Lot complet · 4 exemples','Full batch · 4 samples')}</option></select></div>
          <p class="hint wide" id="modeHint"></p>
          <div><label for="rate">${t('Taux d’apprentissage η','Learning rate η')}</label><input id="rate" type="number" min="0.001" max="5" step="0.05" value="0.5"></div>
          <div><label for="seed">${t('Graine aléatoire','Random seed')}</label><input id="seed" type="number" min="0" max="4294967295" step="1" value="42"></div>
          <p class="hint wide">${t('Même graine = mêmes poids initiaux. Changer la méthode ou le taux restaure ces poids.','Same seed = same initial weights. Changing the method or rate restores those weights.')}</p>
          <div class="wide"><button id="random">${t('Nouvelle graine','New seed')}</button></div>
          <div class="wide"><label for="speed">${t('Vitesse','Speed')} <output id="speedValue">1×</output></label><input id="speed" type="range" min="0.3" max="3" step="0.1" value="1"></div>
          <label class="check wide"><input id="motion" type="checkbox">${t('Animation réduite','Reduced animation')}</label>
        </section>
        <section class="panel"><span class="eyebrow">${t('Le modèle','The model')}</span><h2>3 → 4 → 2</h2><p class="hint">${t('3 entrées, 4 neurones cachés, 2 sorties indépendantes. Sigmoïde, erreur quadratique moyenne, sans biais.','3 inputs, 4 hidden neurons, 2 independent outputs. Sigmoid activation, mean squared error, no biases.')}</p><p class="hint">${t('Les quatre exemples sont synthétiques. Les sorties sont des valeurs cibles continues, pas des probabilités de classes normalisées.','The four examples are synthetic. Outputs are continuous target values, not normalized class probabilities.')}</p></section>
      </aside><div>
        <section class="panel" aria-labelledby="networkTitle"><div class="eyebrow">${t('Laboratoire interactif','Interactive lab')}</div><h2 id="networkTitle">${t('De la prédiction à la mise à jour','From prediction to update')}</h2>
          <div class="toolbar"><button class="primary" id="train">${t('Entraîner · 1 époque','Train · 1 epoch')}</button><button id="step">${t('Étape suivante','Next step')}</button><button id="pause" disabled>${t('Pause','Pause')}</button><button id="forward">${t('Prédire seulement','Predict only')}</button><button id="reset">${t('Restaurer les poids initiaux','Restore initial weights')}</button></div>
          <div class="stats"><div class="stat"><span>${t('Perte après entraînement','Post-training loss')}</span><strong id="finalLoss"></strong></div><div class="stat"><span>${t('Perte observée en époque','Loss observed in epoch')}</span><strong id="observed">—</strong></div><div class="stat"><span>${t('Époques terminées','Completed epochs')}</span><strong id="epochs">0</strong></div><div class="stat"><span>${t('Mises à jour','Updates')}</span><strong id="updates">0</strong></div></div>
          <div class="status" role="status" aria-live="polite" aria-atomic="true"><strong id="statusTitle"></strong><p id="statusText"></p></div>
          <svg id="network" class="network" viewBox="0 0 720 310" role="group" aria-label="${t('Réseau : sélectionner un neurone pour inspecter ses valeurs','Network: select a neuron to inspect its values')}"></svg>
          <div class="legend"><span><b style="background:#087f8c"></b>${t('Poids positif','Positive weight')}</span><span><b style="background:#bd5870"></b>${t('Poids négatif','Negative weight')}</span><span>${t('Épaisseur = amplitude du poids','Thickness = weight magnitude')}</span></div>
          <div class="inspector" id="inspector" aria-live="polite"></div>
        </section>
        <section class="panel"><h2>${t('Exemples et prédictions actuelles','Samples and current predictions')}</h2><p class="hint">${t('Les prédictions de ce tableau utilisent toutes les poids actuels. « Perte observée » mémorise la perte au moment du traitement de chaque exemple.','All predictions in this table use the current weights. “Observed loss” records the loss when each sample was processed.')}</p><div class="table-wrap"><table><thead><tr>${[t('Exemple','Sample'),t('Entrées','Inputs'),t('Cibles','Targets'),t('Prédictions','Predictions'),t('Perte actuelle','Current loss'),t('Perte observée','Observed loss')].map(s=>`<th scope="col">${s}</th>`).join('')}</tr></thead><tbody id="samples"></tbody></table></div></section>
        <div class="two-col"><section class="panel"><h2>${t('Progression de la perte','Loss over time')}</h2><svg class="chart" id="chart" viewBox="0 0 480 150" role="img" aria-label="${t('Perte évaluée à la fin de chaque époque','Loss evaluated at the end of each epoch')}"></svg><p class="hint" id="historyText"></p><button id="compare">${t('Comparer les 3 méthodes · 30 époques','Compare all 3 methods · 30 epochs')}</button><div id="comparison" aria-live="polite"></div></section>
        <section class="panel"><h2>${t('À observer','Things to notice')}</h2><ol><li>${t('En SGD, les exemples suivants utilisent des poids déjà modifiés.','With SGD, later samples use weights that have already changed.')}</li><li>${t('En lot complet, les quatre gradients sont calculés avec les mêmes poids, puis moyennés.','With full batch, all four gradients use the same weights and are then averaged.')}</li><li>${t('Un mini-lot de deux exemples donne deux mises à jour par époque.','A mini-batch of two samples gives two updates per epoch.')}</li></ol><details><summary>${t('Exercice guidé','Guided exercise')}</summary><p>${t('Avec la graine 42 et η = 0,5, exécutez une époque pour chaque méthode. Pourquoi le nombre de mises à jour diffère-t-il ? Pourquoi la perte observée peut-elle différer de la perte finale ? Essayez ensuite η = 0,05.','With seed 42 and η = 0.5, run one epoch for each method. Why does the update count differ? Why can the observed loss differ from the final loss? Then try η = 0.05.')}</p></details></section></div>
      </div></div>
      <section class="panel"><h2>${t('Les calculs derrière la visualisation','The calculations behind the visualization')}</h2><div class="two-col"><div><h3>${t('Propagation avant','Forward propagation')}</h3><code class="formula">zⱼ = Σᵢ wⱼᵢ aᵢ ; aⱼ = σ(zⱼ) = 1 / (1 + exp(−zⱼ))</code><p class="hint">${t('Sans terme de biais dans cette démonstration.','No bias term in this demonstration.')}</p><code class="formula">L = (1 / 2) Σⱼ (aⱼ − yⱼ)²</code><p class="hint">${t('Deux sorties : la division par 2 donne la moyenne des erreurs quadratiques.','Two outputs: dividing by 2 gives the mean squared error.')}</p></div><div><h3>${t('Rétropropagation et mise à jour','Backpropagation and update')}</h3><code class="formula">δⱼ = (aⱼ − yⱼ) aⱼ(1 − aⱼ)<br>δᵢ = (Σⱼ wⱼᵢ δⱼ) aᵢ(1 − aᵢ)<br>∂L/∂wⱼᵢ = δⱼ aᵢ<br>w ← w − η · (1 / B) Σₛ ∇Lₛ</code><p class="hint">${t('B = 1, 2 ou 4. Tous les gradients d’un lot sont calculés avant de modifier ses poids. Ordre fixe des exemples pour une comparaison reproductible ; le SGD pratique utilise souvent un mélange aléatoire.','B = 1, 2 or 4. All gradients in a batch are computed before changing its weights. Samples use a fixed order for reproducible comparison; practical SGD often shuffles them.')}</p></div></div></section>
      <footer class="footer">${t('Une époque = un passage sur les quatre exemples. Une fréquence de mise à jour plus élevée ne garantit pas une meilleure convergence.','One epoch = one pass over all four samples. More frequent updates do not guarantee better convergence.')}</footer>
    </main>`;
    let weights, initial, pass, gradients, previousWeights, accumulated, epoch = 0, updates = 0, sampleIndex = -1;
    let observed = [], history = [], batchCount = 0, phase = 'forward', active = false, running = false, timer = null, selected = [1, 0];
    const rate = () => Number($('rate').value);
    const size = () => Number($('mode').value);
    const status = (title, description) => { $('statusTitle').textContent = title; $('statusText').textContent = description; };
    function controls() {
        ['mode','rate','seed','random','forward','compare'].forEach(id => $(id).disabled = active);
        $('train').disabled = running;
        $('step').disabled = running;
        $('pause').disabled = !active;
        $('pause').textContent = running ? t('Pause','Pause') : t('Reprendre','Resume');
    }
    function restore() {
        clearTimeout(timer); running = active = false;
        weights = M.clone(initial); pass = null; gradients = null; previousWeights = null; accumulated = M.zeros(weights);
        epoch = updates = batchCount = 0; sampleIndex = -1; observed = []; history = [M.evaluate(weights)]; phase = 'forward';
        $('observed').textContent = '—'; $('comparison').textContent = '';
        $('modeHint').textContent = t(`${4 / size()} mise(s) à jour par époque. Les gradients de ${size()} exemple(s) sont moyennés.`, `${4 / size()} update(s) per epoch. Gradients from ${size()} sample(s) are averaged.`);
        status(t('Prêt à explorer','Ready to explore'), t('Lancez une époque ou avancez étape par étape. Sélectionnez un neurone pour voir ses calculs.','Run an epoch or move step by step. Select a neuron to inspect its calculations.'));
        controls(); render();
    }
    function initialize() {
        if (!$('seed').checkValidity() || !$('rate').checkValidity()) { $('seed').reportValidity(); $('rate').reportValidity(); return; }
        initial = M.create(Number($('seed').value)); restore();
    }
    function begin() {
        active = true; sampleIndex = 0; observed = []; accumulated = M.zeros(weights); batchCount = 0; phase = 'forward'; gradients = null;
    }
    function advance() {
        if (!$('rate').checkValidity() || !$('seed').checkValidity()) { $('rate').reportValidity(); $('seed').reportValidity(); return; }
        if (!active) begin();
        const sample = M.data[sampleIndex];
        const label = t(`Exemple ${sampleIndex + 1}`, `Sample ${sampleIndex + 1}`);
        if (phase === 'forward') {
            pass = M.forward(weights, sample.input); gradients = null; phase = 'loss';
            status(`${label} · ${t('Propagation avant','Forward propagation')}`, `${t('Cible','Target')} ${vector(sample.target)} → ${t('Prédiction','Prediction')} ${vector(pass.output)}`);
        } else if (phase === 'loss') {
            observed[sampleIndex] = M.loss(pass.output, sample.target); phase = 'gradient';
            status(`${label} · ${t('Calcul de la perte','Loss calculation')}`, `L = ${fmt(observed[sampleIndex])}`);
        } else if (phase === 'gradient') {
            gradients = M.gradient(weights, pass, sample.target); M.accumulate(accumulated, gradients); batchCount++;
            phase = batchCount === size() ? 'update' : 'next';
            status(`${label} · ${t('Rétropropagation','Backpropagation')}`, t(`${batchCount}/${size()} gradient(s) accumulé(s). Les poids restent inchangés.`, `${batchCount}/${size()} gradient(s) accumulated. Weights are unchanged.`));
        } else if (phase === 'update') {
            previousWeights = M.clone(weights); M.update(weights, accumulated, rate(), batchCount); accumulated = M.zeros(weights); batchCount = 0; updates++; pass = M.forward(weights, sample.input); phase = 'next';
            status(t('Mise à jour des poids','Weight update'), t(`Les poids ont été modifiés avec le gradient moyen de ${size()} exemple(s).`, `Weights changed using the mean gradient of ${size()} sample(s).`));
        } else {
            sampleIndex++;
            if (sampleIndex === M.data.length) {
                epoch++; history.push(M.evaluate(weights)); sampleIndex = -1; active = running = false; gradients = null;
                $('observed').textContent = fmt(observed.reduce((a,b)=>a+b,0)/M.data.length);
                status(t('Époque terminée','Epoch complete'), t('La perte finale est recalculée sur les quatre exemples avec les poids finaux.','Final loss is recalculated on all four samples using the final weights.'));
            } else { phase = 'forward'; advance(); return; }
        }
        render(); controls();
    }
    function schedule() {
        if (!running) return;
        timer = setTimeout(() => { if (!running) return; advance(); schedule(); }, $('motion').checked ? 40 : 900 / Number($('speed').value));
    }
    function start() { if (!$('rate').checkValidity() || !$('seed').checkValidity()) { $('rate').reportValidity(); $('seed').reportValidity(); return; } if (!active) begin(); running = true; advance(); schedule(); controls(); }
    function inspect() {
        const [l,j] = selected;
        if (l === 0) { $('inspector').textContent = t(`Entrée ${j+1} · valeur : `, `Input ${j+1} · value: `) + (pass ? fmt(pass.activations[l][j]) : '—'); return; }
        const terms = pass ? weights[l-1][j].map((w,i)=>`${fmt(w,3)} × ${fmt(pass.activations[l-1][i],3)}`).join(' + ') : '—';
        const g = gradients ? vector(gradients[l-1][j]) : '—';
        $('inspector').textContent = `${t('Neurone','Neuron')} ${l === 1 ? t('caché','hidden') : t('de sortie','output')} ${j+1} · z = ${terms} ${pass ? '= '+fmt(pass.sums[l][j]) : ''} · a = ${pass ? fmt(pass.activations[l][j]) : '—'} · ${t('Poids entrants','Incoming weights')}: ${vector(weights[l-1][j])} · ${t('Dernier gradient calculé','Last computed gradient')} ∂L/∂w = ${g}${previousWeights ? ' · '+t('Poids avant la dernière mise à jour','Weights before the last update')+': '+vector(previousWeights[l-1][j]) : ''}`;
    }
    function render() {
        $('finalLoss').textContent = fmt(M.evaluate(weights)); $('epochs').textContent = epoch; $('updates').textContent = updates;
        const positions = M.sizes.map((n,l)=>Array.from({length:n},(_,j)=>[100+l*260,65+j*(200/(n-1))]));
        let svg = '';
        weights.forEach((layer,l)=>layer.forEach((row,j)=>row.forEach((w,i)=>{ const [x,y]=positions[l][i], [xx,yy]=positions[l+1][j]; svg += `<line class="edge" x1="${x}" y1="${y}" x2="${xx}" y2="${yy}" style="stroke:${w>=0?'#087f8c':'#bd5870'};stroke-width:${Math.min(6,1+Math.abs(w)*5)}"><title>w = ${fmt(w)}</title></line>`; })));
        positions.forEach((layer,l)=>{ svg += `<text class="layer-label" x="${layer[0][0]}" y="24">${[t('Entrées','Inputs'),t('Couche cachée','Hidden layer'),t('Sorties','Outputs')][l]}</text>`; layer.forEach(([x,y],j)=>{ const value = pass ? fmt(pass.activations[l][j],2) : '—'; svg += `<g class="node" role="button" tabindex="0" data-layer="${l}" data-index="${j}" aria-label="${t('Inspecter le neurone','Inspect neuron')} ${l+1}.${j+1}, ${value}"><circle cx="${x}" cy="${y}" r="25" fill="${l===0?'#e9f3f5':l===1?'#e5f3ef':'#fff0dd'}" stroke="${selected[0]===l&&selected[1]===j?'#cc7800':'#6c8c95'}"/><text x="${x}" y="${y+5}">${value}</text></g>`; }); });
        $('network').innerHTML = svg;
        $('samples').innerHTML = M.data.map((sample,i)=>{ const output=M.forward(weights,sample.input).output; return `<tr class="${i===sampleIndex?'current':''}"><th scope="row">${i+1}</th><td>${vector(sample.input)}</td><td>${vector(sample.target)}</td><td>${vector(output)}</td><td>${fmt(M.loss(output,sample.target))}</td><td>${observed[i]===undefined?'—':fmt(observed[i])}</td></tr>`; }).join('');
        const max = Math.max(...history, .001)*1.1;
        const points = history.map((v,i)=>`${40+i*420/Math.max(1,history.length-1)},${125-v/max*100}`).join(' ');
        $('chart').innerHTML = `<path d="M40 20V125H465" fill="none" stroke="#bacacf"/><polyline points="${points}" fill="none" stroke="#086b68" stroke-width="3"/>${history.map((v,i)=>`<circle cx="${40+i*420/Math.max(1,history.length-1)}" cy="${125-v/max*100}" r="3" fill="#086b68"><title>${i}: ${fmt(v)}</title></circle>`).join('')}<text x="0" y="24" font-size="11">${fmt(max,2)}</text><text x="30" y="145" font-size="11">0</text><text x="420" y="145" font-size="11">${epoch} ${t('époques','epochs')}</text>`;
        $('historyText').textContent = t(`Départ : ${fmt(history[0])} · Dernière époque : ${fmt(history[history.length-1])}.`, `Initial: ${fmt(history[0])} · Latest epoch: ${fmt(history[history.length-1])}.`);
        inspect();
    }
    $('network').addEventListener('click', e => { const node=e.target.closest('.node'); if(node){selected=[Number(node.dataset.layer),Number(node.dataset.index)];inspect();} });
    $('network').addEventListener('keydown', e => {if(e.key==='Enter'||e.key===' '){e.preventDefault();e.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}});
    $('train').addEventListener('click',start);
    $('step').addEventListener('click',advance);
    $('pause').addEventListener('click',()=>{running=!running;clearTimeout(timer);controls();if(running)schedule();});
    $('reset').addEventListener('click',restore);
    ['mode','rate','seed'].forEach(id=>$(id).addEventListener('change',initialize));
    $('random').addEventListener('click',()=>{const seed=new Uint32Array(1);crypto.getRandomValues(seed);$('seed').value=seed[0];initialize();});
    $('speed').addEventListener('input',()=>{$('speedValue').textContent=$('speed').value+'×';});
    $('motion').checked = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    $('forward').addEventListener('click',()=>{sampleIndex=0;pass=M.forward(weights,M.data[0].input);gradients=null;status(t('Prédiction seule · exemple 1','Prediction only · sample 1'),`${t('Perte de cet exemple','Loss for this sample')}: ${fmt(M.loss(pass.output,M.data[0].target))}. ${t('Les poids restent inchangés.','Weights are unchanged.')}`);render();});
    $('compare').addEventListener('click',()=>{
        if (!$('rate').checkValidity()) { $('rate').reportValidity(); return; }
        const results=[1,2,4].map(b=>{const w=M.clone(initial);for(let e=0;e<30;e++){let sum=M.zeros(w),n=0;M.data.forEach(sample=>{M.accumulate(sum,M.gradient(w,M.forward(w,sample.input),sample.target));n++;if(n===b){M.update(w,sum,rate(),n);sum=M.zeros(w);n=0;}});}return [b,M.evaluate(w)];});
        $('comparison').innerHTML=`<p>${t('Même graine, même taux, ordre fixe. La comparaison utilise des copies des poids initiaux.','Same seed, same rate, fixed order. Comparison uses copies of the initial weights.')}</p><table><thead><tr><th>${t('Méthode','Method')}</th><th>${t('Perte finale','Final loss')}</th><th>${t('Mises à jour','Updates')}</th></tr></thead><tbody>${results.map(([b,v])=>`<tr><td>${b===1?'SGD':b===2?t('Mini-lot','Mini-batch'):t('Lot complet','Full batch')}</td><td>${fmt(v)}</td><td>${30*4/b}</td></tr>`).join('')}</tbody></table>`;
    });
    initialize();
})();
