'use strict';
// Stage 3: pure UI helpers — headline formatting, Hs palette, spot naming.
// No DOM, no tables: node-testable and browser-loadable via the tiny loader.

// ---- Hs palette (ft): deep blue -> cyan -> amber -> orange-red -> crimson -> magenta ----
const HS_STOPS = [
  [0.0, 0x1e, 0x40, 0xaf], // deep blue
  [1.0, 0x06, 0xb6, 0xd4], // vibrant cyan
  [2.0, 0xf5, 0x9e, 0x0b], // amber
  [3.5, 0xea, 0x58, 0x0c], // orange-red
  [4.5, 0xdc, 0x26, 0x26], // crimson
  [5.5, 0xbe, 0x18, 0x5d], // magenta
];
const HS_BREAKS = [0, 1, 2, 3.5, 4.5, 6];
const OVERLAY_OPACITY = 0.72;

// RGBA for an Hs value in ft. Land / flat water -> fully transparent; water -> opaque,
// opacity is applied once by the Leaflet overlay.
function colorForHs(hsFt) {
  if (!(hsFt > 0) || !Number.isFinite(hsFt)) return [0, 0, 0, 0];
  const t = Math.min(hsFt, HS_STOPS[HS_STOPS.length - 1][0]);
  let i = 0;
  while (i < HS_STOPS.length - 2 && t > HS_STOPS[i + 1][0]) i++;
  const a = HS_STOPS[i], b = HS_STOPS[i + 1];
  const f = (t - a[0]) / (b[0] - a[0]);
  return [
    Math.round(a[1] + f * (b[1] - a[1])),
    Math.round(a[2] + f * (b[2] - a[2])),
    Math.round(a[3] + f * (b[3] - a[3])),
    255,
  ];
}

