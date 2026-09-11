'use strict';
// Stage 4A display: affine warp, canvas paint, lazy frame cache + LRU,
// water-masked smoothing, zoom-aware gather, Leaflet overlay, map readout.
// Pure geometry/gather/cache helpers are node-testable; mount() drives the DOM.

const { BATHY_ROWS, BATHY_COLS, BATHY_CELLS, LAND_U16 } = require('./tables');
const waveMath = require('./wave-math');
const ui = require('./ui');

const SCALE_FT = 6.0;
const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
// CARTO's keyless basemaps now stamp "API KEY REQUIRED" on the tiles, so the muted
// look is achieved by desaturating standard OSM tiles (see .leaflet-tile-pane in index.html).
const TILE_ATTRIBUTION = '&copy; OpenStreetMap contributors';
const TILE_MAX_ZOOM = 19;
const OVERLAY_OPACITY = ui.OVERLAY_OPACITY;
const PLAY_INTERVAL_MS = 333;
const FRAME_MINUTES = 15;
const FRAME_CACHE_MAX = 8;

// ---- affine warp ----
function gridToLonlat(warp, col, row) {
  const a = warp.grid_to_lonlat, b = warp.grid_to_lonlat_row;
  return { lon: a[0] * col + a[1] * row + a[2], lat: b[0] * col + b[1] * row + b[2] };
}

function lonlatToGrid(warp, lon, lat) {
  const a = warp.lonlat_to_grid, b = warp.lonlat_to_grid_row;
  return { col: a[0] * lon + a[1] * lat + a[2], row: b[0] * lon + b[1] * lat + b[2] };
}

function displayBounds(warp) {
  return {
    west: warp.corners.nw[0], north: warp.corners.nw[1],
    east: warp.corners.se[0], south: warp.corners.se[1],
  };
}

function pickDisplayDims(bounds, targetW) {
  const W = targetW || 384;
  const midLat = ((bounds.north + bounds.south) / 2) * Math.PI / 180;
  const wM = (bounds.east - bounds.west) * Math.cos(midLat) * 111320;
  const hM = (bounds.north - bounds.south) * 110574;
  return { W, H: Math.max(2, Math.round(W * hM / wM)) };
}

// Raster width for a container: client px * dpr, clamped to [lo, hi].
function targetWidth(clientWidth, dpr, lo = 512, hi = 1536) {
  const px = Math.round((Number(clientWidth) || 0) * (Number(dpr) || 1));
  return Math.max(lo, Math.min(hi, px));
}

function bilinearSample(field, cols, rows, colF, rowF) {
  const cx = colF < 0 ? 0 : colF > cols - 1 ? cols - 1 : colF;
  const ry = rowF < 0 ? 0 : rowF > rows - 1 ? rows - 1 : rowF;
  const c0 = Math.floor(cx), r0 = Math.floor(ry);
  const c1 = Math.min(cols - 1, c0 + 1), r1 = Math.min(rows - 1, r0 + 1);
  const fc = cx - c0, fr = ry - r0;
  const v00 = field[r0 * cols + c0], v01 = field[r0 * cols + c1];
  const v10 = field[r1 * cols + c0], v11 = field[r1 * cols + c1];
  return (v00 * (1 - fc) + v01 * fc) * (1 - fr) + (v10 * (1 - fc) + v11 * fc) * fr;
}

// Gather the UTM field into a lat/lng-uniform display raster (row 0 = north).
function gatherRaster(field, warp, W, H) {
  const [cols, rows] = warp.dims;
  const A = warp.lonlat_to_grid, Ar = warp.lonlat_to_grid_row;
  const b = displayBounds(warp);
  const out = new Float32Array(W * H);
  for (let i = 0; i < H; i++) {
    const lat = b.north + (b.south - b.north) * ((i + 0.5) / H);
    for (let j = 0; j < W; j++) {
      const lon = b.west + (b.east - b.west) * ((j + 0.5) / W);
      const colF = A[0] * lon + A[1] * lat + A[2];
      const rowF = Ar[0] * lon + Ar[1] * lat + Ar[2];
      out[i * W + j] = bilinearSample(field, cols, rows, colF, rowF);
    }
  }
  return out;
}

// roller / Hmax definition (post-Ks, pre-0.6d), pinned in golden.json.
function hmaxFt(hsAfterKsFt, dLocalFt) {
  return Math.min(1.67 * hsAfterKsFt, 0.78 * dLocalFt);
}

