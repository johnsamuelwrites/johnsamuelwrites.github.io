/* Progressive enhancement: all slides and notes remain readable without JavaScript. */
(() => {
  'use strict';
  const slides = [...document.querySelectorAll('.slide')];
  const picker = document.querySelector('#slide-picker');
  const prev = document.querySelector('#previous');
  const next = document.querySelector('#next');
  const reading = document.querySelector('#reading');
  let index = 0;
  const fromHash = () => {
    const match = /^#slide(\d+)$/.exec(location.hash);
    return match ? Math.max(0, Math.min(slides.length - 1, Number(match[1]) - 1)) : 0;
  };
  function render() {
    index = fromHash();
    slides.forEach((slide, i) => slide.classList.toggle('active', i === index));
    picker.value = String(index);
    prev.disabled = index === 0;
    next.disabled = index === slides.length - 1;
    document.querySelector('#status').textContent = `${index + 1} / ${slides.length}`;
    document.title = `${index + 1} · ${slides[index].querySelector('h1').textContent} — Recherche`;
    if (document.body.classList.contains('reading')) slides[index].scrollIntoView();
    else window.scrollTo(0, 0);
  }
  function go(i) {
    i = Math.max(0, Math.min(slides.length - 1, i));
    if (i !== index || !location.hash) location.hash = `slide${i + 1}`;
  }
  prev.addEventListener('click', () => go(index - 1));
  next.addEventListener('click', () => go(index + 1));
  picker.addEventListener('change', () => go(Number(picker.value)));
  reading.addEventListener('click', () => {
    const enabled = document.body.classList.toggle('reading');
    document.body.classList.toggle('presenting', !enabled);
    reading.setAttribute('aria-pressed', String(enabled));
    slides.forEach(slide => { slide.querySelector('details').open = enabled; });
    render();
  });
  document.querySelector('#print').addEventListener('click', () => window.print());
  // Advance from slide content without interrupting reading or interaction.
  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    if (!document.body.classList.contains('presenting')) return;
    if (event.target.closest('.slide') !== slides[index]) return;
    if (event.target.closest('a,button,input,select,textarea,label,summary,details,[contenteditable],[role="button"],audio,video,iframe')) return;
    if (window.getSelection()?.toString()) return;
    go(index + 1);
  });

  document.addEventListener('keydown', event => {
    if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    const target = event.target;
    if (event.key === 'Escape') {
      const notes = slides[index].querySelector('details');
      if (notes.open && document.body.classList.contains('presenting')) {
        notes.open = false;
        notes.querySelector('summary').focus();
      }
      return;
    }
    if (target.closest('a,button,input,select,textarea,summary,[contenteditable],details[open]') || document.body.classList.contains('reading')) return;
    const moves = {ArrowRight: index + 1, ArrowLeft: index - 1, PageDown: index + 1, PageUp: index - 1, Home: 0, End: slides.length - 1};
    if (Object.hasOwn(moves, event.key)) {
      event.preventDefault();
      go(moves[event.key]);
    }
  });
  window.addEventListener('hashchange', render);
  document.body.classList.add('presenting');
  document.querySelector('.toolbar').hidden = false;
  render();
})();