// CSS rgb() for a stop value, used by the legend strip.
function rgbForHs(hsFt) {
  const c = colorForHs(hsFt);
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

// Single source of truth for the deck ramp gradient: the six Hs stop colours, evenly
// spaced. index.html applies it to #ramp-bar at mount.
const RAMP_PCT = ['0%', '16.7%', '33.3%', '50%', '66.7%', '100%'];
function rampGradient() {
  const stops = HS_STOPS.map(([, r, g, b], i) => `rgb(${r}, ${g}, ${b}) ${RAMP_PCT[i]}`);
  return `linear-gradient(90deg, ${stops.join(', ')})`;
}

// ---- stats ----
function percentile(values, p) {
  const v = [];
  for (let i = 0; i < values.length; i++) {
    if (values[i] > 0 && Number.isFinite(values[i])) v.push(values[i]);
  }
  if (!v.length) return 0;
  v.sort((x, y) => x - y);
  const idx = (v.length - 1) * p;
  const lo = Math.floor(idx), hi = Math.ceil(idx);
  return v[lo] + (v[hi] - v[lo]) * (idx - lo);
}
function p10(values) { return percentile(values, 0.1); }

// ---- geography ----
const SECTORS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
const MI_M = 1609.344;
const FEATURE_RADIUS_M = 4000;
const SHORE_RADIUS_M = 400;

function haversineM(lat1, lon1, lat2, lon2) {
  const R = 6371008.8;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

// 8-way compass bearing from point 1 to point 2, degrees clockwise from north.
function bearing8(lat1, lon1, lat2, lon2) {
  const midLat = (lat1 + lat2) / 2 * Math.PI / 180;
  const dx = (lon2 - lon1) * Math.cos(midLat);
  const dy = lat2 - lat1;
  let deg = Math.atan2(dx, dy) * 180 / Math.PI;
  deg = ((deg % 360) + 360) % 360;
  return SECTORS[Math.round(deg / 45) % 8];
}

function centroidOfCorners(corners) {
  let lat = 0, lon = 0, n = 0;
  for (const k of Object.keys(corners || {})) { lat += corners[k][1]; lon += corners[k][0]; n++; }
  return n ? { lat: lat / n, lon: lon / n } : { lat: 0, lon: 0 };
}

// 8-way sector of a point relative to the lake centroid.
function sectorFor(lat, lon, centroid) {
  return bearing8(centroid.lat, centroid.lon, lat, lon);
}

// Nearest named feature within 4 km, else open water with its sector descriptor.
// sector = { name, shore }.
function nameSpot(lat, lon, features, sector) {
  let best = null, bestM = Infinity;
  for (const f of features || []) {
    const m = haversineM(lat, lon, f.lat, f.lon);
    if (m < bestM) { bestM = m; best = f; }
  }
  if (best && bestM <= FEATURE_RADIUS_M) {
    return {
      kind: 'feature', name: best.name, distanceMi: bestM / MI_M,
      bearing: bearing8(lat, lon, best.lat, best.lon), sector,
    };
  }
  return { kind: 'open', sector };
}

function describePin(spot) {
  if (spot.kind === 'feature') {
    return `${spot.distanceMi.toFixed(1)} mi ${spot.bearing} of ${spot.name}`;
  }
  return `Open water - ${sectorName(spot.sector)}`;
}

function sectorPhrase(sector) {
  const s = sector || {};
  return `${s.name} ${s.shore ? 'shore' : 'basin'}`;
}

// Capitalised sector label for headers and cards: "N Basin" / "SW Shore".
function sectorName(sector) {
  const s = sector || {};
  return `${s.name} ${s.shore ? 'Shore' : 'Basin'}`;
}

// Short place label for the header: the named feature if the peak is close to one,
// else the sector. "Peak: 4.0 ft · N Basin" / "Peak: 4.0 ft · Cove Bay".
function shortPlace(spot, sector) {
  return spot && spot.kind === 'feature' ? spot.name : sectorName(sector);
}

// Two-line honest verdict. Never a bare single Hs number.
function formatHeadline(frame) {
  const spot = nameSpot(frame.peakLat, frame.peakLon, frame.features, frame.sector);
  return {
    range: `Waves: ${frame.p10Ft.toFixed(1)} - ${frame.maxHsFt.toFixed(1)} ft`,
    peak: `Peak: ${frame.rollerFt.toFixed(1)} ft · ${shortPlace(spot, frame.sector)}`,
  };
}

// ---- Stage 4B: wind split, compass, condition tier, local clock ----
const CALM_MPH = 3;
const CHICAGO_TZ = 'America/Chicago';
const TIERS = {
  red: 'Dangerous · Stay Home',
  amber: 'Heavy Rollers',
  yellow: 'Walleye Chop',
  green: 'Fishable · Light Chop',
};

// Bearing in [0, 360).
function normalizeDeg(deg) {
  const d = Number(deg) % 360;
  return d < 0 ? d + 360 : d;
}

// "Wind: 14 mph · Gusts 26 mph" (0 decimals). Any missing/short speed -> calm.
function windLine(speedMph, gustMph) {
  const s = Number(speedMph);
  if (!Number.isFinite(s) || s < CALM_MPH) return 'Wind: calm';
  const g = Number(gustMph);
  return Number.isFinite(g)
    ? `Wind: ${Math.round(s)} mph · Gusts ${Math.round(g)} mph`
    : `Wind: ${Math.round(s)} mph`;
}

// Compass metadata. arrowDeg points INTO the wind (at the source). Calm (< 3 mph)
// or a non-finite bearing -> { sector:'Calm', degText:'', arrowDeg:null }.
function compass(bearingDeg, speedMph) {
  if (speedMph != null) {
    const s = Number(speedMph);
    if (!Number.isFinite(s) || s < CALM_MPH) return { sector: 'Calm', degText: '', arrowDeg: null };
  }
  const b = Number(bearingDeg);
  if (!Number.isFinite(b)) return { sector: 'Calm', degText: '', arrowDeg: null };
  const deg = normalizeDeg(b);
  return { sector: SECTORS[Math.round(deg / 45) % 8], degText: `${Math.round(deg)}°`, arrowDeg: deg };
}

// Condition tier, strict red -> amber -> yellow -> green (first match wins).
// Missing/NaN inputs never trigger a condition.
function comfortTier(stats) {
  const s = stats || {};
  const maxHs = Number(s.maxHsFt), roller = Number(s.rollerFt), hl = Number(s.hlMax);
  const at = (v, t) => Number.isFinite(v) && v >= t;
  let key = 'green';
  if (at(maxHs, 5.0) || at(roller, 4.0) || at(hl, 0.055)) key = 'red';
  else if (at(maxHs, 3.5) || at(roller, 2.5)) key = 'amber';
  else if (at(maxHs, 2.0) || at(roller, 1.5)) key = 'yellow';
  return { key, label: TIERS[key] };
}

// Offset (local wall-clock as UTC minus the true instant) at an instant, ms.
function tzOffsetMs(utcMs) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: CHICAGO_TZ, hour12: false,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  }).formatToParts(new Date(utcMs));
  const p = {};
  for (const x of parts) p[x.type] = x.value;
  const asUTC = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour % 24, +p.minute, +p.second);
  return asUTC - utcMs;
}

