'use strict';
// Stage 2 display: affine warp, canvas paint, Leaflet overlay, map readout.
// Pure geometry/gather helpers are node-testable; mount() drives the DOM.

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

// One hour frame: capped Hs field + post-Ks/depth/period for readout + lake-max stats.
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

// ---- browser app ----
async function mount(deps) {
  const { tables: T, wind } = deps;
  const note = document.getElementById('note');
  const body = document.body;
  const canvas = document.getElementById('field');
  const cctx = canvas.getContext('2d');
  const scrub = document.getElementById('scrub');
  const label = document.getElementById('hour-label');
  const windEl = document.getElementById('wind-info');
  const frameEl = document.getElementById('frame-info');
  const verdictRange = document.getElementById('verdict-range');
  const verdictPeak = document.getElementById('verdict-peak');
  const playBtn = document.getElementById('play');
  const playLabel = document.getElementById('play-label');
  const card = document.getElementById('card');
  const q = new URLSearchParams(location.search);
  const point = wind.pointFromQuery(location.search);

  const [meta, bins, warp, spots] = await Promise.all([
    fetch('public/meta.v1.json').then((r) => r.json()),
    fetch('public/tables.v1.bin').then((r) => r.arrayBuffer()),
    fetch('public/warp.v1.json').then((r) => r.json()),
    fetch('public/spots.v1.json').then((r) => r.json()),
  ]);
  const tables = T.decodeTables(bins);
  const gamma = meta.gamma_deg;
  const features = spots.features || [];
  const centroid = ui.centroidOfCorners(meta.wgs84_corners || warp.corners);
  const reducedMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  if (reducedMotion) body.classList.add('reduced-motion');

  const bounds = displayBounds(warp);
  const { W: dw, H: dh } = pickDisplayDims(bounds, 384);
  canvas.width = dw;
  canvas.height = dh;

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

  function buildFrames(day) {
    const built = [];
    for (const entry of day) {
      const f = computeFrame(tables, entry, { gamma, ...scratch });
      const raster = gatherRaster(f.capped, warp, dw, dh);
      const p10Ft = ui.p10(f.capped);
      const peak = gridToLonlat(warp, f.maxIdx % BATHY_COLS, Math.floor(f.maxIdx / BATHY_COLS));
      built.push({
        entry, raster, maxHs: f.maxHs, maxIdx: f.maxIdx, rollerFt: f.rollerFt, hlMax: f.hlMax,
        p10Ft, peak,
        afterKs: Float32Array.from(f.afterKs), ts: Float32Array.from(f.ts),
      });
    }
    return built;
  }

  const map = L.map('map', { zoomControl: true }).setView(
    [(bounds.north + bounds.south) / 2, (bounds.east + bounds.west) / 2], 11);
  L.tileLayer(TILE_URL, {
    maxZoom: TILE_MAX_ZOOM, attribution: TILE_ATTRIBUTION, detectRetina: true,
  }).addTo(map);
  const llBounds = [[bounds.south, bounds.west], [bounds.north, bounds.east]];
  const overlay = L.imageOverlay('data:image/gif;base64,R0lGODlhAQABAAAAACw=',
    llBounds, { opacity: OVERLAY_OPACITY }).addTo(map);
  map.fitBounds(llBounds);

  let frames = [];
  let cur = 0;
  let pinned = null;
  let pin = null;
  let playing = false;
  let timer = null;

  function setCardField(name, value) {
    const el = card.querySelector(`[data-field="${name}"] .v`);
    if (el) el.textContent = value;
  }

  function updatePinned() {
    if (!pinned || !frames.length) return;
    const f = frames[cur];
    const d = tables.depth[pinned.i] * 0.25;
    const hsKs = f.afterKs[pinned.i], ts = f.ts[pinned.i];
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
    card.hidden = true;
  }

  function showFrame(idx) {
    if (!frames.length) return;
    cur = Math.max(0, Math.min(frames.length - 1, idx));
    const f = frames[cur];
    const e = f.entry;
    paintRaster(cctx, f.raster, dw, dh);
    overlay.setUrl(canvas.toDataURL());
    body.dataset.hour = e.time;
    body.dataset.hsFt = f.maxHs.toFixed(3);
    body.dataset.hmaxFt = f.rollerFt.toFixed(3);
    body.dataset.p10Ft = f.p10Ft.toFixed(3);
    body.dataset.windMph = e.speedMph.toFixed(1);
    body.dataset.bearingGrid = e.bearingGrid.toFixed(3);
    body.dataset.teffH = e.tEffH.toFixed(2);
    scrub.value = String(cur);
    label.textContent = e.time.replace('T', ' ');
    windEl.textContent = `${e.speedMph.toFixed(0)} mph gust ${e.gustMph.toFixed(0)} · ${e.dirTrueDeg.toFixed(0)}°`;
    frameEl.textContent = `H/L ${f.hlMax.toFixed(3)}`;
    const headline = ui.formatHeadline({
      p10Ft: f.p10Ft, maxHsFt: f.maxHs, rollerFt: f.rollerFt,
      peakLat: f.peak.lat, peakLon: f.peak.lon,
      features, sector: sectorInfo(f.peak.lat, f.peak.lon),
    });
    verdictRange.textContent = headline.range;
    verdictPeak.textContent = headline.peak;
    if (pinned) updatePinned();
  }

  function setPlaying(on) {
    playing = !!on;
    playBtn.setAttribute('aria-pressed', playing ? 'true' : 'false');
    playBtn.dataset.state = playing ? 'pause' : 'play';
    playLabel.textContent = playing ? 'Pause' : 'Play';
    if (playing) {
      timer = setInterval(() => {
        if (!frames.length) return;
        showFrame((cur + 1) % frames.length);
      }, PLAY_INTERVAL_MS);
    } else if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }
  function pause() { if (playing) setPlaying(false); }

  map.on('click', (ev) => { placePin(ev.latlng); });
  scrub.addEventListener('input', () => {
    pause();
    showFrame(parseInt(scrub.value, 10));
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });
  playBtn.addEventListener('click', () => setPlaying(!playing));
  document.getElementById('card-close').addEventListener('click', dismissPin);
  // test hook: same handler the map click uses
  window.__bpcTap = (lat, lon) => placePin(L.latLng(lat, lon));

  async function refresh() {
    note.style.display = 'none';
    try {
      const data = await wind.ingest({ point, gamma });
      const t0 = performance.now();
      frames = buildFrames(data.day);
      const totalMs = performance.now() - t0;
      const frameMs = frames.length ? totalMs / frames.length : 0;
      body.dataset.precomputeMs = totalMs.toFixed(1);
      body.dataset.frameMs = frameMs.toFixed(1);
      console.info(`day precompute ${totalMs.toFixed(0)} ms / ${frames.length} frames ` +
        `(${frameMs.toFixed(1)} ms per frame)`);
      scrub.min = '0';
      scrub.max = String(Math.max(0, frames.length - 1));
      const start = q.has('hour') ? parseInt(q.get('hour'), 10) : data.currentIndex;
      showFrame(Number.isFinite(start) ? start : 0);
    } catch (err) {
      console.error(err);
      note.textContent = 'wind unavailable — refresh';
      note.style.display = 'block';
    }
  }

  document.getElementById('refresh').addEventListener('click', refresh);
  await refresh();
}

module.exports = {
  SCALE_FT, TILE_URL, TILE_ATTRIBUTION, TILE_MAX_ZOOM, OVERLAY_OPACITY, PLAY_INTERVAL_MS,
  gridToLonlat, lonlatToGrid, displayBounds, pickDisplayDims,
  bilinearSample, gatherRaster, hmaxFt, computeFrame, paintRaster, mount,
};
