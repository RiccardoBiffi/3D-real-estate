'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const statusLabels = { published: 'Pubblicato', archived: 'Archiviato' };
  const modelLabels = { ready: '3D verificato', awaiting_plans: 'Ricostruzione da preparare', in_review: 'Modello in revisione', not_required: 'Scheda senza modello' };
  const euro = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
  const number = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 2 });
  let properties = [], propertyMap = new Map(), catalog = null, loadingCatalog = false;
  let current = null, currentMode = 0, frame = null, timer = null, toastTimer = null;
  let ready = false, startedAt = 0, unloaded = false, frameCleanup = null;
  const compact = matchMedia('(max-width: 760px)');
  const sceneKeys = new Set(['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', '+', '=', '-', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'Home', 'r', 'R', 't', 'T']);
  const text = value => value == null || value === '' ? 'Non indicato' : String(value);
  const numeric = value => typeof value === 'number' && Number.isFinite(value);
  const area = value => numeric(value) ? `${number.format(value)} m²` : text(value);
  const price = value => numeric(value) ? euro.format(value) : 'Prezzo non indicato';
  const list = value => Array.isArray(value) ? value.filter(v => typeof v === 'string') : [];
  const date = value => {
    if (!value) return 'Non verificato';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? 'Data non disponibile' : new Intl.DateTimeFormat('it-IT', { dateStyle: 'medium', timeZone: 'Europe/Rome' }).format(parsed);
  };
  function el(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }
  function sourceUrl(value) {
    if (typeof value !== 'string') return null;
    try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url : null; } catch (_) { return null; }
  }
  function modelPath(value) {
    return typeof value === 'string' && /^modelli\/[a-zA-Z0-9_-]+\.html$/.test(value) ? value : null;
  }
  function status(property) { return Object.hasOwn(statusLabels, property.availability?.status) ? property.availability.status : 'archived'; }
  function modelStatus(property) { return Object.hasOwn(modelLabels, property.model?.status) ? property.model.status : 'awaiting_plans'; }
  function views(property) { return Array.isArray(property?.model?.views) ? property.model.views.filter(v => v && typeof v.label === 'string') : []; }
  function modelReady(property) { return modelStatus(property) === 'ready' && modelPath(property.model?.path) && views(property).length > 0; }
  function modelLabel(property) {
    if (!modelReady(property)) return modelLabels[modelStatus(property)];
    return property.model.coverage === 'exterior_only' ? '3D · solo esterni' : property.model.coverage === 'partial' ? '3D parziale' : '3D verificato';
  }
  function missingVolumes(property) { return list(property.model?.unrenderedVolumes); }
  function coverageNotice(property) {
    const block = el('div', 'model-omissions');
    block.append(el('strong', '', property.model?.coverage === 'exterior_only' ? 'Ricostruzione dei soli esterni' : 'Modello 3D parziale'));
    block.append(el('p', '', 'Queste parti sono presenti nell’annuncio, ma non sono renderizzate nel modello:'));
    const ul = el('ul'); missingVolumes(property).forEach(label => ul.append(el('li', '', label))); block.append(ul); return block;
  }
  function propertyHref(property) { return `#${encodeURIComponent(property.id)}`; }
  function badge(content, kind) { return el('span', `status-badge ${kind}`, content); }
  function showToast(message) {
    clearTimeout(toastTimer); $('toast').textContent = message; $('toast').hidden = false;
    toastTimer = setTimeout(() => { $('toast').hidden = true; }, 5000);
  }
  function renderNavigation() {
    const host = $('property-nav-list'); host.replaceChildren();
    properties.forEach(property => {
      const link = el('a', 'property-nav'); link.href = propertyHref(property); link.dataset.nav = property.id;
      const icon = el('span', 'nav-house', '⌂'); icon.setAttribute('aria-hidden', 'true');
      const title = el('span'); title.append(el('strong', '', text(property.title)), el('small', '', text(property.locality)));
      link.append(icon, title); host.append(link);
    });
  }
  function matches(property) {
    const query = $('catalog-search').value.trim().toLocaleLowerCase('it-IT');
    const locality = $('locality-filter').value, availability = $('availability-filter').value, model = $('model-filter').value;
    const haystack = [property.title, property.address, property.locality].filter(Boolean).join(' ').toLocaleLowerCase('it-IT');
    return (!query || haystack.includes(query)) && (!locality || property.locality === locality) &&
      (availability === 'all' || status(property) === availability) &&
      (!model || modelStatus(property) === model);
  }
  function renderCatalog() {
    const filtered = properties.filter(matches), grid = $('property-grid'); grid.replaceChildren();
    filtered.forEach((property, index) => {
      const facts = property.facts || {}, card = el('a', 'property-card catalog-card'); card.href = propertyHref(property);
      const banner = el('div', 'catalog-card-banner');
      const preview = typeof property.model?.preview === 'string' && /^assets\/[a-z0-9-]+\.jpg$/.test(property.model.preview) ? property.model.preview : null;
      if (preview && modelReady(property)) {
        const image = el('img'); image.src = preview; image.alt = `Anteprima del modello di ${text(property.title)}`; image.loading = 'lazy'; banner.append(image);
      } else { banner.append(el('span', 'house-mark', '⌂'), el('span', 'card-locality', text(property.locality))); }
      const badges = el('div', 'card-badges'); badges.append(badge(statusLabels[status(property)], status(property)), badge(modelLabel(property), 'model'));
      banner.append(badges); card.append(banner);
      const info = el('div', 'card-info'); const heading = el('div'); heading.append(el('h3', '', text(property.title)), el('p', '', [property.locality, property.address].filter(Boolean).join(' · ')));
      info.append(heading, el('span', 'card-number', String(index + 1).padStart(2, '0'))); card.append(info);
      const summary = el('div', 'card-facts'); summary.append(el('strong', 'card-price', price(facts.priceEur)));
      if (numeric(facts.areaHabitableM2)) summary.append(el('span', '', `${area(facts.areaHabitableM2)} abitativi`));
      else if (numeric(facts.areaWalkableM2)) summary.append(el('span', '', `${area(facts.areaWalkableM2)} calpestabili`));
      else if (numeric(facts.areaCommercialM2)) summary.append(el('span', '', `${area(facts.areaCommercialM2)} commerciali · superficie interna da verificare`));
      if (numeric(facts.gardenM2)) summary.append(el('span', '', `Giardino ${area(facts.gardenM2)}`));
      if (facts.parking) summary.append(el('span', '', `Parcheggio: ${text(facts.parking)}`));
      card.append(summary);
      if (facts.description) card.append(el('p', 'card-description', text(facts.description)));
      const bottom = el('div', 'card-bottom'); bottom.append(el('span', '', `Controllo: ${date(property.availability?.checkedAt)}`), el('span', '', modelReady(property) ? 'Scheda e modello 3D →' : 'Leggi la scheda →')); card.append(bottom); grid.append(card);
    });
    $('catalog-empty').hidden = filtered.length > 0 || !catalog;
    const archived = properties.filter(p => status(p) === 'archived').length;
    $('catalog-summary').textContent = `${filtered.length} ${filtered.length === 1 ? 'casa' : 'case'} visualizzate · ${properties.length} nel catalogo · ${archived} in archivio`;
  }
  function detailBlock(title, values) {
    const section = el('section', 'detail-block'); section.append(el('h3', '', title)); const ul = el('ul');
    values.forEach(value => ul.append(el('li', '', value))); section.append(ul); return section;
  }
  function renderDetails(property) {
    const host = $('property-details'); host.replaceChildren(); const facts = property.facts || {};
    const heading = el('div', 'detail-heading'); heading.append(el('h2', '', 'La casa, nelle fonti disponibili'), el('strong', 'detail-price', price(facts.priceEur))); host.append(heading);
    const badges = el('div', 'detail-badges'); badges.append(badge(statusLabels[status(property)], status(property)), badge(modelLabel(property), 'model')); host.append(badges);
    if (facts.description) host.append(el('p', 'property-description', text(facts.description)));
    if (property.evidence?.note) host.append(el('p', 'surface-note', text(property.evidence.note)));
    const availability = el('div', 'availability-note'); availability.append(el('strong', '', `Ultimo controllo: ${date(property.availability?.checkedAt)}`));
    if (property.availability?.reason) availability.append(el('p', '', text(property.availability.reason)));
    if (status(property) === 'archived') availability.append(el('p', '', 'Nessuna fonte online fresca leggibile individuata nell’ultimo controllo. La scheda e gli eventuali modelli restano consultabili; l’archiviazione non certifica una vendita o un ritiro.'));
    host.append(availability);
    if (modelReady(property) && missingVolumes(property).length) host.append(coverageNotice(property));
    if (!modelReady(property)) {
      const pending = el('div', 'model-pending'); pending.append(el('h3', '', modelLabels[modelStatus(property)]));
      const notes = list(property.model?.notes);
      notes.forEach(note => pending.append(el('p', '', note)));
      if (!notes.length) pending.append(el('p', '', 'Ricostruzione delle parti documentate in preparazione. Le parti dell’annuncio non renderizzate saranno indicate nel modello parziale.'));
      host.append(pending);
    } else if (list(property.model?.notes).length) host.append(detailBlock('Fonti e stime della ricostruzione', list(property.model.notes)));
    const dl = el('dl', 'property-facts');
    const entries = [['Località', property.locality], ['Indirizzo', property.address], ['Superficie abitativa', area(facts.areaHabitableM2)], ['Superficie calpestabile', area(facts.areaWalkableM2)], ['Superficie commerciale', area(facts.areaCommercialM2)], ['Giardino', facts.gardenText || area(facts.gardenM2)], ['Terreno', area(facts.landM2)], ['Parcheggio', facts.parking], ['Piani', facts.floors], ['Camere', facts.bedrooms], ['Bagni', facts.bathrooms], ['Stato e lavori', facts.condition], ['Classe energetica', facts.energy], ['Autobus', facts.bus]];
    entries.forEach(([label, value]) => { const row = el('div'); row.append(el('dt', '', label), el('dd', '', text(value))); dl.append(row); }); host.append(dl);
    host.append(el('p', 'surface-note', facts.areaNotes ? text(facts.areaNotes) : 'Superfici abitative, calpestabili e commerciali sono riportate separatamente. Il dato commerciale non permette di ricavare la superficie interna.'));
    if (list(facts.highlights).length) host.append(detailBlock('Elementi rilevanti', list(facts.highlights)));
    if (list(facts.limitations).length) host.append(detailBlock('Requisiti mancanti e aspetti da confermare', list(facts.limitations)));
    const history = Array.isArray(property.historicalPrices) ? property.historicalPrices : [];
    if (history.length) {
      const rows = history.map(entry => typeof entry === 'object' && entry ? `${price(entry.priceEur ?? entry.price)} · ${date(entry.observedAt ?? entry.date ?? entry.checkedAt)}` : text(entry));
      host.append(detailBlock('Prezzi registrati', rows));
    }
    const sources = el('section', 'detail-block source-links'); sources.append(el('h3', '', 'Annunci e fonti')); const ul = el('ul');
    const urls = Array.isArray(property.sourceUrls) ? property.sourceUrls : [];
    urls.forEach(raw => {
      const url = sourceUrl(raw); if (!url) return;
      const li = el('li'), link = el('a', '', `${url.hostname.replace(/^www\./, '')} · Apri la fonte ↗`);
      link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; li.append(link); ul.append(li);
    });
    sources.append(ul.childElementCount ? ul : el('p', '', 'Collegamento pubblico non ancora identificato con certezza.')); host.append(sources);
    const plans = Array.isArray(property.model?.sourcePlans) ? property.model.sourcePlans : [];
    if (plans.length) {
      const section = el('section', 'detail-block source-links'); section.append(el('h3', '', 'Planimetrie della ricostruzione'));
      const links = el('ul'); plans.forEach(plan => {
        const url = sourceUrl(plan?.url); if (!url) return;
        const li = el('li'), link = el('a', '', `${text(plan.label)} ↗`); link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; li.append(link); links.append(li);
      }); section.append(links); host.append(section);
    }
    host.append(el('p', 'detail-disclaimer', 'Informazioni tratte dagli annunci e dalle verifiche indicate. Le ricostruzioni visuali non sono rilievi metrici, certificazioni o verifiche catastali.'));
  }
  function sceneWindow() { try { return frame?.contentWindow?.document ? frame.contentWindow : null; } catch (_) { return null; } }
  function setControlsEnabled(enabled) {
    document.querySelectorAll('.scene-action, .view-tab').forEach(button => { button.disabled = !enabled; }); $('view-select').disabled = !enabled;
  }
  function reflectMode(mode, updateUrl = true) {
    const count = views(current).length; if (!Number.isInteger(mode) || mode < 0 || mode >= count) return;
    currentMode = mode; $('view-select').value = String(mode);
    document.querySelectorAll('.view-tab').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.mode) === mode)));
    $('view-description').textContent = views(current)[mode].label;
    if (updateUrl && current) {
      const hash = `${propertyHref(current)}${mode ? `/${mode + 1}` : ''}`;
      if (location.hash !== hash) try { history.replaceState(null, '', hash); } catch (_) { /* Local file history can be restricted. */ }
    }
  }
  function chooseMode(mode) {
    const control = sceneWindow()?.__sceneControls;
    if (!ready || !control || !Number.isInteger(mode) || mode < 0 || mode >= views(current).length) return;
    try { control.setMode(mode); reflectMode(mode); } catch (_) { reportUnavailable('Il controllo del modello non è disponibile. Riprova aprendo la scheda.'); }
  }
  function sendKey(key) {
    const w = sceneWindow(); if (!ready || !w) return;
    if (/^[1-9]$/.test(key)) { chooseMode(Number(key) - 1); return; }
    if (key === 'r' || key === 'R') { chooseMode((currentMode + 1) % views(current).length); return; }
    if (key === '0' || key === 'Home') { chooseMode(0); return; }
    w.dispatchEvent(new w.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
  }
  function unloadModel() {
    clearInterval(timer); timer = null; frameCleanup?.(); frameCleanup = null;
    if (frame) {
      try {
        const w = sceneWindow(); w?.__sceneControls?.pause?.();
        const canvas = w?.document.querySelector('canvas');
        canvas?.getContext('webgl2')?.getExtension('WEBGL_lose_context')?.loseContext();
      } catch (_) { /* Removing the iframe releases the remaining resources. */ }
      frame.remove(); frame = null;
    }
    ready = false;
  }
  function reportUnavailable(message) {
    $('loading').hidden = true; $('viewer-message').hidden = false; $('viewer-message').textContent = message;
    ready = false; setControlsEnabled(false); clearInterval(timer); timer = null;
  }
  function pollScene() {
    if (!frame || unloaded) return;
    const w = sceneWindow(), state = w?.__sceneState, canvas = w?.document.querySelector('canvas');
    if (w?.document.body?.dataset.render === 'unavailable' || state?.contextLost) { reportUnavailable('Le informazioni della casa restano consultabili. Questo browser non riesce a mostrare il modello: verifica il supporto WebGL2 e l’accelerazione grafica.'); return; }
    if (state?.ready && state.frames > 0 && w?.__sceneControls?.setMode && canvas && canvas.style.opacity !== '0') {
      if (!ready) {
        ready = true; $('loading').hidden = true; $('viewer-message').hidden = true; setControlsEnabled(true);
        chooseMode(currentMode); updatePausedState();
      } else if (state.mode !== currentMode) reflectMode(state.mode);
    } else if (performance.now() - startedAt > 20000) reportUnavailable('Il modello non è pronto o il rendering è bloccato. La scheda resta disponibile; riapri la casa per riprovare.');
  }
  function openProperty(property, mode) {
    const sameModel = current?.id === property.id && frame;
    current = property; $('overview').hidden = true; $('back-to-catalog').hidden = false; $('property-details').hidden = false;
    $('main').classList.add('detail-open'); $('page-title').textContent = text(property.title);
    $('page-subtitle').textContent = [property.locality, property.address].filter(Boolean).join(' · '); document.title = `${text(property.title)} - Case in 3D`;
    renderDetails(property);
    const coverage = $('model-coverage'); coverage.replaceChildren();
    coverage.hidden = !modelReady(property) || !missingVolumes(property).length;
    if (!coverage.hidden) coverage.append(coverageNotice(property));
    if (!modelReady(property)) { leaveFullscreen(); unloadModel(); $('viewer').hidden = true; currentMode = 0; return; }
    $('viewer').hidden = false;
    if (sameModel) { if (ready) chooseMode(mode); else reflectMode(mode, false); return; }
    unloadModel(); currentMode = mode;
    $('view-buttons').replaceChildren(); $('view-select').replaceChildren();
    views(property).forEach((view, index) => {
      const button = el('button', 'view-tab', view.label); button.type = 'button'; button.dataset.mode = String(index);
      button.addEventListener('click', () => chooseMode(index)); $('view-buttons').append(button);
      const option = el('option', '', view.label); option.value = String(index); $('view-select').append(option);
    });
    reflectMode(mode, false); setControlsEnabled(false); $('viewer-message').hidden = true; $('loading').hidden = false;
    const newFrame = el('iframe'); frame = newFrame; frame.title = `${text(property.title)} - modello 3D interattivo`;
    frame.setAttribute('allowfullscreen', ''); frame.setAttribute('referrerpolicy', 'no-referrer');
    frame.addEventListener('load', () => {
      if (frame !== newFrame) return;
      const w = sceneWindow(); if (!w) return;
      const onKey = event => {
        if (event.key === 'Escape') leaveFullscreen();
        if (event.ctrlKey || event.metaKey || event.altKey || /INPUT|SELECT|TEXTAREA/.test(event.target.tagName) || event.target.isContentEditable) return;
        if (/^[1-9]$/.test(event.key) || ['r', 'R', '0', 'Home'].includes(event.key)) { event.preventDefault(); event.stopImmediatePropagation(); sendKey(event.key); }
      };
      const onError = () => reportUnavailable('Impossibile inizializzare il modello in questo browser. Le informazioni della casa restano consultabili.');
      w.addEventListener('keydown', onKey, true); w.addEventListener('error', onError);
      frameCleanup = () => { w.removeEventListener('keydown', onKey, true); w.removeEventListener('error', onError); };
      pollScene();
    });
    frame.addEventListener('error', () => { if (frame === newFrame) reportUnavailable('Il file del modello non è raggiungibile. Le informazioni della casa restano consultabili.'); });
    const revision = /^[a-f0-9]{64}$/.test(property.model.artifactSha256 || '') ? `?v=${property.model.artifactSha256.slice(0, 12)}` : '';
    frame.src = modelPath(property.model.path) + revision; startedAt = performance.now(); $('frame-host').replaceChildren(frame); timer = setInterval(pollScene, 300);
  }
  function route() {
    if (!catalog) return;
    const raw = location.hash.slice(1).split('/'); let id;
    try { id = decodeURIComponent(raw[0]); } catch (_) { id = ''; }
    let property = propertyMap.get(id);
    if (!property && ['aurisina', 'muggia'].includes(id)) property = properties.find(p => p.model?.path === `modelli/${id}.html`);
    const n = Number(raw[1]); const mode = property && Number.isInteger(n) && n >= 1 && n <= views(property).length ? n - 1 : 0;
    closeMenu(false);
    document.querySelectorAll('[data-nav]').forEach(link => { if (link.dataset.nav === (property?.id || 'panoramica')) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current'); });
    if (!property) {
      leaveFullscreen(); unloadModel(); current = null; currentMode = 0;
      $('overview').hidden = false; $('viewer').hidden = true; $('property-details').hidden = true; $('back-to-catalog').hidden = true;
      $('main').classList.remove('detail-open'); $('page-title').textContent = 'Esplora gli immobili';
      $('page-subtitle').textContent = 'Case a Trieste e dintorni, da ogni prospettiva.'; document.title = 'Case in 3D - Esplora gli immobili';
      if (id && id !== 'panoramica') showToast('La scheda richiesta non è presente nel catalogo.');
    } else openProperty(property, mode);
  }
  async function loadCatalog() {
    if (loadingCatalog) return; loadingCatalog = true; $('catalog-error').hidden = true;
    const controller = new AbortController(); const requestTimeout = setTimeout(() => controller.abort(), 20000);
    if (!catalog) $('catalog-summary').textContent = 'Caricamento del catalogo…';
    try {
      const response = await fetch('data/catalog.json', { cache: 'no-cache', credentials: 'omit', signal: controller.signal });
      if (!response.ok) throw new Error('Catalogo non raggiungibile');
      const payload = await response.json();
      if (payload.schemaVersion !== 1 || !Array.isArray(payload.properties)) throw new Error('Formato del catalogo non supportato');
      const seen = new Set(); const validated = payload.properties.filter(p => p && typeof p.id === 'string' && p.id && p.id !== 'panoramica' && !seen.has(p.id) && seen.add(p.id));
      if (validated.length !== payload.properties.length) throw new Error('Catalogo con identificatori mancanti o duplicati');
      catalog = payload; properties = validated; propertyMap = new Map(properties.map(property => [property.id, property]));
      const oldLocality = $('locality-filter').value; $('locality-filter').replaceChildren(el('option', '', 'Tutte le località')); $('locality-filter').firstChild.value = '';
      [...new Set(properties.map(p => p.locality).filter(v => typeof v === 'string' && v))].sort((a, b) => a.localeCompare(b, 'it')).forEach(locality => { const option = el('option', '', locality); option.value = locality; $('locality-filter').append(option); });
      if ([...$('locality-filter').options].some(o => o.value === oldLocality)) $('locality-filter').value = oldLocality;
      $('catalog-updated').textContent = `Catalogo aggiornato: ${date(payload.updatedAt)} · Controlli indicati nelle singole schede.`;
      renderNavigation(); renderCatalog(); route();
    } catch (_) {
      $('catalog-error-text').textContent = catalog ? 'Aggiornamento non riuscito. Restano visibili le informazioni già caricate con le loro date di controllo.' : 'Il catalogo non è raggiungibile o non è leggibile. Riprova tra poco. Questo errore non indica che gli immobili siano indisponibili.';
      $('catalog-error').hidden = false;
      if (!catalog) $('catalog-summary').textContent = 'Disponibilità non verificabile finché il catalogo non viene caricato.';
    } finally { clearTimeout(requestTimeout); loadingCatalog = false; }
  }
  function closeMenu(restoreFocus = true) {
    const wasOpen = $('sidebar').classList.contains('open'); $('sidebar').classList.remove('open'); $('menu-shade').hidden = true;
    $('open-menu').setAttribute('aria-expanded', 'false'); $('sidebar').inert = compact.matches; $('main').inert = false;
    if (wasOpen && restoreFocus) $('open-menu').focus();
  }
  function openMenu() { $('sidebar').inert = false; $('sidebar').classList.add('open'); $('menu-shade').hidden = false; $('open-menu').setAttribute('aria-expanded', 'true'); $('main').inert = true; $('close-menu').focus(); }
  function syncFullscreen() {
    const active = Boolean(document.fullscreenElement) || $('viewer').classList.contains('immersive'); $('fullscreen').setAttribute('aria-pressed', String(active));
    const label = active ? 'Esci dallo schermo intero' : 'Schermo intero'; $('fullscreen').setAttribute('aria-label', label); $('fullscreen').title = label; document.body.classList.toggle('is-immersive', active);
  }
  async function leaveFullscreen() { $('viewer').classList.remove('immersive'); if (document.fullscreenElement) try { await document.exitFullscreen(); } catch (_) {} syncFullscreen(); }
  async function toggleFullscreen() {
    if (document.fullscreenElement || $('viewer').classList.contains('immersive')) { await leaveFullscreen(); return; }
    if ($('viewer').requestFullscreen) try { await $('viewer').requestFullscreen(); } catch (_) { $('viewer').classList.add('immersive'); }
    else $('viewer').classList.add('immersive'); syncFullscreen();
  }
  async function copyLink() {
    if (location.protocol === 'file:') { showToast('Questa è una copia locale. Apri il sito pubblicato per condividere un collegamento pubblico.'); return; }
    const url = new URL(location.href); url.search = '';
    try { if (!navigator.clipboard?.writeText) throw new Error(); await navigator.clipboard.writeText(url.href); showToast('Collegamento copiato.'); }
    catch (_) { $('share-url').value = url.href; $('share-dialog').showModal(); $('share-url').select(); }
  }
  function updatePausedState() {
    const control = sceneWindow()?.__sceneControls; if (!control) return;
    const paused = document.hidden || $('help-dialog').open || $('share-dialog').open || $('sidebar').classList.contains('open');
    if (paused) control.pause?.(); else control.resume?.();
  }
  $('catalog-filters').addEventListener('submit', event => event.preventDefault());
  $('catalog-search').addEventListener('input', renderCatalog);
  ['locality-filter', 'availability-filter', 'model-filter'].forEach(id => $(id).addEventListener('change', renderCatalog));
  $('retry-catalog').addEventListener('click', loadCatalog);
  $('open-menu').addEventListener('click', () => { openMenu(); updatePausedState(); });
  $('close-menu').addEventListener('click', () => { closeMenu(); updatePausedState(); });
  $('menu-shade').addEventListener('click', () => { closeMenu(); updatePausedState(); });
  document.addEventListener('click', event => { const link = event.target.closest('a[href^="#"]'); if (link && link.hash === location.hash) { closeMenu(); updatePausedState(); } });
  $('view-select').addEventListener('change', event => chooseMode(Number(event.target.value)));
  $('reset').addEventListener('click', () => chooseMode(currentMode)); $('top-view').addEventListener('click', () => sendKey('T'));
  $('fullscreen').addEventListener('click', toggleFullscreen); document.addEventListener('fullscreenchange', syncFullscreen);
  $('share').addEventListener('click', copyLink); $('help').addEventListener('click', () => { $('help-dialog').showModal(); updatePausedState(); });
  $('close-help').addEventListener('click', () => $('help-dialog').close()); $('start-exploring').addEventListener('click', () => $('help-dialog').close()); $('close-share').addEventListener('click', () => $('share-dialog').close());
  [$('help-dialog'), $('share-dialog')].forEach(dialog => {
    dialog.addEventListener('close', updatePausedState);
    dialog.addEventListener('click', event => { if (event.target === dialog) { const bounds = dialog.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close(); } });
  });
  document.addEventListener('visibilitychange', updatePausedState);
  document.addEventListener('keydown', event => {
    const menuOpen = $('sidebar').classList.contains('open');
    if (menuOpen && event.key === 'Tab') {
      const links = [...$('sidebar').querySelectorAll('a,button')].filter(node => node.offsetParent !== null);
      if (event.shiftKey && document.activeElement === links[0]) { event.preventDefault(); links.at(-1).focus(); }
      else if (!event.shiftKey && document.activeElement === links.at(-1)) { event.preventDefault(); links[0].focus(); }
    }
    if ($('help-dialog').open || $('share-dialog').open) return;
    if (event.key === 'Escape') { closeMenu(); leaveFullscreen(); updatePausedState(); return; }
    if (!current || !ready || menuOpen || /INPUT|SELECT|TEXTAREA/.test(event.target.tagName) || event.target.isContentEditable || event.ctrlKey || event.metaKey || event.altKey) return;
    if (sceneKeys.has(event.key)) { event.preventDefault(); sendKey(event.key); }
  });
  compact.addEventListener('change', () => { closeMenu(false); updatePausedState(); });
  window.addEventListener('hashchange', () => { route(); updatePausedState(); });
  window.addEventListener('pagehide', () => { unloaded = true; unloadModel(); });
  window.addEventListener('pageshow', event => { if (event.persisted) { unloaded = false; route(); } });
  closeMenu(false); loadCatalog();
})();
