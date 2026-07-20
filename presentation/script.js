(() => {
  const slides = [...document.querySelectorAll('.slide')];
  const prevButton = document.querySelector('#prev');
  const nextButton = document.querySelector('#next');
  const progress = document.querySelector('#progress');
  const counter = document.querySelector('#counter');
  const helpButton = document.querySelector('#help');
  const helpDialog = document.querySelector('#help-dialog');
  const helpClose = document.querySelector('#help-close');
  const deckWidth = 1280;
  const deckHeight = 720;

  const fromHash = Number.parseInt(location.hash.replace('#', ''), 10);
  let current = Number.isFinite(fromHash)
    ? Math.min(Math.max(fromHash - 1, 0), slides.length - 1)
    : 0;
  let touchX = null;

  const pad = (value) => String(value).padStart(2, '0');

  function fitDeck() {
    const scale = Math.min(window.innerWidth / deckWidth, window.innerHeight / deckHeight);
    document.documentElement.style.setProperty('--deck-scale', String(Math.max(scale, 0.1)));
  }

  function render({ updateHash = true } = {}) {
    slides.forEach((slide, index) => {
      const active = index === current;
      slide.classList.toggle('active', active);
      slide.classList.toggle('before', index < current);
      slide.setAttribute('aria-hidden', active ? 'false' : 'true');
    });
    prevButton.disabled = current === 0;
    nextButton.disabled = current === slides.length - 1;
    progress.style.width = `${((current + 1) / slides.length) * 100}%`;
    counter.textContent = `${pad(current + 1)} / ${pad(slides.length)}`;
    document.title = `${slides[current].dataset.title} — SolidHunt`;
    if (updateHash) history.replaceState(null, '', `#${current + 1}`);
  }

  function go(next) {
    const target = Math.min(Math.max(next, 0), slides.length - 1);
    if (target === current) return;
    current = target;
    render();
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  }

  function toggleOverview() {
    document.body.classList.toggle('overview');
    if (!document.body.classList.contains('overview')) {
      render();
    }
  }

  prevButton.addEventListener('click', () => go(current - 1));
  nextButton.addEventListener('click', () => go(current + 1));

  helpButton.addEventListener('click', () => helpDialog.showModal());
  helpClose.addEventListener('click', () => helpDialog.close());
  helpDialog.addEventListener('click', (event) => {
    if (event.target === helpDialog) helpDialog.close();
  });

  document.addEventListener('keydown', (event) => {
    if (helpDialog.open && event.key !== 'Escape') return;
    if (event.target.closest('a, button, dialog')) return;

    const key = event.key.toLowerCase();
    if (['arrowright', 'pagedown', ' ', 'enter'].includes(key)) {
      event.preventDefault();
      go(current + 1);
    } else if (['arrowleft', 'pageup', 'backspace'].includes(key)) {
      event.preventDefault();
      go(current - 1);
    } else if (key === 'home') {
      event.preventDefault();
      go(0);
    } else if (key === 'end') {
      event.preventDefault();
      go(slides.length - 1);
    } else if (key === 'f') {
      event.preventDefault();
      toggleFullscreen();
    } else if (key === 'o') {
      event.preventDefault();
      toggleOverview();
    } else if (key === '?') {
      helpDialog.showModal();
    }
  });

  document.addEventListener('touchstart', (event) => {
    touchX = event.changedTouches[0]?.clientX ?? null;
  }, { passive: true });

  document.addEventListener('touchend', (event) => {
    if (touchX == null) return;
    const endX = event.changedTouches[0]?.clientX ?? touchX;
    const delta = endX - touchX;
    touchX = null;
    if (Math.abs(delta) < 55) return;
    go(current + (delta < 0 ? 1 : -1));
  }, { passive: true });

  slides.forEach((slide, index) => {
    slide.addEventListener('click', (event) => {
      if (!document.body.classList.contains('overview')) return;
      if (event.target.closest('a')) return;
      current = index;
      document.body.classList.remove('overview');
      render();
    });
  });

  window.addEventListener('hashchange', () => {
    const hashIndex = Number.parseInt(location.hash.replace('#', ''), 10) - 1;
    if (Number.isFinite(hashIndex) && hashIndex >= 0 && hashIndex < slides.length) {
      current = hashIndex;
      render({ updateHash: false });
    }
  });

  window.addEventListener('resize', fitDeck, { passive: true });

  fitDeck();
  render({ updateHash: false });
})();