// One hour/step frame: capped Hs field + post-Ks/depth/period for readout + lake-max stats.
function computeFrame(tables, entry, opts = {}) {
  const gamma = opts.gamma || 0;
  const capped = opts.out || new Float64Array(BATHY_CELLS);
  const afterKs = opts.outAfterKs || new Float64Array(BATHY_CELLS);
  const ts = opts.outTs || new Float64Array(BATHY_CELLS);
  waveMath.computeField(tables, entry.speedMph, entry.dirTrueDeg, capped, {
    blend: true, t_eff_s: entry.tEffH * 3600, gamma, outAfterKs: afterKs, outTs: ts,
  });
  let maxIdx = 0, maxHs = 0;
  for (let i = 0; i < capped.length; i++) {
    if (capped[i] > maxHs) { maxHs = capped[i]; maxIdx = i; }
  }
  const depthMax = tables.depth[maxIdx] * 0.25;
  const rollerFt = hmaxFt(afterKs[maxIdx], depthMax);
  const L_m = (waveMath.dispersionFast(ts[maxIdx], depthMax * waveMath.FT)).L_m;
  return { capped, afterKs, ts, maxHs, maxIdx, rollerFt, hlMax: (afterKs[maxIdx] * waveMath.FT) / L_m };
}

// ---- colour scale (land / flat water transparent) ----
function paintRaster(ctx, raster, W, H) {
  const img = ctx.createImageData(W, H);
  const px = img.data;
  for (let k = 0, p = 0; k < raster.length; k++, p += 4) {
    const c = ui.colorForHs(raster[k]);
    px[p] = c[0]; px[p + 1] = c[1]; px[p + 2] = c[2]; px[p + 3] = c[3];
  }
  ctx.putImageData(img, 0, 0);
}

// ---- display smoothing (display-only; stats stay on the raw field) ----
const landFields = new WeakMap();
const landFracCache = new Map();

// Land fraction per display pixel: bilinear gather of a binary land field.
function landMaskRaster(warp, tables, W, H) {
  let field = landFields.get(tables);
  if (!field) {
    field = new Float32Array(tables.depth.length);
    for (let i = 0; i < field.length; i++) field[i] = tables.depth[i] === LAND_U16 ? 1 : 0;
    landFields.set(tables, field);
  }
  const key = `${W}x${H}`;
  let frac = landFracCache.get(key);
  if (!frac) { frac = gatherRaster(field, warp, W, H); landFracCache.set(key, frac); }
  return frac;
}

// Separable masked blur. Land sources (landFrac = 1) get zero weight, so the
// shoreline fringe is removed; weights are normalized per pixel. Pure-land
// pixels are forced to exactly 0. Inputs are never mutated.
function smoothRaster(raster, landFrac, W, H, radius = 2) {
  const r = Math.max(1, radius | 0);
  const n = 2 * r;
  const kern = new Float64Array(n + 1);
  kern[0] = 1;
  for (let i = 1; i <= n; i++) kern[i] = (kern[i - 1] * (n - i + 1)) / i;
  const tmp = new Float32Array(W * H);
  const out = new Float32Array(W * H);
  for (let i = 0; i < H; i++) {
    const row = i * W;
    for (let j = 0; j < W; j++) {
      let sw = 0, sv = 0;
      if (j >= r && j < W - r) {
        const j0 = row + j - r;
        for (let k = 0; k <= n; k++) {
          const w = kern[k] * (1 - landFrac[j0 + k]);
          sw += w; sv += w * raster[j0 + k];
        }
      } else {
        for (let k = -r; k <= r; k++) {
          let jj = j + k;
          if (jj < 0) jj = 0; else if (jj >= W) jj = W - 1;
          const w = kern[k + r] * (1 - landFrac[row + jj]);
          sw += w; sv += w * raster[row + jj];
        }
      }
      tmp[row + j] = sw > 0 ? sv / sw : 0;
    }
  }
  for (let i = 0; i < H; i++) {
    const row = i * W;
    const inner = i >= r && i < H - r;
    for (let j = 0; j < W; j++) {
      let sw = 0, sv = 0;
      if (inner) {
        for (let k = -r; k <= r; k++) {
          const v = row + k * W + j;
          const w = kern[k + r] * (1 - landFrac[v]);
          sw += w; sv += w * tmp[v];
        }
      } else {
        for (let k = -r; k <= r; k++) {
          let ii = i + k;
          if (ii < 0) ii = 0; else if (ii >= H) ii = H - 1;
          const v = ii * W + j;
          const w = kern[k + r] * (1 - landFrac[v]);
          sw += w; sv += w * tmp[v];
        }
      }
      const v = row + j;
      out[v] = landFrac[v] >= 1 ? 0 : (sw > 0 ? sv / sw : 0);
    }
  }
  return out;
}

