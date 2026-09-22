/* Progressive enhancement: all slide content and reveals work without JS. */
(() => {
  'use strict';
  const slides = [...document.querySelectorAll('.slide')];
  const picker = document.querySelector('#slide-picker');
  const previous = document.querySelector('#previous');
  const next = document.querySelector('#next');
  const reading = document.querySelector('#reading');
  const steps = slides.map(() => 0);
  const reveals = slides.map(slide => [...slide.querySelectorAll('[data-reveal]')]);
  let index = 0;
  const isReading = () => document.body.classList.contains('reading');
  function render() {
    const match = /^#slide(\d+)$/.exec(location.hash);
    index = match ? Math.max(0, Math.min(slides.length - 1, Number(match[1]) - 1)) : 0;
    slides.forEach((slide, i) => {
      slide.classList.toggle('active', i === index);
      reveals[i].forEach((item, n) => {
        const pending = !isReading() && n >= steps[i];
        item.classList.toggle('pending', pending);
        if (pending) item.setAttribute('aria-hidden', 'true');
        else item.removeAttribute('aria-hidden');
      });
    });
    picker.value = String(index);
    previous.disabled = index === 0 && (isReading() || steps[index] === 0);
    next.disabled = index === slides.length - 1 && (isReading() || steps[index] === reveals[index].length);
    document.querySelector('#status').textContent = `${index + 1} / ${slides.length}`;
    const more = !isReading() && steps[index] < reveals[index].length;
    next.setAttribute('aria-label', more ? 'Reveal next idea' : 'Next slide');
    next.title = more ? 'Reveal next idea (Space or →)' : 'Next slide (Space or →)';
    document.title = `${index + 1} · ${slides[index].querySelector('h1').textContent} — Mindstone AI Meetup`;
  }
  function go(value) {
    const target = Math.max(0, Math.min(slides.length - 1, value));
    if (target === index) return;
    location.hash = `slide${target + 1}`;
  }
  function advance() {
    if (!isReading() && steps[index] < reveals[index].length) { steps[index]++; render(); }
    else go(index + 1);
  }
  function back() {
    if (!isReading() && steps[index] > 0) { steps[index]--; render(); }
    else go(index - 1);
  }
  previous.addEventListener('click', back);
  next.addEventListener('click', advance);
  picker.addEventListener('change', () => go(Number(picker.value)));
  reading.addEventListener('click', () => {
    const enabled = document.body.classList.toggle('reading');
    document.body.classList.toggle('presenting', !enabled);
    reading.setAttribute('aria-pressed', String(enabled));
    render();
    if (enabled) slides[index].scrollIntoView();
    else window.scrollTo(0, 0);
  });
  document.querySelector('#print').addEventListener('click', () => window.print());
  const fullscreen = document.querySelector('#fullscreen');
  fullscreen.hidden = !document.fullscreenEnabled;
  fullscreen.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch { fullscreen.textContent = 'Fullscreen unavailable'; }
  });
  document.addEventListener('fullscreenchange', () => {
    fullscreen.textContent = document.fullscreenElement ? 'Exit fullscreen' : 'Fullscreen';
  });
  const interactive = 'a,button,input,select,textarea,label,summary,details,[contenteditable],[role="button"],audio,video,iframe';
  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || isReading()) return;
    if (event.target.closest('.slide') !== slides[index] || event.target.closest(interactive) || window.getSelection()?.toString()) return;
    advance();
  });
  document.addEventListener('keydown', event => {
    if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    if (event.target.closest(interactive) || isReading()) return;
    if (['ArrowRight', 'PageDown', ' ', 'ArrowLeft', 'PageUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      if (['ArrowRight', 'PageDown', ' '].includes(event.key)) advance();
      else if (['ArrowLeft', 'PageUp'].includes(event.key)) back();
      else go(event.key === 'Home' ? 0 : slides.length - 1);
    }
  });
  window.addEventListener('hashchange', () => {
    render();
    if (isReading()) slides[index].scrollIntoView();
    else window.scrollTo(0, 0);
  });
  // Printed slides include every reveal, including in the accessibility tree.
  window.addEventListener('beforeprint', () => reveals.flat().forEach(item => item.removeAttribute('aria-hidden')));
  window.addEventListener('afterprint', render);
  document.body.classList.add('presenting');
  document.querySelector('.toolbar').hidden = false;
  render();
})();
