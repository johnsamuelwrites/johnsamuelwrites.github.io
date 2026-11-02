'use strict';
(() => {
  const mode = document.body.dataset.mode;
  const $ = (id) => document.getElementById(id);
  const input = $('expression');
  const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------------------------------------------------------------------------
  // Texts (all user-visible strings live here)
  // ---------------------------------------------------------------------------
  const T = {
    emptyInfix: 'Saisissez une expression.',
    emptyPostfix: 'Saisissez une expression postfixée.',
    badNumber: p => `Nombre incorrect : ${p}`,
    badChar: c => `Caractère non pris en charge : ${c}`,
    badToken: t => `Jeton non reconnu : ${t}`,
    unary: t => `Opérande attendu avant « ${t} ». Le signe moins n’est accepté que devant un nombre (ex. -3).`,
    expectOp: t => `Opérateur attendu avant « ${t} ».`,
    strayClose: 'Parenthèse fermante sans correspondance.',
    unclosed: 'Parenthèse ouvrante non refermée.',
    incomplete: 'Expression incomplète : opérande manquant.',
    notEnough: (t, n) => `Pas assez d’opérandes pour « ${t} » (jeton ${n}).`,
    divZero: 'Division par zéro.',
    badResult: 'Résultat numérique invalide.',
    leftover: n => `Expression invalide : ${n} valeurs restent dans la pile.`,

    ready: 'Animation prête.',
    finished: 'Animation terminée.',
    invalid: 'Expression invalide.',
    fixIt: 'Corrigez l’expression pour lancer l’animation.',
    stepCounter: (a, b) => `Étape ${a} / ${b}`,
    stackCount: n => `${n} élément${n !== 1 ? 's' : ''}`,

    // infix → postfix
    iInit: 'Initialisation : pile d’opérateurs et sortie vides.',
    iOpen: 'Parenthèse ouvrante : empiler « ( ».',
    iPop: op => `Dépiler « ${op} » vers la sortie.`,
    iDiscard: 'Retirer « ( » sans l’ajouter à la sortie.',
    iPushOp: t => `Empiler l’opérateur « ${t} ».`,
    iOperand: t => `Opérande « ${t} » : l’ajouter directement à la sortie.`,
    iEndPop: op => `Fin du parcours : dépiler « ${op} » vers la sortie.`,
    iDone: s => `Conversion terminée : ${s}`,
    dOperand: 'Un opérande va toujours directement dans la sortie.',
    dOpen: 'Une parenthèse ouvrante est toujours empilée : elle marque le début d’un sous-calcul.',
    dClose: op => `On dépile jusqu’à « ( » : <code>${op}</code> part vers la sortie.`,
    dDiscard: 'Les parenthèses ne figurent pas dans le résultat : on retire « ( ».',
    dEmpty: 'Pile vide : l’opérateur est empilé sans comparaison.',
    dParenTop: 'Le sommet est « ( » : on ne dépile pas au-delà, l’opérateur est empilé.',
    dEnd: 'Plus aucun jeton à lire : on vide la pile vers la sortie.',
    dDoneInfix: 'La sortie contient maintenant l’expression postfixée complète.',
    dPop: (top, t, pTop, pIn) =>
      `prio(<code>${top}</code>) = ${pTop} ${pTop > pIn ? '&gt;' : '='} prio(<code>${t}</code>) = ${pIn}` +
      `${pTop === pIn ? ` et <code>${t}</code> est associatif à gauche` : ''} → <strong>dépiler</strong> <code>${top}</code>`,
    dKeep: (top, t, pTop, pIn) => pTop < pIn ?
      `prio(<code>${top}</code>) = ${pTop} &lt; prio(<code>${t}</code>) = ${pIn} → <strong>empiler</strong> <code>${t}</code>` :
      `prio(<code>${top}</code>) = prio(<code>${t}</code>) = ${pIn} et <code>${t}</code> est associatif à droite → <strong>empiler</strong> <code>${t}</code>`,

    // postfix evaluation
    pInit: 'Initialisation : pile d’opérandes vide.',
    pPush: t => `Empiler l’opérande ${t}.`,
    pPop2: (r, l) => `Dépiler ${r} (droite), puis ${l} (gauche).`,
    pCalc: (l, t, r, res) => `Calculer ${l} ${t} ${r} = ${res}, puis empiler le résultat.`,
    pDone: v => `Évaluation terminée. Résultat : ${v}.`,
    dPush: 'Un nombre est toujours empilé tel quel.',
    dOperands: (l, t, r) =>
      `<span class="slot">gauche&nbsp;: ${l}</span> <strong class="op">${t}</strong> <span class="slot">droite&nbsp;: ${r}</span> → calcul à effectuer`,
    dCalc: (l, t, r, res) => `${l} ${t} ${r} = <strong>${res}</strong> → le résultat est empilé.`,
    dDonePostfix: 'Il reste exactement une valeur sur la pile : c’est le résultat.',
    calcHint: 'Les résultats intermédiaires apparaissent ici dès le premier calcul.',
    calcFinal: 'Résultat final',
    calcLast: 'Dernier résultat intermédiaire',
    captionDone: 'Évaluation terminée : une seule valeur reste sur la pile.',
    captionRunning: 'Chaque opération produit une valeur intermédiaire, qui est ensuite empilée.',

    // predict mode
    quizToken: t => `jeton « ${t} »`,
    quizEnd: 'fin de l’expression',
    quizAfterPop: 'opérandes dépilés',
    quizQuestion: label => `Prochaine étape (${label}) : que faut-il faire ?`,
    quizWrong: 'Pas tout à fait. Regardez la pile et réessayez.',
    quizScore: (a, b) => `Score : ${a} / ${b} du premier coup`,
    choice: {
      infix: {
        out: 'Copier dans la sortie',
        push: 'Empiler sur la pile',
        pop: 'Dépiler vers la sortie',
        discard: 'Retirer la parenthèse'
      },
      postfix: {
        push: 'Empiler le nombre',
        pop2: 'Dépiler les deux opérandes',
        calc: 'Calculer et empiler le résultat'
      }
    }
  };

  // ---------------------------------------------------------------------------
  // Operators and tokenizer (shared by both pages)
  // ---------------------------------------------------------------------------
  const OPS = {
    '+': { p: 1, right: false, apply: (a, b) => a + b },
    '-': { p: 1, right: false, apply: (a, b) => a - b },
    '*': { p: 2, right: false, apply: (a, b) => a * b },
    '/': { p: 2, right: false, apply: (a, b) => a / b },
    '^': { p: 3, right: true, apply: (a, b) => a ** b }
  };
  const isOp = t => Object.hasOwn(OPS, t);
  const NUMBER = /^-?(?:\d+(?:\.\d*)?|\.\d+)$/;
  const fmt = v => Number.isInteger(v) ? String(v) : String(Number(v.toPrecision(12)));
  const escapeHTML = s => String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[c]));

  // Lexical scan of an infix expression; a « - » directly before a digit is a sign
  // when an operand is expected (start, after « ( » or after an operator).
  function scanInfix(s) {
    const arr = [];
    let i = 0;
    while (i < s.length) {
      const c = s[i];
      if (/\s/.test(c)) {
        i++;
        continue;
      }
      const prev = arr.at(-1);
      const operandExpected = prev === undefined || prev === '(' || isOp(prev);
      const signed = c === '-' && operandExpected && /[0-9.]/.test(s[i + 1] ?? '');
      if (/[0-9.]/.test(c) || signed) {
        let j = i + (signed ? 1 : 0);
        while (j < s.length && /[0-9.]/.test(s[j])) j++;
        const part = s.slice(i, j);
        if (!NUMBER.test(part)) throw Error(T.badNumber(part));
        arr.push(part);
        i = j;
      } else if (isOp(c) || c === '(' || c === ')') {
        arr.push(c);
        i++;
      } else {
        throw Error(T.badChar(c));
      }
    }
    return arr;
  }

  function checkInfixGrammar(arr) {
    let expectOperand = true;
    let balance = 0;
    arr.forEach(t => {
      if (expectOperand) {
        if (t === '(') {
          balance++;
        } else if (NUMBER.test(t)) {
          expectOperand = false;
        } else {
          throw Error(T.unary(t));
        }
      } else if (isOp(t)) {
        expectOperand = true;
      } else if (t === ')') {
        if (--balance < 0) throw Error(T.strayClose);
      } else {
        throw Error(T.expectOp(t));
      }
    });
    if (expectOperand) throw Error(T.incomplete);
    if (balance !== 0) throw Error(T.unclosed);
  }

  function tokenize(s, kind) {
    const infix = kind === 'infix';
    const arr = infix ? scanInfix(s) : s.trim().split(/\s+/).filter(Boolean);
    if (!arr.length) throw Error(infix ? T.emptyInfix : T.emptyPostfix);
    if (infix) {
      checkInfixGrammar(arr);
    } else {
      arr.forEach(t => {
        if (!isOp(t) && !NUMBER.test(t)) throw Error(T.badToken(t));
      });
    }
    return arr;
  }

  // ---------------------------------------------------------------------------
  // Frame builders. A frame carries what is displayed plus what just happened
  // (event) so that the renderer can animate it, and why (detail).
  // ---------------------------------------------------------------------------
  const shouldPop = (top, incoming) =>
    OPS[top].p > OPS[incoming].p || (OPS[top].p === OPS[incoming].p && !OPS[incoming].right);

  function buildInfix(s) {
    const tokens = tokenize(s, 'infix');
    const stack = [];
    const output = [];
    const frames = [];
    const add = (index, action, explanation, event = {}, detail = {}) => frames.push({
      tokens,
      index,
      action,
      explanation,
      stack: [...stack],
      output: [...output],
      event: { pushed: false, popped: [], out: false, ...event },
      detail: { html: '', ops: [], ...detail }
    });
    const pop = (index, explanation, html, ops) => {
      const op = stack.pop();
      output.push(op);
      add(index, 'pop', explanation(op), { popped: [op], out: true }, { html: html(op), ops });
    };

    add(-1, 'init', T.iInit);
    tokens.forEach((t, i) => {
      if (t === '(') {
        stack.push(t);
        add(i, 'push', T.iOpen, { pushed: true }, { html: T.dOpen });
      } else if (t === ')') {
        while (stack.length && stack.at(-1) !== '(') {
          pop(i, T.iPop, T.dClose, [stack.at(-1)]);
        }
        stack.pop();
        add(i, 'discard', T.iDiscard, { popped: ['('] }, { html: T.dDiscard });
      } else if (isOp(t)) {
        while (stack.length && isOp(stack.at(-1)) && shouldPop(stack.at(-1), t)) {
          const top = stack.at(-1);
          pop(i, T.iPop, () => T.dPop(top, t, OPS[top].p, OPS[t].p), [top, t]);
        }
        const top = stack.at(-1);
        let html = T.dEmpty;
        if (top === '(') html = T.dParenTop;
        else if (top !== undefined) html = T.dKeep(top, t, OPS[top].p, OPS[t].p);
        stack.push(t);
        add(i, 'push', T.iPushOp(t), { pushed: true }, { html, ops: top && isOp(top) ? [t, top] : [t] });
      } else {
        output.push(t);
        add(i, 'out', T.iOperand(t), { out: true }, { html: T.dOperand });
      }
    });
    while (stack.length) {
      pop(tokens.length, T.iEndPop, () => T.dEnd, []);
    }
    add(tokens.length, 'done', T.iDone(output.join(' ')), {}, { html: T.dDoneInfix });
    return frames;
  }

  function buildEval(s) {
    const tokens = tokenize(s, 'postfix');
    const stack = [];
    const calculations = [];
    const frames = [];
    const add = (index, action, explanation, event = {}, detail = {}) => frames.push({
      tokens,
      index,
      action,
      explanation,
      stack: stack.map(fmt),
      output: [],
      calculations: calculations.map(c => ({ ...c })),
      event: { pushed: false, popped: [], out: false, ...event },
      detail: { html: '', ops: [], ...detail }
    });

    add(-1, 'init', T.pInit);
    tokens.forEach((t, i) => {
      if (!isOp(t)) {
        stack.push(Number(t));
        add(i, 'push', T.pPush(t), { pushed: true }, { html: T.dPush });
        return;
      }
      if (stack.length < 2) throw Error(T.notEnough(t, i + 1));
      const right = stack.pop();
      const left = stack.pop();
      add(i, 'pop2', T.pPop2(fmt(right), fmt(left)), { popped: [fmt(right), fmt(left)] },
        { html: T.dOperands(fmt(left), t, fmt(right)) });
      if (t === '/' && right === 0) throw Error(T.divZero);
      const result = OPS[t].apply(left, right);
      if (!Number.isFinite(result)) throw Error(T.badResult);
      stack.push(result);
      calculations.push({ left: fmt(left), operator: t, right: fmt(right), result: fmt(result) });
      add(i, 'calc', T.pCalc(fmt(left), t, fmt(right), fmt(result)), { pushed: true },
        { html: T.dCalc(fmt(left), t, fmt(right), fmt(result)) });
    });
    if (stack.length !== 1) throw Error(T.leftover(stack.length));
    add(tokens.length, 'done', T.pDone(fmt(stack[0])), {}, { html: T.dDonePostfix });
    return frames;
  }

  // ---------------------------------------------------------------------------
  // Rendering and animation
  // ---------------------------------------------------------------------------
  let frames = [];
  let position = 0;
  let timer = null;
  let predict = false;
  let pending = null;
  const score = { ok: 0, total: 0 };

  // Moves a copy of an element (or a rectangle) towards a target element, or fades it out.
  function fly(text, from, to) {
    if (!from) return;
    const a = from instanceof Element ? from.getBoundingClientRect() : from;
    const ghost = document.createElement('div');
    ghost.className = 'fly';
    ghost.textContent = text;
    Object.assign(ghost.style, {
      left: `${a.left}px`,
      top: `${a.top}px`,
      width: `${a.width}px`,
      height: `${a.height}px`
    });
    document.body.append(ghost);
    let end = { transform: 'translate(0, -24px) scale(0.8)', opacity: 0 };
    if (to) {
      const b = to.getBoundingClientRect();
      const dx = b.left + b.width / 2 - (a.left + a.width / 2);
      const dy = b.top + b.height / 2 - (a.top + a.height / 2);
      end = { transform: `translate(${dx}px, ${dy}px) scale(0.85)`, opacity: 0.35 };
    }
    ghost.animate([{ transform: 'translate(0, 0) scale(1)', opacity: 1 }, end], {
      duration: 380,
      easing: 'ease-in-out'
    }).onfinish = () => ghost.remove();
  }

  function animateFlights(f, popped) {
    const tokenEl = document.querySelector('#tokens .current');
    const topCell = $('stack').firstElementChild;
    const tokenText = f.tokens[f.index];
    if (mode === 'infix') {
      const lastOut = $('output').lastElementChild;
      if (f.action === 'out') fly(tokenText, tokenEl, lastOut);
      else if (f.action === 'push') fly(tokenText, tokenEl, topCell);
      else if (f.action === 'pop') popped.forEach(p => fly(p.text, p.rect, lastOut));
      else if (f.action === 'discard') popped.forEach(p => fly(p.text, p.rect, null));
    } else if (f.action === 'push') {
      fly(tokenText, tokenEl, topCell);
    } else if (f.action === 'pop2') {
      popped.forEach(p => fly(p.text, p.rect, $('detail')));
    } else if (f.action === 'calc') {
      fly(f.stack.at(-1), $('detail'), topCell);
    }
  }

  function renderPostfixOutput(f, done, fx) {
    const calculations = f.calculations || [];
    const last = calculations.length - 1;
    $('output').innerHTML = calculations.length ?
      `<div class="calculation-summary"><span class="hint">${done ? T.calcFinal : T.calcLast}</span><strong class="result">${escapeHTML(calculations[last].result)}</strong></div>` +
      `<ol class="calculation-history">${calculations.map((c, i) => {
        const cls = i === last ? `latest${fx && f.action === 'calc' ? ' arrived' : ''}` : '';
        return `<li class="${cls}"><span class="calc-expression">${escapeHTML(c.left)} ${escapeHTML(c.operator)} ${escapeHTML(c.right)}</span><span aria-hidden="true"> = </span><strong>${escapeHTML(c.result)}</strong></li>`;
      }).join('')}</ol>` :
      `<span class="hint">${T.calcHint}</span>`;
    $('output-caption').textContent = done ? T.captionDone : T.captionRunning;
  }

  // `animate` is true only when moving forward by exactly one step.
  function render(animate = false) {
    if (!frames.length) return;
    const f = frames[position];
    const fx = animate && !reducedMotion();
    const done = position === frames.length - 1;

    // Remember the cells about to disappear so they can fly away.
    const popped = fx ? [...$('stack').children].slice(0, f.event.popped.length)
      .map(el => ({ text: el.textContent, rect: el.getBoundingClientRect() })) : [];

    $('tokens').innerHTML = f.tokens.map((t, i) =>
      `<span class="token ${i === f.index ? 'current' : i < f.index ? 'processed' : 'pending'}" ${i === f.index ? 'aria-current="step"' : ''}>${escapeHTML(t)}</span>`).join('');
    // Top of the stack first: the base stays anchored at the bottom of the panel.
    $('stack').innerHTML = [...f.stack].reverse().map((v, i) =>
      `<div class="stack-cell${i === 0 ? ' top' : ''}${i === 0 && fx && f.event.pushed ? ' pushed' : ''}">${escapeHTML(v)}</div>`).join('');
    if (mode === 'infix') {
      const last = f.output.length - 1;
      $('output').innerHTML = f.output.map((v, i) =>
        `<span class="token${i === last && fx && f.event.out ? ' arrived' : ''}">${escapeHTML(v)}</span>`).join('');
    } else {
      renderPostfixOutput(f, done, fx);
    }
    $('detail').innerHTML = f.detail.html;
    document.querySelectorAll('.prio-line [data-ops]').forEach(row => {
      const ops = row.dataset.ops.split(' ');
      row.classList.toggle('active', f.detail.ops.some(o => ops.includes(o)));
    });
    $('explanation').textContent = f.explanation;
    $('step-counter').textContent = T.stepCounter(position + 1, frames.length);
    $('slider').max = frames.length - 1;
    $('slider').value = position;
    $('previous').disabled = position === 0;
    $('next').disabled = done;
    $('play').disabled = done && !timer;
    $('restart').disabled = position === 0;
    $('stack-count').textContent = T.stackCount(f.stack.length);
    $('pause').disabled = !timer;
    $('status').textContent = done ? T.finished : T.ready;

    if (fx) animateFlights(f, popped);
  }

  function pause() {
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
    $('pause').disabled = true;
  }

  // ---------------------------------------------------------------------------
  // Predict mode
  // ---------------------------------------------------------------------------
  const quizActions = () => Object.keys(T.choice[mode]);

  function updateScore() {
    const el = $('quiz-score');
    el.textContent = T.quizScore(score.ok, score.total);
    el.classList.toggle('hidden', score.total === 0);
  }

  function hideQuiz() {
    pending = null;
    $('quiz').classList.add('hidden');
  }

  function ask(next) {
    pause();
    const set = quizActions();
    const k = set.indexOf(next.action);
    // Keep the correct answer and two distractors, in a fixed order.
    const options = set.filter((_, i) => set.length <= 3 || i !== (k + 2) % set.length);
    const label = next.action === 'calc' ? T.quizAfterPop :
      next.index < next.tokens.length ? T.quizToken(next.tokens[next.index]) : T.quizEnd;
    pending = { action: next.action, first: true };
    score.total++;
    $('quiz-question').textContent = T.quizQuestion(label);
    $('quiz-choices').innerHTML = options.map(o =>
      `<button type="button" data-choice="${o}">${escapeHTML(T.choice[mode][o])}</button>`).join('');
    $('quiz-feedback').textContent = '';
    $('quiz').classList.remove('hidden');
    updateScore();
    render();
    $('quiz-choices').firstElementChild.focus();
  }

  function answer(choice, button) {
    if (!pending) return;
    if (choice === pending.action) {
      if (pending.first) score.ok++;
      hideQuiz();
      updateScore();
      position++;
      render(true);
    } else {
      pending.first = false;
      button.disabled = true;
      $('quiz-feedback').textContent = T.quizWrong;
    }
  }

  // ---------------------------------------------------------------------------
  // Playback
  // ---------------------------------------------------------------------------
  function advance() {
    if (pending) return;
    if (position < frames.length - 1) {
      const next = frames[position + 1];
      if (predict && quizActions().includes(next.action)) {
        ask(next);
        return;
      }
      position++;
      render(true);
    } else {
      pause();
      render();
    }
  }

  function play() {
    if (timer !== null || pending) return;
    if (position === frames.length - 1) position = 0;
    advance();
    if (!pending && position < frames.length - 1) {
      timer = setInterval(advance, Number($('speed').value));
    }
    $('pause').disabled = !timer;
  }

  function jumpTo(newPosition) {
    pause();
    hideQuiz();
    position = newPosition;
    render();
  }

  function compile() {
    pause();
    hideQuiz();
    score.ok = 0;
    score.total = 0;
    updateScore();
    $('error').classList.add('hidden');
    const other = $('other-page');
    try {
      frames = (mode === 'infix' ? buildInfix : buildEval)(input.value);
      position = 0;
      if (other) {
        other.href = `evaluation-postfixee.html?expr=${encodeURIComponent(frames.at(-1).output.join(' '))}`;
        other.classList.remove('hidden');
      }
      render();
    } catch (e) {
      frames = [];
      other?.classList.add('hidden');
      $('error').textContent = e.message;
      $('error').classList.remove('hidden');
      $('status').textContent = T.invalid;
      $('tokens').innerHTML = '';
      $('stack').innerHTML = '';
      $('output').innerHTML = '';
      $('detail').innerHTML = '';
      $('explanation').textContent = T.fixIt;
      $('step-counter').textContent = '—';
      ['play', 'previous', 'next', 'restart', 'pause'].forEach(id => {
        $(id).disabled = true;
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Events
  // ---------------------------------------------------------------------------
  $('compile').addEventListener('click', compile);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') compile();
  });
  document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => {
    input.value = button.dataset.example;
    compile();
  }));
  $('play').addEventListener('click', play);
  $('pause').addEventListener('click', pause);
  $('previous').addEventListener('click', () => jumpTo(Math.max(0, position - 1)));
  $('next').addEventListener('click', () => {
    pause();
    advance();
  });
  $('restart').addEventListener('click', () => jumpTo(0));
  $('slider').addEventListener('input', e => jumpTo(Number(e.target.value)));
  $('speed').addEventListener('change', () => {
    if (timer !== null) {
      pause();
      timer = setInterval(advance, Number($('speed').value));
      $('pause').disabled = false;
    }
  });
  $('predict').addEventListener('change', e => {
    predict = e.target.checked;
    if (!predict) hideQuiz();
  });
  $('quiz-choices').addEventListener('click', e => {
    const button = e.target.closest('[data-choice]');
    if (button) answer(button.dataset.choice, button);
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) pause();
  });
  document.addEventListener('keydown', e => {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    const tag = e.target.tagName;
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(tag)) return;
    if (e.key === 'ArrowRight') $('next').click();
    else if (e.key === 'ArrowLeft') $('previous').click();
    else if (e.key === 'Home') $('restart').click();
    else if (e.key === ' ' && tag !== 'BUTTON' && tag !== 'A') (timer ? $('pause') : $('play')).click();
    else return;
    e.preventDefault();
  });

  const shared = new URLSearchParams(window.location.search).get('expr');
  if (shared) input.value = shared;
  compile();
})();
