'use strict';
// Stage 2 display: affine warp, canvas paint, Leaflet overlay, map readout.
// Pure geometry/gather helpers are node-testable; mount() drives the DOM.

const { BATHY_ROWS, BATHY_COLS, BATHY_CELLS, LAND_U16 } = require('./tables');
const waveMath = require('./wave-math');

const SCALE_FT = 6.0;

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
const STOPS = [
  [0.0, 43, 108, 176], [0.5, 43, 131, 196], [1.0, 55, 160, 196],
  [1.5, 64, 179, 137], [2.0, 123, 192, 67], [2.5, 212, 197, 58],
  [3.0, 232, 163, 61], [4.0, 224, 98, 47], [5.0, 192, 44, 44], [6.0, 122, 16, 16],
];
function colorFor(hsFt, maxFt) {
  if (!(hsFt > 0)) return [0, 0, 0, 0];
  const scale = maxFt || SCALE_FT;
  const t = hsFt > scale ? scale : hsFt;
  let i = 0;
  while (i < STOPS.length - 2 && t > STOPS[i + 1][0]) i++;
  const a = STOPS[i], b = STOPS[i + 1];
  const f = (t - a[0]) / (b[0] - a[0]);
  const alpha = Math.round(90 + 150 * Math.min(1, t / scale));
  return [
    Math.round(a[1] + f * (b[1] - a[1])),
    Math.round(a[2] + f * (b[2] - a[2])),
    Math.round(a[3] + f * (b[3] - a[3])),
    alpha,
  ];
}

function paintRaster(ctx, raster, W, H, maxFt) {
  const img = ctx.createImageData(W, H);
  const px = img.data;
  for (let k = 0, p = 0; k < raster.length; k++, p += 4) {
    const c = colorFor(raster[k], maxFt);
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
  const readoutEl = document.getElementById('readout');
  const q = new URLSearchParams(location.search);
  const point = wind.pointFromQuery(location.search);

  const [meta, bins, warp] = await Promise.all([
    fetch('public/meta.v1.json').then((r) => r.json()),
    fetch('public/tables.v1.bin').then((r) => r.arrayBuffer()),
    fetch('public/warp.v1.json').then((r) => r.json()),
  ]);
  const tables = T.decodeTables(bins);
  const gamma = meta.gamma_deg;

  const bounds = displayBounds(warp);
  const { W: dw, H: dh } = pickDisplayDims(bounds, 384);
  canvas.width = dw;
  canvas.height = dh;

  const scratch = {
    out: new Float64Array(BATHY_CELLS),
    afterKs: new Float64Array(BATHY_CELLS),
    ts: new Float64Array(BATHY_CELLS),
  };

  function buildFrames(day) {
    const frames = [];
    for (const entry of day) {
      const f = computeFrame(tables, entry, { gamma, ...scratch });
      const raster = gatherRaster(f.capped, warp, dw, dh);
      frames.push({
        entry, raster, maxHs: f.maxHs, maxIdx: f.maxIdx, rollerFt: f.rollerFt, hlMax: f.hlMax,
        afterKs: Float32Array.from(f.afterKs), ts: Float32Array.from(f.ts),
      });
    }
    return frames;
  }

  const map = L.map('map', { zoomControl: true }).setView(
    [(bounds.north + bounds.south) / 2, (bounds.east + bounds.west) / 2], 11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    { maxZoom: 18, attribution: '&copy; OpenStreetMap' }).addTo(map);
  const llBounds = [[bounds.south, bounds.west], [bounds.north, bounds.east]];
  let overlay = L.imageOverlay('data:image/gif;base64,R0lGODlhAQABAAAAACw=',
    llBounds, { opacity: 0.8 }).addTo(map);
  map.fitBounds(llBounds);

  let frames = [];
  let cur = 0;

  function showFrame(idx) {
    if (!frames.length) return;
    cur = Math.max(0, Math.min(frames.length - 1, idx));
    const f = frames[cur];
    const e = f.entry;
    paintRaster(cctx, f.raster, dw, dh, SCALE_FT);
    overlay.setUrl(canvas.toDataURL());
    body.dataset.hour = e.time;
    body.dataset.hsFt = f.maxHs.toFixed(3);
    body.dataset.hmaxFt = f.rollerFt.toFixed(3);
    body.dataset.windMph = e.speedMph.toFixed(1);
    body.dataset.bearingGrid = e.bearingGrid.toFixed(3);
    body.dataset.teffH = e.tEffH.toFixed(2);
    scrub.value = String(cur);
    label.textContent = e.time.replace('T', ' ');
    windEl.textContent = `${e.speedMph.toFixed(0)} mph, gust ${e.gustMph.toFixed(0)}, ${e.dirTrueDeg.toFixed(0)}°`;
    frameEl.textContent = `Hs ${f.maxHs.toFixed(2)} ft · Hmax ${f.rollerFt.toFixed(2)} ft · H/L ${f.hlMax.toFixed(3)}`;
  }

  map.on('click', (ev) => {
    const g = lonlatToGrid(warp, ev.latlng.lng, ev.latlng.lat);
    const c = Math.round(g.col), r = Math.round(g.row);
    if (c < 0 || r < 0 || c >= BATHY_COLS || r >= BATHY_ROWS) {
      readoutEl.textContent = 'off the lake';
      return;
    }
    const i = r * BATHY_COLS + c;
    const du = tables.depth[i];
    if (du === LAND_U16) { readoutEl.textContent = 'land'; return; }
    const f = frames[cur];
    const d = du * 0.25;
    const hsKs = f.afterKs[i], ts = f.ts[i];
    const hs = Math.min(hsKs, 0.6 * d);
    const hm = hmaxFt(hsKs, d);
    const L_m = (waveMath.dispersionFast(ts, d * waveMath.FT)).L_m;
    readoutEl.textContent = `Hs ${hs.toFixed(2)} ft · Hmax ${hm.toFixed(2)} ft · ` +
      `H/L ${(hsKs * waveMath.FT / L_m).toFixed(3)} · depth ${d.toFixed(1)} ft`;
  });

  scrub.addEventListener('input', () => showFrame(parseInt(scrub.value, 10)));

  async function refresh() {
    note.style.display = 'none';
    try {
      const data = await wind.ingest({ point, gamma });
      frames = buildFrames(data.day);
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
  SCALE_FT, gridToLonlat, lonlatToGrid, displayBounds, pickDisplayDims,
  bilinearSample, gatherRaster, hmaxFt, computeFrame, colorFor, paintRaster, mount,
};