// ---- lazy frame cache (LRU) ----
function cacheKey(idx, pinIdx, W, H) {
  return `${idx}|${pinIdx}|${W}x${H}`;
}

// Rough memory of one cached frame: the encoded data URL is the payload.
function frameBytes(entry) {
  if (!entry) return 0;
  return (entry.url ? entry.url.length * 2 : 0) + 64;
}

function createFrameCache(opts = {}) {
  const max = opts.max || FRAME_CACHE_MAX;
  const sizeOf = opts.sizeOf || frameBytes;
  const map = new Map();
  let bytes = 0, peakBytes = 0;
  return {
    get(key) {
      if (!map.has(key)) return undefined;
      const v = map.get(key);
      map.delete(key); map.set(key, v); // touch -> most recently used
      return v;
    },
    has(key) { return map.has(key); },
    set(key, entry) {
      if (map.has(key)) { bytes -= sizeOf(map.get(key)); map.delete(key); }
      map.set(key, entry);
      bytes += sizeOf(entry);
      while (map.size > max) {
        const oldest = map.keys().next().value;
        bytes -= sizeOf(map.get(oldest));
        map.delete(oldest);
      }
      if (bytes > peakBytes) peakBytes = bytes;
      return entry;
    },
    clear() { map.clear(); bytes = 0; },
    keys() { return [...map.keys()]; },
    get size() { return map.size; },
    get bytes() { return bytes; },
    get peakBytes() { return peakBytes; },
    get max() { return max; },
  };
}

