'use strict';
// Stage 2 wind ingest + t_eff persistence + grid-bearing mapping.
// Open-Meteo hourly, one lake-wide point, mph, America/Chicago, past_days=1.

const DEFAULT_POINT = { lat: 46.22, lon: -93.657 };

const API = 'https://api.open-meteo.com/v1/forecast';
const HOURLY = 'wind_speed_10m,wind_direction_10m,wind_gusts_10m';

// bearing_grid = ((dir_true - gamma) % 360 + 360) % 360, gamma from meta.v1.json.
function gammaToGrid(dirTrueDeg, gammaDeg) {
  return ((dirTrueDeg - gammaDeg) % 360 + 360) % 360;
}

// Smallest absolute angular difference in degrees, wrap-aware.
function bearingDelta(a, b) {
  const d = Math.abs(a - b) % 360;
  return d > 180 ? 360 - d : d;
}

// t_eff persistence pass (docs/BUILD-SPEC-STAGE2.md s1), hours.
// series: [{ bearingGrid, speedMph }] in time order.
function computeTeff(series) {
  const out = new Array(series.length);
  for (let i = 0; i < series.length; i++) {
    const s = series[i];
    if (s.speedMph < 4) { out[i] = 0; continue; }        // case 3 (speed wins)
    if (i === 0) { out[i] = 0.5; continue; }              // no predecessor
    const d = bearingDelta(s.bearingGrid, series[i - 1].bearingGrid);
    out[i] = d > 30 ? 0.5 : Math.min(6.0, out[i - 1] + 1.0); // case 2 / case 1
  }
  return out;
}

function buildSeries(hourly, gammaDeg) {
  const t = hourly.time || [];
  const sp = hourly.wind_speed_10m || [];
  const dr = hourly.wind_direction_10m || [];
  const gu = hourly.wind_gusts_10m || [];
  const raw = [];
  for (let i = 0; i < t.length; i++) {
    const dirTrue = Number(dr[i]);
    raw.push({
      time: t[i],
      speedMph: Number(sp[i]),
      gustMph: Number(gu[i]),
      dirTrueDeg: dirTrue,
      bearingGrid: gammaToGrid(dirTrue, gammaDeg),
    });
  }
  const teff = computeTeff(raw);
  for (let i = 0; i < raw.length; i++) raw[i].tEffH = teff[i];
  return raw;
}

// Current local (America/Chicago) date + hour.
function chicagoNow(now) {
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Chicago', year: 'numeric', month: '2-digit',
    day: '2-digit', hour: '2-digit', hour12: false,
  });
  const p = {};
  for (const part of fmt.formatToParts(now || new Date())) p[part.type] = part.value;
  return { date: `${p.year}-${p.month}-${p.day}`, hour: parseInt(p.hour, 10) % 24 };
}

// The 24 entries of a local date, each tagged with its absolute series index.
function selectDay(series, dateStr) {
  const day = [];
  for (let i = 0; i < series.length; i++) {
    if (series[i].time.slice(0, 10) === dateStr) day.push({ ...series[i], seriesIndex: i });
  }
  return day;
}

// Index (within `day`) of the entry matching the current Chicago hour.
function currentIndex(day, now) {
  const { hour } = chicagoNow(now);
  for (let i = 0; i < day.length; i++) {
    if (parseInt(day[i].time.slice(11, 13), 10) === hour) return i;
  }
  return 0;
}

function buildUrl(lat, lon) {
  return `${API}?latitude=${lat}&longitude=${lon}&hourly=${HOURLY}` +
    `&wind_speed_unit=mph&timezone=America%2FChicago&past_days=1&forecast_days=2`;
}

async function fetchWind(lat, lon) {
  const res = await fetch(buildUrl(lat, lon), { cache: 'no-store' });
  if (!res.ok) throw new Error(`open-meteo HTTP ${res.status}`);
  return res.json();
}

// ?lat=&lon= override, else the lake-wide default point.
function pointFromQuery(search) {
  const q = new URLSearchParams(search || '');
  const lat = parseFloat(q.get('lat'));
  const lon = parseFloat(q.get('lon'));
  return {
    lat: Number.isFinite(lat) ? lat : DEFAULT_POINT.lat,
    lon: Number.isFinite(lon) ? lon : DEFAULT_POINT.lon,
  };
}

// Full ingest: fetch + parse + gamma + t_eff. fetchImpl injectable for tests.
async function ingest(opts = {}) {
  const point = opts.point || DEFAULT_POINT;
  const gamma = opts.gamma != null ? opts.gamma : 0;
  const json = opts.json || await fetchWind(point.lat, point.lon);
  const series = buildSeries(json.hourly, gamma);
  const now = opts.now || new Date();
  const date = chicagoNow(now).date;
  const day = selectDay(series, date);
  return { point, gamma, series, day, currentIndex: currentIndex(day, now), raw: json };
}

module.exports = {
  DEFAULT_POINT, API, gammaToGrid, bearingDelta, computeTeff, buildSeries,
  chicagoNow, selectDay, currentIndex, buildUrl, fetchWind, pointFromQuery, ingest,
};
