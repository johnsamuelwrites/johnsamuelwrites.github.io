const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function run(lang,rate){
 const elements=new Map(),timers=new Map();let timerId=0;
 function get(id){if(!elements.has(id))elements.set(id,{value:({rate,speed:'1'})[id]||'',textContent:'',innerHTML:'',disabled:false,listeners:{},addEventListener(e,f){this.listeners[e]=f;},setCustomValidity(s){this.validationMessage=s;},reportValidity(){},setAttribute(){},querySelectorAll(){return[];}});return elements.get(id);}
 vm.runInNewContext(fs.readFileSync('ui/perceptron/perceptron.js','utf8'),{document:{documentElement:{lang},getElementById:get},crypto:require('node:crypto').webcrypto,MouseEvent:class{},setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);}});
 const click=id=>get(id).listeners.click();
 const initial=get('samples').innerHTML;
 click('step');assert.equal(get('processed').textContent,1);assert.equal(get('epoch').textContent,0);
 for(let i=0;i<20000&&get('errors').textContent!==0;i++)click('step');
 assert.equal(get('errors').textContent,0,'Converges on seeded separable data');
 const trained=[get('w1').textContent,get('w2').textContent,get('bias').textContent];
 click('step');assert.ok(get('status').textContent.includes(lang==='fr'?'Convergé':'Converged'));
 click('reset');assert.equal(get('samples').innerHTML,initial);assert.equal(get('processed').textContent,0);
 click('train');assert.equal(get('rate').disabled,true);assert.equal(timers.size,1);
 click('reset');assert.equal(timers.size,0);assert.equal(get('rate').disabled,false);
 get('rate').value='bad';click('step');assert.equal(get('processed').textContent,0);assert.ok(get('rate').validationMessage);
 return trained;
}
assert.deepEqual(run('fr','0,45'),run('fr','0.45'));
run('en','0.1');
console.log('Passed: sample steps, convergence, repeatable reset, playback cancellation, comma/dot rates, invalid input, French and English.');
