(() => {
    'use strict';
    const $ = id => document.getElementById(id), fr = document.documentElement.lang === 'fr';
    const t = (f,e) => fr ? f : e;
    const fmt = (v,n=3) => v.toLocaleString(fr?'fr-FR':'en-GB',{minimumFractionDigits:n,maximumFractionDigits:n});
    let weights=[0,0], bias=0, epoch=0, processed=0, index=0, selected=0, running=false, timer=null, data=[], seed=42;
    const rate = () => Number($('rate').value.trim().replace(',','.'));
    function validRate() {
        const valid=/^(?:[0-9]+(?:[.,][0-9]*)?|[.,][0-9]+)$/.test($('rate').value.trim()) && rate()>=.001 && rate()<=5;
        $('rate').setCustomValidity(valid?'':t('Saisissez un taux entre 0,001 et 5, par exemple 0,45.','Enter a rate between 0.001 and 5, for example 0.45.'));
        if(!valid)$('rate').reportValidity(); return valid;
    }
    const score = p => weights[0]*p.x1+weights[1]*p.x2+bias;
    const predict = p => score(p)>=0?1:0;
    const errors = () => data.filter(p=>predict(p)!==p.label).length;
    function generate() {
        let state=seed>>>0;
        const random=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296;};
        data=Array.from({length:20},()=>{const x1=random()*6-3,x2=random()*6-3;return{x1,x2,label:x2>.5*x1+.5?1:0};});
    }
    function stop() { clearTimeout(timer); timer=null; running=false; $('train').textContent=t('Démarrer','Start training'); $('rate').disabled=false; $('step').disabled=false; }
    function reset() {
        stop();weights=[0,0];bias=epoch=processed=index=selected=0;
        $('status').textContent=t('Prêt à explorer','Ready to explore');
        $('detail').textContent=t('Traitez un exemple ou lancez l’entraînement.','Process one sample or start training.');
        $('calculation').textContent=t('La dernière prédiction et les changements de poids apparaîtront ici.','The last prediction and weight changes will appear here.');render();
    }
    function step() {
        if(!validRate())return;
        if(errors()===0){stop();$('status').textContent=t('Convergé : tous les exemples sont correctement classés.','Converged: all samples are correctly classified.');return;}
        const p=data[index], before=[...weights,bias], z=score(p), prediction=predict(p), error=p.label-prediction;
        weights[0]+=rate()*error*p.x1;weights[1]+=rate()*error*p.x2;bias+=rate()*error;selected=index;processed++;index++;
        if(index===data.length){epoch++;index=0;}
        $('calculation').textContent=`z = ${fmt(before[0])} × ${fmt(p.x1)} + ${fmt(before[1])} × ${fmt(p.x2)} + ${fmt(before[2])} = ${fmt(z)}\nŷ = ${prediction} ; y = ${p.label} ; e = ${p.label} − ${prediction} = ${error}\nw₁ : ${fmt(before[0])} → ${fmt(weights[0])} (Δ = ${fmt(weights[0]-before[0])})\nw₂ : ${fmt(before[1])} → ${fmt(weights[1])} (Δ = ${fmt(weights[1]-before[1])})\nb : ${fmt(before[2])} → ${fmt(bias)} (Δ = ${fmt(bias-before[2])})`;
        $('status').textContent=t(`Exemple ${selected+1} · ${error?'Mise à jour':'Prédiction correcte'}`,`Sample ${selected+1} · ${error?'Weight update':'Correct prediction'}`);
        $('detail').textContent=error?t('Les poids et le biais ont été ajustés.','Weights and bias were adjusted.'):t('Les poids et le biais restent inchangés.','Weights and bias are unchanged.');
        if(errors()===0){stop();$('status').textContent=t('Convergé : tous les exemples sont correctement classés.','Converged: all samples are correctly classified.');}
        else if(epoch>=1000){stop();$('status').textContent=t('Limite de 1 000 époques atteinte.','Reached the 1,000-epoch limit.');}
        render();
    }
    const sx=x=>40+(x+3)/6*620, sy=y=>340-(y+3)/6*300;
    function boundary() {
        const [a,b]=weights, hits=[];
        const add=(x,y)=>{if(x>=-3-1e-9&&x<=3+1e-9&&y>=-3-1e-9&&y<=3+1e-9&&!hits.some(p=>Math.hypot(x-p[0],y-p[1])<1e-8))hits.push([x,y]);};
        if(Math.abs(b)>1e-12){add(-3,(-bias+3*a)/b);add(3,(-bias-3*a)/b);}
        if(Math.abs(a)>1e-12){add((-bias+3*b)/a,-3);add((-bias-3*b)/a,3);}
        if(hits.length<2)return '';
        return `<line class="boundary" x1="${sx(hits[0][0])}" y1="${sy(hits[0][1])}" x2="${sx(hits[1][0])}" y2="${sy(hits[1][1])}"/>`;
    }
    function inspect(){const p=data[selected];$('inspector').textContent=t(`Exemple ${selected+1} : `,`Sample ${selected+1}: `)+`x₁ = ${fmt(p.x1)} ; x₂ = ${fmt(p.x2)} ; ${t('cible','target')} = ${p.label} ; z = ${fmt(score(p))} ; ${t('prédiction actuelle','current prediction')} = ${predict(p)}`;}
    function render(){
        const count=errors();$('w1').textContent=fmt(weights[0]);$('w2').textContent=fmt(weights[1]);$('bias').textContent=fmt(bias);$('epoch').textContent=epoch;$('processed').textContent=processed;$('errors').textContent=count;$('accuracy').textContent=fmt((data.length-count)/data.length*100,1)+' %';
        let svg='';
        for(let i=-3;i<=3;i++)svg+=`<line class="grid" x1="${sx(i)}" y1="40" x2="${sx(i)}" y2="340"/><line class="grid" x1="40" y1="${sy(i)}" x2="660" y2="${sy(i)}"/><text class="plot-label" x="${sx(i)-5}" y="360">${i}</text><text class="plot-label" x="18" y="${sy(i)+4}">${i}</text>`;
        svg+=`<text class="plot-label" x="680" y="${sy(0)}">x₁</text><text class="plot-label" x="350" y="25">x₂</text>`+boundary();
        data.forEach((p,i)=>{const x=sx(p.x1),y=sy(p.x2),color=p.label?'#bd5870':'#087f8c';svg+=`<g class="sample" role="button" tabindex="0" data-index="${i}" aria-label="${t('Exemple','Sample')} ${i+1}, ${t('classe','class')} ${p.label}">${p.label?`<path class="marker" d="M${x} ${y-12}L${x+12} ${y}L${x} ${y+12}L${x-12} ${y}Z" fill="${color}" stroke="white"/>`:`<circle class="marker" cx="${x}" cy="${y}" r="11" fill="${color}" stroke="white"/>`}<text x="${x}" y="${y+4}">${i+1}</text></g>`;});svg+=`<circle id="selectionRing" cx="${sx(data[selected].x1)}" cy="${sy(data[selected].x2)}" r="16" fill="none" stroke="#cc7800" stroke-width="3" pointer-events="none"/>`;$('canvas').innerHTML=svg;
        $('network').innerHTML=[60,120,180].map((y,i)=>`<line x1="65" y1="${y}" x2="260" y2="120" stroke="${[weights[0],bias,weights[1]][i]>=0?'#087f8c':'#bd5870'}" stroke-width="${Math.min(6,1+Math.abs([weights[0],bias,weights[1]][i])*3)}"/><circle cx="65" cy="${y}" r="22" fill="#e5f3ef" stroke="#6c8c95"/><text x="65" y="${y+5}" text-anchor="middle">${['x₁','1','x₂'][i]}</text>`).join('')+'<circle cx="260" cy="120" r="30" fill="#fff0dd" stroke="#6c8c95"/><text x="260" y="125" text-anchor="middle">ŷ</text><text x="170" y="225" text-anchor="middle" font-size="12">z ≥ 0 → 1 ; z &lt; 0 → 0</text>';
        $('samples').innerHTML=data.map((p,i)=>`<tr class="${i===selected?'current':''}"><th scope="row">${i+1}</th><td>${fmt(p.x1)}</td><td>${fmt(p.x2)}</td><td>${p.label}</td><td>${fmt(score(p))}</td><td>${predict(p)}</td></tr>`).join('');inspect();
    }
    function schedule(){if(!running)return;timer=setTimeout(()=>{step();schedule();},800/Number($('speed').value));}
    $('train').addEventListener('click',()=>{if(running){stop();return;}if(!validRate())return;if(errors()===0){step();return;}running=true;$('train').textContent=t('Pause','Pause');$('rate').disabled=true;$('step').disabled=true;step();schedule();});
    $('step').addEventListener('click',()=>{stop();step();});$('reset').addEventListener('click',reset);
    $('rate').addEventListener('input',validRate);
    $('speed').addEventListener('input',()=>{$('speedLabel').textContent=$('speed').value+'×';if(running){clearTimeout(timer);schedule();}});
    $('newData').addEventListener('click',()=>{const values=new Uint32Array(1);crypto.getRandomValues(values);seed=values[0];generate();reset();});
    $('canvas').addEventListener('click',e=>{const node=e.target.closest('.sample');if(node){selected=Number(node.dataset.index);$('selectionRing').setAttribute('cx',sx(data[selected].x1));$('selectionRing').setAttribute('cy',sy(data[selected].x2));$('canvas').querySelectorAll('.sample').forEach(n=>n.setAttribute('aria-pressed',String(Number(n.dataset.index)===selected)));inspect();}});
    $('canvas').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();e.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}});
    generate();reset();
})();