// "2026-09-11T17:15" -> "5:15 PM CDT". Input is America/Chicago wall-clock; the
// local instant is resolved with a two-pass offset (DST-safe), never by slicing.
function formatClockLocal(isoLocal) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(String(isoLocal == null ? '' : isoLocal));
  if (!m) return '';
  const naive = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
  let epoch = naive - tzOffsetMs(naive);
  epoch = naive - tzOffsetMs(epoch);
  return new Intl.DateTimeFormat('en-US', {
    timeZone: CHICAGO_TZ, hour: 'numeric', minute: '2-digit', hour12: true, timeZoneName: 'short',
  }).format(new Date(epoch));
}

// Compact pill clock: 12-hour, no leading zero, minutes only when non-zero,
// no timezone suffix. '2026-09-11T10:00' -> '10 AM', '2026-09-11T13:15' -> '1:15 PM'.
function formatPillTime(isoLocal) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(String(isoLocal == null ? '' : isoLocal));
  if (!m) return '';
  const naive = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
  let epoch = naive - tzOffsetMs(naive);
  epoch = naive - tzOffsetMs(epoch);
  return new Intl.DateTimeFormat('en-US', {
    timeZone: CHICAGO_TZ, hour: 'numeric', minute: '2-digit', hour12: true,
  }).format(new Date(epoch)).replace(':00 ', ' ');
}

// ---- Stage 5D: day label from a local ISO string ----
// Weekday comes from calendar math alone (Date.UTC noon + getUTCDay); never a
// TZ-parse of the full string, which would shift the date near midnight.
const DOW_SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const DOW_LONG = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

// '2026-09-11T00:00' -> 'Fri 11' (long = false) / 'Friday 11' (long = true). '' on bad input.
function dayLabel(isoLocal, long) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(isoLocal == null ? '' : isoLocal));
  if (!m) return '';
  const y = +m[1], mo = +m[2], d = +m[3];
  const dt = new Date(Date.UTC(y, mo - 1, d, 12));
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) return '';
  return `${(long ? DOW_LONG : DOW_SHORT)[dt.getUTCDay()]} ${d}`;
}

module.exports = {
  HS_STOPS, HS_BREAKS, OVERLAY_OPACITY,
  colorForHs, rgbForHs, rampGradient, percentile, p10,
  SECTORS, haversineM, bearing8, centroidOfCorners, sectorFor,
  nameSpot, describePin, sectorPhrase, sectorName, shortPlace, formatHeadline,
  FEATURE_RADIUS_M, SHORE_RADIUS_M,
  CALM_MPH, normalizeDeg, windLine, compass, comfortTier, formatClockLocal,
  formatPillTime, dayLabel,
};
