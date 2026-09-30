'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const models = {
    aurisina: {
      title: 'Villa Aurisina', subtitle: 'Aurisina · Ricostruzione 3D', file: 'modelli/aurisina.html',
      views: ['Esterno', 'Piano superiore', 'Piano terra', 'Cantina'],
      descriptions: ['Esterno completo', 'Taglio del piano superiore', 'Taglio del piano terra', 'Vista della cantina']
    },
    muggia: {
      title: 'Muggia - Via Mameli', subtitle: 'Via Mameli 14/F · Ricostruzione 3D', file: 'modelli/muggia.html',
      views: ['Esterno', 'Sottotetto', 'Piano rialzato', 'Seminterrato'],
      descriptions: ['Esterno completo', 'Taglio del sottotetto', 'Taglio del piano rialzato', 'Taglio del seminterrato e box']
    }
  };
  let current = null, currentMode = 0, frame = null, timer = null;
  let toastTimer = null, ready = false, startedAt = 0, unloaded = false;
  const compact = matchMedia('(max-width: 760px)');
  const sceneKeys = new Set(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-','0','1','2','3','4','Home','r','R','t','T']);

  function showToast(message) {
    clearTimeout(toastTimer);
    $('toast').textContent = message;
    $('toast').hidden = false;
    toastTimer = setTimeout(() => { $('toast').hidden = true; }, 5000);
  }
  function sceneWindow() {
    try { return frame?.contentWindow?.document ? frame.contentWindow : null; }
    catch (_) { return null; }
  }
  function setControlsEnabled(enabled) {
    document.querySelectorAll('.scene-action, .view-tab').forEach(b => { b.disabled = !enabled; });
    $('view-select').disabled = !enabled;
  }
  function reflectMode(mode, updateUrl = true) {
    currentMode = mode;
    $('view-select').value = String(mode);
    document.querySelectorAll('.view-tab').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.mode) === mode)));
    if (current) $('view-description').textContent = models[current].descriptions[mode];
    if (updateUrl && current) {
      const hash = `#${current}${mode ? `/${mode + 1}` : ''}`;
      if (location.hash !== hash) {
        try { history.replaceState(null, '', hash); } catch (_) { /* File URLs may restrict history replacement. */ }
      }
    }
  }
  function chooseMode(mode) {
    const control = sceneWindow()?.__sceneControls;
    if (!ready || !control || !Number.isInteger(mode) || mode < 0 || mode > 3) return;
    control.setMode(mode);
    reflectMode(mode);
  }
  function sendKey(key) {
    const w = sceneWindow();
    if (!ready || !w) return;
    w.dispatchEvent(new w.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
  }
  function unloadModel() {
    clearInterval(timer); timer = null;
    if (frame) {
      try {
        const w = sceneWindow();
        w?.__sceneControls?.pause();
        const canvas = w?.document.querySelector('canvas');
        canvas?.getContext('webgl2')?.getExtension('WEBGL_lose_context')?.loseContext();
      } catch (_) { /* Detaching the iframe also releases its rendering context. */ }
      frame.remove(); frame = null;
    }
    ready = false;
  }
  function reportUnavailable(message) {
    $('loading').hidden = true;
    $('viewer-message').hidden = false;
    $('viewer-message').textContent = message;
    ready = false; setControlsEnabled(false);
  }
  function pollScene() {
    if (!frame || unloaded) return;
    const w = sceneWindow();
    const bodyStatus = w?.document.body?.dataset.render;
    const state = w?.__sceneState;
    const canvas = w?.document.querySelector('canvas');
    const unavailable = bodyStatus === 'unavailable' || state?.contextLost || (ready && canvas?.style.opacity === '0');
    if (unavailable) {
      reportUnavailable('Il rendering 3D non è disponibile. Resta visibile l’anteprima. Prova un browser con WebGL2 e accelerazione grafica attiva.');
      return;
    }
    if (state?.ready && state.frames > 0 && canvas?.style.opacity === '1') {
      if (!ready) {
        ready = true;
        $('loading').hidden = true;
        $('viewer-message').hidden = true;
        setControlsEnabled(true);
        w.__sceneControls.setMode(currentMode);
        return;
      }
      if (state.mode !== currentMode) reflectMode(state.mode);
    } else if (performance.now() - startedAt > 20000) {
      reportUnavailable('Il modello impiega più tempo del previsto oppure WebGL2 non è disponibile. L’anteprima rimane visibile; prova un browser aggiornato con accelerazione grafica.');
    }
  }
  function openModel(id, mode) {
    if (id === current && frame) { if (ready) chooseMode(mode); else reflectMode(mode, false); return; }
    unloadModel();
    current = id; reflectMode(mode, false);
    const model = models[id];
    $('overview').hidden = true;
    $('viewer').hidden = false;
    $('page-title').textContent = model.title;
    $('page-subtitle').textContent = model.subtitle;
    document.title = `${model.title} - Case in 3D`;
    $('view-buttons').replaceChildren(); $('view-select').replaceChildren();
    model.views.forEach((label, index) => {
      const button = document.createElement('button');
      button.className = 'view-tab'; button.type = 'button'; button.dataset.mode = String(index);
      button.textContent = label; button.setAttribute('aria-pressed', String(index === mode));
      button.addEventListener('click', () => chooseMode(index));
      $('view-buttons').append(button);
      const option = document.createElement('option'); option.value = String(index); option.textContent = label;
      $('view-select').append(option);
    });
    reflectMode(mode, false); setControlsEnabled(false);
    $('viewer-message').hidden = true; $('loading').hidden = false;
    frame = document.createElement('iframe');
    frame.title = `${model.title} - modello 3D interattivo`;
    frame.setAttribute('allowfullscreen', '');
    frame.setAttribute('referrerpolicy', 'no-referrer');
    // Only the two trusted, supplied standalone pages are ever loaded here.
    // Keeping them in an iframe preserves their full original geometry and code.
    frame.addEventListener('load', () => {
      const w = sceneWindow();
      if (!w) return;
      w.addEventListener('keydown', event => {
        if (event.key === 'Escape') leaveFullscreen();
      });
      w.addEventListener('error', () => reportUnavailable('Impossibile inizializzare il rendering 3D in questo browser. L’anteprima statica rimane disponibile.'));
      pollScene();
    });
    if (window.__INLINE_MODELS__?.[id]) {
      const binary = atob(window.__INLINE_MODELS__[id]);
      frame.srcdoc = new TextDecoder().decode(Uint8Array.from(binary, c => c.charCodeAt(0)));
    } else { frame.src = model.file; }
    startedAt = performance.now();
    $('frame-host').replaceChildren(frame);
    timer = setInterval(pollScene, 300);
  }
  function readRoute() {
    const raw = location.hash.slice(1).split('/');
    const id = Object.prototype.hasOwnProperty.call(models, raw[0]) ? raw[0] : 'panoramica';
    const n = Number(raw[1]);
    return {id, mode: Number.isInteger(n) && n >= 1 && n <= 4 ? n - 1 : 0};
  }
  function route() {
    const {id, mode} = readRoute();
    closeMenu(false);
    document.querySelectorAll('[data-nav]').forEach(a => {
      if (a.dataset.nav === id) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
    if (id === 'panoramica') {
      leaveFullscreen(); unloadModel(); current = null;
      $('overview').hidden = false; $('viewer').hidden = true;
      $('page-title').textContent = 'Esplora gli immobili';
      $('page-subtitle').textContent = 'Due case, da ogni prospettiva.';
      document.title = 'Case in 3D - Esplora gli immobili';
    } else { openModel(id, mode); }
  }
  function closeMenu(restoreFocus = true) {
    const wasOpen = $('sidebar').classList.contains('open');
    $('sidebar').classList.remove('open'); $('menu-shade').hidden = true;
    $('open-menu').setAttribute('aria-expanded','false');
    $('sidebar').inert = compact.matches;
    $('main').inert = false;
    if (wasOpen && restoreFocus) $('open-menu').focus();
  }
  function openMenu() {
    $('sidebar').inert = false; $('sidebar').classList.add('open');
    $('menu-shade').hidden = false; $('open-menu').setAttribute('aria-expanded','true');
    $('main').inert = true; $('close-menu').focus();
  }
  function syncFullscreen() {
    const active = Boolean(document.fullscreenElement) || $('viewer').classList.contains('immersive');
    $('fullscreen').setAttribute('aria-pressed', String(active));
    const label = active ? 'Esci dallo schermo intero' : 'Schermo intero';
    $('fullscreen').setAttribute('aria-label', label); $('fullscreen').title = label;
    document.body.classList.toggle('is-immersive', active);
  }
  async function leaveFullscreen() {
    $('viewer').classList.remove('immersive');
    if (document.fullscreenElement) {
      try { await document.exitFullscreen(); } catch (_) { /* Already exited. */ }
    }
    syncFullscreen();
  }
  async function toggleFullscreen() {
    if (document.fullscreenElement || $('viewer').classList.contains('immersive')) { await leaveFullscreen(); return; }
    if ($('viewer').requestFullscreen) {
      try { await $('viewer').requestFullscreen(); }
      catch (_) { $('viewer').classList.add('immersive'); }
    } else { $('viewer').classList.add('immersive'); }
    syncFullscreen();
  }
  async function copyLink() {
    if (location.protocol === 'file:') {
      showToast('Questa è la copia locale. Per condividere un link pubblico occorre pubblicare il sito; puoi già condividere il file HTML.');
      return;
    }
    const url = new URL(location.href); url.search = '';
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(url.href);
      showToast('Collegamento copiato.');
    } catch (_) {
      $('share-url').value = url.href; $('share-dialog').showModal(); $('share-url').select();
    }
  }
  function updatePausedState() {
    const c = sceneWindow()?.__sceneControls;
    if (!c) return;
    const paused = document.hidden || $('help-dialog').open || $('share-dialog').open || $('sidebar').classList.contains('open');
    paused ? c.pause() : c.resume();
  }
  $('open-menu').addEventListener('click', () => { openMenu(); updatePausedState(); });
  $('close-menu').addEventListener('click', () => { closeMenu(); updatePausedState(); });
  $('menu-shade').addEventListener('click', () => { closeMenu(); updatePausedState(); });
  document.querySelectorAll('a[href^="#"]').forEach(link => link.addEventListener('click', () => {
    if (link.hash === location.hash) closeMenu();
    updatePausedState();
  }));
  $('view-select').addEventListener('change', e => chooseMode(Number(e.target.value)));
  $('reset').addEventListener('click', () => chooseMode(currentMode));
  $('top-view').addEventListener('click', () => sendKey('T'));
  $('fullscreen').addEventListener('click', toggleFullscreen);
  document.addEventListener('fullscreenchange', syncFullscreen);
  $('share').addEventListener('click', copyLink);
  $('help').addEventListener('click', () => { $('help-dialog').showModal(); updatePausedState(); });
  $('close-help').addEventListener('click', () => $('help-dialog').close());
  $('start-exploring').addEventListener('click', () => $('help-dialog').close());
  $('close-share').addEventListener('click', () => $('share-dialog').close());
  [$('help-dialog'),$('share-dialog')].forEach(d => {
    d.addEventListener('close', updatePausedState);
    d.addEventListener('click', e => { if (e.target === d) { const r = d.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) d.close(); } });
  });
  document.addEventListener('visibilitychange', updatePausedState);
  document.addEventListener('keydown', e => {
    const menuOpen = $('sidebar').classList.contains('open');
    if (menuOpen && e.key === 'Tab') {
      const links = [...$('sidebar').querySelectorAll('a,button')].filter(el => el.offsetParent !== null);
      if (e.shiftKey && document.activeElement === links[0]) { e.preventDefault(); links.at(-1).focus(); }
      else if (!e.shiftKey && document.activeElement === links.at(-1)) { e.preventDefault(); links[0].focus(); }
    }
    if ($('help-dialog').open || $('share-dialog').open) return;
    if (e.key === 'Escape') { closeMenu(); leaveFullscreen(); updatePausedState(); return; }
    if (!current || !ready || menuOpen || /INPUT|SELECT|TEXTAREA/.test(e.target.tagName) || e.target.isContentEditable || e.ctrlKey || e.metaKey || e.altKey) return;
    if (sceneKeys.has(e.key)) { e.preventDefault(); sendKey(e.key); }
  });
  compact.addEventListener('change', () => { closeMenu(false); updatePausedState(); });
  window.addEventListener('hashchange', () => { route(); updatePausedState(); });
  window.addEventListener('pagehide', () => { unloaded = true; unloadModel(); });
  window.addEventListener('pageshow', e => { if (e.persisted) { unloaded = false; route(); } });
  route();
})();
