/* Progressive enhancement: without JavaScript every slide and its notes stack on one page. */
(() => {
  'use strict';
  const slides = [...document.querySelectorAll('.slide')];
  if (!slides.length) return;
  const bar = document.querySelector('.bar');
  const status = document.querySelector('#status');
  const reading = document.querySelector('#reading');
  const prev = document.querySelector('#previous');
  const next = document.querySelector('#next');
  let index = 0;

  const fromHash = () => {
    const m = /^#slide(\d+)$/.exec(location.hash);
    return m ? Math.max(0, Math.min(slides.length - 1, Number(m[1]) - 1)) : 0;
  };
  function render() {
    index = fromHash();
    slides.forEach((s, i) => s.classList.toggle('active', i === index));
    status.textContent = `${index + 1} / ${slides.length}`;
    prev.disabled = index === 0;
    next.disabled = index === slides.length - 1;
    const title = slides[index].querySelector('h1');
    if (title) document.title = `${index + 1} · ${title.textContent} — ${document.body.dataset.deck || ''}`;
    if (document.body.classList.contains('reading')) slides[index].scrollIntoView();
    else window.scrollTo(0, 0);
  }
  function go(i) {
    i = Math.max(0, Math.min(slides.length - 1, i));
    if (i !== index || !location.hash) location.hash = `slide${i + 1}`;
  }
  function toggleReading() {
    const on = document.body.classList.toggle('reading');
    document.body.classList.toggle('presenting', !on);
    reading.setAttribute('aria-pressed', String(on));
    slides.forEach(s => { const d = s.querySelector('details'); if (d) d.open = on; });
    render();
  }
  prev.addEventListener('click', () => go(index - 1));
  next.addEventListener('click', () => go(index + 1));
  reading.addEventListener('click', toggleReading);
  document.querySelector('#print').addEventListener('click', () => window.print());

  document.addEventListener('keydown', event => {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    const notes = slides[index].querySelector('details');
    if (event.key === 'Escape') { if (notes) notes.open = false; return; }
    if (event.target.closest('a,button,input,select,textarea,summary,[contenteditable]')) return;
    if (event.key === 'r') { toggleReading(); return; }
    if (document.body.classList.contains('reading')) return;
    const moves = { ArrowRight: index + 1, ArrowLeft: index - 1, PageDown: index + 1, PageUp: index - 1, ' ': index + 1, Home: 0, End: slides.length - 1 };
    if (Object.hasOwn(moves, event.key)) { event.preventDefault(); go(moves[event.key]); }
    else if (event.key === 'n' && notes) notes.open = !notes.open;
  });
  window.addEventListener('hashchange', render);
  document.body.classList.add('presenting');
  bar.hidden = false;
  render();
})();