// ---- browser app ----
async function mount(deps) {
  const { tables: T, wind } = deps;
  const note = document.getElementById('note');
  const noteMsg = document.getElementById('note-msg');
  const noteRetry = document.getElementById('note-retry');
  const bootEl = document.getElementById('boot');
  const bootText = document.getElementById('boot-text');
  const bootBar = document.getElementById('boot-bar');
  const body = document.body;
  const canvas = document.getElementById('field');
  const cctx = canvas.getContext('2d');
  const scrub = document.getElementById('scrub');
  const nowTick = document.getElementById('now-tick');
  const label = document.getElementById('hour-label');
  const windEl = document.getElementById('wind-info');
  const frameEl = document.getElementById('frame-info');
  const verdictRange = document.getElementById('verdict-range');
  const verdictPeak = document.getElementById('verdict-peak');
  const comfortChip = document.getElementById('comfort-chip');
  const windBadge = document.getElementById('wind-badge');
  const badgeText = document.getElementById('wind-badge-text');
  const badgeArrow = document.getElementById('wind-badge-arrow');
  const playBtn = document.getElementById('play');
  const playLabel = document.getElementById('play-label');
  const card = document.getElementById('card');
  const mapEl = document.getElementById('map');
  const readout = document.getElementById('readout');
  // Panel chrome must not double as a map tap: without this, clicking the card's X (or the
  // wind badge) also fires Leaflet's map click, which re-drops the pin and reopens the card.
  ['click', 'mousedown', 'touchstart', 'dblclick'].forEach((t) => {
    card.addEventListener(t, (e) => e.stopPropagation());
    windBadge.addEventListener(t, (e) => e.stopPropagation());
  });
  const q = new URLSearchParams(location.search);
  const point = wind.pointFromQuery(location.search);
  const DEFAULT_HINT = 'tap the lake for a local readout';

  const reducedMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  if (reducedMotion) body.classList.add('reduced-motion');
  const dpr = () => window.devicePixelRatio || 1;

  let tables = null, warp = null, gamma = 0, features = [], centroid = null, bounds = null;

  // ---- loading skeleton + retry toast ----
  function boot(text, frac) {
    bootText.textContent = text;
    if (frac == null) bootEl.classList.add('indeterminate');
    else { bootEl.classList.remove('indeterminate'); bootBar.style.width = `${Math.round(frac * 100)}%`; }
    bootEl.classList.remove('hidden');
  }
  function hideBoot() { bootEl.classList.add('hidden'); }
  function showNote(msg, retryFn) {
    noteMsg.textContent = msg;
    note.style.display = 'flex';
    noteRetry.hidden = !retryFn;
    noteRetry.onclick = retryFn || null;
  }
  function hideNote() { note.style.display = 'none'; noteRetry.onclick = null; }

  function fetchJson(url) {
    return fetch(url).then((r) => {
      if (!r.ok) throw new Error(`${url} HTTP ${r.status}`);
      return r.json();
    });
  }

  // Streaming fetch driven by Content-Length; null fraction = indeterminate.
  async function fetchProgress(url, onProgress) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${url} HTTP ${res.status}`);
    const total = Number(res.headers.get('Content-Length'));
    if (!res.body || !Number.isFinite(total) || total <= 0) {
      const buf = await res.arrayBuffer();
      onProgress(null);
      return buf;
    }
    const reader = res.body.getReader();
    const chunks = [];
    let got = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      got += value.length;
      onProgress(got / total);
    }
    const merged = new Uint8Array(got);
    let off = 0;
    for (const c of chunks) { merged.set(c, off); off += c.length; }
    return merged.buffer;
  }

  // Decoded map data is loaded once; a wind retry never refetches these.
  async function loadMapData() {
    if (tables) return;
    boot('Loading wave map…', null);
    const meta = await fetchJson('public/meta.v1.json');
    const bins = await fetchProgress('public/tables.v1.bin', (f) => boot('Loading wave map…', f));
    const w = await fetchJson('public/warp.v1.json');
    const spots = await fetchJson('public/spots.v1.json');
    tables = T.decodeTables(bins);
    warp = w;
    gamma = meta.gamma_deg;
    features = spots.features || [];
    centroid = ui.centroidOfCorners(meta.wgs84_corners || w.corners);
    bounds = displayBounds(warp);
  }

  const legendBar = document.getElementById('legend-bar');
  if (legendBar) {
    const stops = ui.HS_STOPS.map(([v, r, g, b]) => `rgb(${r}, ${g}, ${b}) ${(v / 6 * 100).toFixed(1)}%`);
    legendBar.style.background = `linear-gradient(90deg, ${stops.join(', ')})`;
  }

  function isShoreCell(lat, lon) {
    const g = lonlatToGrid(warp, lon, lat);
    const r0 = Math.round(g.row), c0 = Math.round(g.col);
    const d = Math.ceil(ui.SHORE_RADIUS_M / 100);
    for (let r = r0 - d; r <= r0 + d; r++) {
      if (r < 0 || r >= BATHY_ROWS) continue;
      for (let c = c0 - d; c <= c0 + d; c++) {
        if (c < 0 || c >= BATHY_COLS) continue;
        if (tables.depth[r * BATHY_COLS + c] !== LAND_U16) continue;
        const ll = gridToLonlat(warp, c, r);
        if (ui.haversineM(lat, lon, ll.lat, ll.lon) <= ui.SHORE_RADIUS_M) return true;
      }
    }
    return false;
  }

  function sectorInfo(lat, lon) {
    return { name: ui.sectorFor(lat, lon, centroid), shore: isShoreCell(lat, lon) };
  }

  const scratch = {
    out: new Float64Array(BATHY_CELLS),
    afterKs: new Float64Array(BATHY_CELLS),
    ts: new Float64Array(BATHY_CELLS),
  };

  let map = null, overlay = null;
  let frames = [];
  let stepMin = 15;
  let cur = 0;
  let pinned = null;
  let pin = null;
  let playing = false;
  let timer = null;
  let builtMs = 0;
  let bootHidden = false;
  let readoutTimer = null;
  let mapReady = false;

  function setupMap() {
    if (mapReady) return;
    mapReady = true;
  map = L.map('map', {
    zoomControl: true,
    zoomSnap: 0.1,      // fractional zoom levels
    zoomDelta: 0.5,     // half-step on the +/- buttons
    touchZoom: true,
    zoomAnimation: true,
    wheelPxPerZoomLevel: 90,
  });
  L.tileLayer(TILE_URL, {
    maxZoom: TILE_MAX_ZOOM, attribution: TILE_ATTRIBUTION, detectRetina: true,
  }).addTo(map);
  const llBounds = [[bounds.south, bounds.west], [bounds.north, bounds.east]];
  overlay = L.imageOverlay('data:image/gif;base64,R0lGODlhAQABAAAAACw=',
    llBounds, { opacity: OVERLAY_OPACITY }).addTo(map);
  // Auto-fit the lake edge-to-edge: no static setView/zoom, padding keeps the
  // east/west shorelines off the viewport edges on portrait phones.
  const fitLake = () => map.fitBounds(llBounds, { padding: [12, 12], maxZoom: 12 });
  fitLake();
  // The flex layout can settle after the first paint; refit once the container is real.
  requestAnimationFrame(() => map.invalidateSize());
  window.addEventListener('load', () => { fitLake(); map.invalidateSize(); scheduleRegather(); }, { once: true });
  map.on('click', (ev) => {
    if (!placePin(ev.latlng)) {
      dismissPin();
      flashReadout('land — no wave data here');
    }
  });
  map.on('zoomend', scheduleRegather);
  const d0 = desiredDims();
  canvas.width = d0.W;
  canvas.height = d0.H;
  }

  // Zoom-aware raster width: the lake's projected on-screen width grows with zoom,
  // and the viewport can grow on resize. Clamp via targetWidth.
  function overlayScreenWidth() {
    const z = map.getZoom();
    const nw = map.project(L.latLng(bounds.north, bounds.west), z);
    const se = map.project(L.latLng(bounds.south, bounds.east), z);
    const w = Math.abs(se.x - nw.x);
    return Number.isFinite(w) && w > 0 ? w : (mapEl.clientWidth || 384);
  }
  function desiredDims() {
    const css = Math.max(mapEl.clientWidth || 384, overlayScreenWidth());
    return pickDisplayDims(bounds, targetWidth(css, dpr()));
  }
  const frameCache = createFrameCache({ max: FRAME_CACHE_MAX });

  function frameFor(idx) {
    if (!frames.length) return null;
    const W = canvas.width, H = canvas.height;
    const pinIdx = pinned ? pinned.i : -1;
    const key = cacheKey(idx, pinIdx, W, H);
    const hit = frameCache.get(key);
    if (hit) return hit;
    const t0 = performance.now();
    const f = computeFrame(tables, frames[idx], { gamma, ...scratch });
    const raster = gatherRaster(f.capped, warp, W, H);
    const landFrac = landMaskRaster(warp, tables, W, H);
    const smooth = smoothRaster(raster, landFrac, W, H);
    paintRaster(cctx, smooth, W, H);
    const url = canvas.toDataURL();
    const p10Ft = ui.p10(f.capped);
    const peak = gridToLonlat(warp, f.maxIdx % BATHY_COLS, Math.floor(f.maxIdx / BATHY_COLS));
    const stats = {
      maxHs: f.maxHs, maxIdx: f.maxIdx, rollerFt: f.rollerFt, hlMax: f.hlMax,
      p10Ft, peakLat: peak.lat, peakLon: peak.lon, entry: frames[idx],
    };
    const pinVals = pinned ? { hsKs: f.afterKs[pinned.i], ts: f.ts[pinned.i] } : null;
    const ms = performance.now() - t0;
    builtMs += ms;
    body.dataset.precomputeMs = builtMs.toFixed(1);
    body.dataset.frameMs = ms.toFixed(1);
    return frameCache.set(key, { url, stats, pinVals });
  }

  function setCardField(name, value) {
    const el = card.querySelector(`[data-field="${name}"] .v`);
    if (el) el.textContent = value;
  }

  function updatePinned() {
    if (!pinned || !frames.length) return;
    const built = frameFor(cur);
    if (!built || !built.pinVals) return;
    const d = tables.depth[pinned.i] * 0.25;
    const hsKs = built.pinVals.hsKs, ts = built.pinVals.ts;
    const hs = Math.min(hsKs, 0.6 * d);
    const hm = hmaxFt(hsKs, d);
    const L_m = waveMath.dispersionFast(ts, d * waveMath.FT).L_m;
    const spot = ui.nameSpot(pinned.latlng.lat, pinned.latlng.lng, features,
      sectorInfo(pinned.latlng.lat, pinned.latlng.lng));
    setCardField('spot', ui.describePin(spot));
    setCardField('coords', `${pinned.latlng.lat.toFixed(4)}, ${pinned.latlng.lng.toFixed(4)}`);
    setCardField('depth', `${d.toFixed(1)} ft`);
    setCardField('hs', `${hs.toFixed(1)} ft`);
    setCardField('hmax', `${hm.toFixed(1)} ft`);
    setCardField('hl', (hsKs * waveMath.FT / L_m).toFixed(3));
    card.dataset.spot = spot.name || spot.kind;
  }

  function placePin(latlng) {
    pause();
    const g = lonlatToGrid(warp, latlng.lng, latlng.lat);
    const c = Math.round(g.col), r = Math.round(g.row);
    if (c < 0 || r < 0 || c >= BATHY_COLS || r >= BATHY_ROWS) return false;
    const i = r * BATHY_COLS + c;
    if (tables.depth[i] === LAND_U16) return false;
    pinned = { latlng, i };
    frameCache.clear(); // cache key includes pinIdx
    if (pin) pin.setLatLng(latlng);
    else pin = L.circleMarker(latlng, {
      radius: 6, color: '#ffffff', weight: 2, fillColor: '#FF00AA', fillOpacity: 1,
    }).addTo(map);
    card.hidden = false;
    updatePinned();
    return true;
  }

  function dismissPin() {
    if (pin) { map.removeLayer(pin); pin = null; }
    pinned = null;
    frameCache.clear();
    card.hidden = true;
  }

  function showFrame(idx) {
    if (!frames.length) return;
    cur = Math.max(0, Math.min(frames.length - 1, idx));
    const built = frameFor(cur);
    if (!built) return;
    const s = built.stats, e = s.entry;
    overlay.setUrl(built.url);
    if (!bootHidden) { bootHidden = true; hideBoot(); }
    body.dataset.hour = e.time;
    body.dataset.stepMin = String(stepMin);
    body.dataset.hsFt = s.maxHs.toFixed(3);
    body.dataset.hmaxFt = s.rollerFt.toFixed(3);
    body.dataset.p10Ft = s.p10Ft.toFixed(3);
    body.dataset.windMph = e.speedMph.toFixed(1);
    body.dataset.bearingGrid = e.bearingGrid.toFixed(3);
    body.dataset.teffH = e.tEffH.toFixed(2);
    scrub.value = String(cur);
    label.textContent = ui.formatClockLocal(e.time);
    windEl.textContent = ui.windLine(e.speedMph, e.gustMph);
    frameEl.textContent = `H/L ${s.hlMax.toFixed(3)}`;
    const c = ui.compass(e.dirTrueDeg, e.speedMph);
    if (c.arrowDeg == null) {
      badgeArrow.style.display = 'none';
      badgeText.textContent = 'Calm';
      windBadge.setAttribute('aria-label', 'Wind calm');
    } else {
      badgeArrow.style.display = 'block';
      badgeArrow.style.transform = `rotate(${c.arrowDeg}deg)`;
      badgeText.textContent = `${c.sector} ${c.degText}`;
      windBadge.setAttribute('aria-label',
        `Wind from ${c.sector} at ${Math.round(c.arrowDeg)} degrees`);
    }
    const tier = ui.comfortTier({ maxHsFt: s.maxHs, rollerFt: s.rollerFt, hlMax: s.hlMax });
    comfortChip.className = `tier-${tier.key}`;
    comfortChip.textContent = tier.label;
    const headline = ui.formatHeadline({
      p10Ft: s.p10Ft, maxHsFt: s.maxHs, rollerFt: s.rollerFt,
      peakLat: s.peakLat, peakLon: s.peakLon,
      features, sector: sectorInfo(s.peakLat, s.peakLon),
    });
    verdictRange.textContent = headline.range;
    verdictPeak.textContent = headline.peak;
    if (pinned) updatePinned();
  }

  // rAF-coalesced: many input/tick events collapse into one render of the LATEST index.
  let pendingIdx = null;
  let rafId = 0;
  function requestFrame(idx) {
    pendingIdx = idx;
    if (rafId) return;
    rafId = requestAnimationFrame(() => {
      rafId = 0;
      const i = pendingIdx;
      pendingIdx = null;
      if (i != null) showFrame(i);
    });
  }

  function setPlaying(on) {
    playing = !!on;
    playBtn.setAttribute('aria-pressed', playing ? 'true' : 'false');
    playBtn.dataset.state = playing ? 'pause' : 'play';
    playLabel.textContent = playing ? 'Pause' : 'Play';
    if (playing) {
      timer = setInterval(() => {
        if (!frames.length) return;
        requestFrame((cur + 1) % frames.length);
      }, PLAY_INTERVAL_MS);
    } else if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }
  function pause() { if (playing) setPlaying(false); }

  // Re-gather at the zoom-aware width, debounced; the old image stays visible until ready.
  let regatherTimer = null;
  function regather() {
    const d = desiredDims();
    if (d.W === canvas.width && d.H === canvas.height) return;
    canvas.width = d.W;
    canvas.height = d.H;
    frameCache.clear();
    if (frames.length) showFrame(cur);
  }
  function scheduleRegather() {
    if (regatherTimer) clearTimeout(regatherTimer);
    regatherTimer = setTimeout(regather, 150);
  }

  function flashReadout(msg) {
    readout.textContent = msg;
    if (readoutTimer) clearTimeout(readoutTimer);
    readoutTimer = setTimeout(() => { readout.textContent = DEFAULT_HINT; }, 2000);
  }
  scrub.addEventListener('input', () => {
    pause();
    requestFrame(parseInt(scrub.value, 10));
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });
  playBtn.addEventListener('click', () => setPlaying(!playing));
  document.getElementById('card-close').addEventListener('click', dismissPin);
  window.addEventListener('resize', scheduleRegather);
  // test hook: same handler the map click uses
  window.__bpcTap = (lat, lon) => placePin(L.latLng(lat, lon));

  function applyWindData(data) {
    frames = data.day;
    stepMin = data.stepMin || 15;
    builtMs = 0;
    frameCache.clear();
    const d = desiredDims();
    if (d.W !== canvas.width || d.H !== canvas.height) { canvas.width = d.W; canvas.height = d.H; }
    console.info(`lazy frames: ${frames.length} @ ${stepMin} min`);
    scrub.min = '0';
    scrub.max = String(Math.max(0, frames.length - 1));
    // The now-tick marks the real "now"; an explicit ?hour=/?frame= override hides it.
    if (!q.has('hour') && !q.has('frame') && frames.length) {
      const nowIdx = Number.isFinite(data.currentIndex) ? data.currentIndex : 0;
      const pct = frames.length > 1 ? (nowIdx / (frames.length - 1)) * 100 : 0;
      nowTick.style.left = `${pct}%`;
      nowTick.hidden = false;
    } else {
      nowTick.hidden = true;
    }
    let start;
    if (q.has('hour')) {
      const hh = String(parseInt(q.get('hour'), 10)).padStart(2, '0');
      start = frames.findIndex((e) => e.time.slice(11, 13) === hh);
    } else if (q.has('frame')) {
      start = parseInt(q.get('frame'), 10);
    } else {
      start = data.currentIndex;
    }
    showFrame(Number.isFinite(start) && start >= 0 ? start : 0);
  }

  // Wind-only retry: map data is already decoded and never refetched.
  async function refreshWind() {
    hideNote();
    boot('Loading wind…', null);
    try {
      const data = await wind.ingest({ point, gamma });
      applyWindData(data);
    } catch (err) {
      console.error(err);
      hideBoot();
      showNote('wind unavailable — retry', refreshWind);
    }
  }

  // Full boot: map data first (streamed), then wind. Each step retries itself.
  async function bootMap() {
    hideNote();
    try {
      await loadMapData();
    } catch (err) {
      console.error(err);
      hideBoot();
      showNote('map data failed — retry', bootMap);
      return;
    }
    setupMap();
    await refreshWind();
  }

  document.getElementById('refresh').addEventListener('click', refreshWind);
  await bootMap();
}

module.exports = {
  SCALE_FT, TILE_URL, TILE_ATTRIBUTION, TILE_MAX_ZOOM, OVERLAY_OPACITY, PLAY_INTERVAL_MS,
  FRAME_MINUTES, FRAME_CACHE_MAX,
  gridToLonlat, lonlatToGrid, displayBounds, pickDisplayDims, targetWidth,
  bilinearSample, gatherRaster, hmaxFt, computeFrame, paintRaster,
  landMaskRaster, smoothRaster, cacheKey, frameBytes, createFrameCache, mount,
};
