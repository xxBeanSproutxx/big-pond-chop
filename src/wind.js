'use strict';
// Stage 4A wind ingest: 15-minute time base + t_eff persistence + grid-bearing mapping.
// Open-Meteo hourly (fallback) + minutely_15 (native), one lake-wide point, mph,
// America/Chicago, past_days=1, forecast_days=2.

const DEFAULT_POINT = { lat: 46.22, lon: -93.657 };

const API = 'https://api.open-meteo.com/v1/forecast';
const HOURLY = 'wind_speed_10m,wind_direction_10m,wind_gusts_10m';
const MINUTELY = 'wind_speed_10m,wind_direction_10m,wind_gusts_10m';
const STEP_H = 0.25;

// bearing_grid = ((dir_true - gamma) % 360 + 360) % 360, gamma from meta.v1.json.
function gammaToGrid(dirTrueDeg, gammaDeg) {
  return ((dirTrueDeg - gammaDeg) % 360 + 360) % 360;
}

// Smallest absolute angular difference in degrees, wrap-aware.
function bearingDelta(a, b) {
  const d = Math.abs(a - b) % 360;
  return d > 180 ? 360 - d : d;
}

// Shortest-arc linear interpolation in true bearing space (350 -> 10 passes 0).
function lerpAngle(a, b, f) {
  const d = ((b - a + 540) % 360) - 180;
  return ((a + f * d) % 360 + 360) % 360;
}

// t_eff persistence pass, hours. dtH is the step in hours (1 = hourly, 0.25 = 15 min).
// The +1.0 accumulation is per step; the 0.5 reset and 4 mph floor are NOT scaled.
function computeTeff(series, dtH = 1) {
  const out = new Array(series.length);
  for (let i = 0; i < series.length; i++) {
    const s = series[i];
    if (s.speedMph < 4) { out[i] = 0; continue; }        // case 3 (speed wins)
    if (i === 0) { out[i] = 0.5; continue; }              // no predecessor
    const d = bearingDelta(s.bearingGrid, series[i - 1].bearingGrid);
    out[i] = d > 30 ? 0.5 : Math.min(6.0, out[i - 1] + dtH); // case 2 / case 1
  }
  return out;
}

// End-of-yesterday state, from the last up-to-6 hourly entries, so today's first
// frame can inherit persistence across midnight. Pure; the shipped ingest path
// computes t_eff over the whole multi-day series, so it does not need this seed.
function seedTeff(hourlyTail, opts = {}) {
  const dtH = opts.dtH != null ? opts.dtH : 1;
  const tail = (hourlyTail || []).slice(-6);
  if (!tail.length) return { tEffH: 0, bearingGrid: 0 };
  const teff = computeTeff(tail, dtH);
  const last = tail[tail.length - 1];
  return { tEffH: teff[teff.length - 1], bearingGrid: last.bearingGrid };
}

// Single construction path for a series: raw arrays -> tagged entries with t_eff.
function buildSeriesFrom(times, speeds, dirs, gusts, gammaDeg, dtH = 1) {
  const raw = [];
  for (let i = 0; i < times.length; i++) {
    const dirTrue = Number(dirs[i]);
    raw.push({
      time: times[i],
      speedMph: Number(speeds[i]),
      gustMph: Number(gusts[i]),
      dirTrueDeg: dirTrue,
      bearingGrid: gammaToGrid(dirTrue, gammaDeg),
    });
  }
  const teff = computeTeff(raw, dtH);
  for (let i = 0; i < raw.length; i++) raw[i].tEffH = teff[i];
  return raw;
}

function buildSeries(hourly, gammaDeg) {
  return buildSeriesFrom(
    hourly.time || [], hourly.wind_speed_10m || [],
    hourly.wind_direction_10m || [], hourly.wind_gusts_10m || [], gammaDeg, 1,
  );
}

// Expand a source series 4x to 15-min resolution. Linear for speed/gust,
// shortest-arc for direction (true bearing space). gammaDeg is applied by the
// caller (buildSeriesFrom); it is accepted here to keep the spec signature.
function addMin(iso, min) {
  const ms = Date.parse(iso.length <= 16 ? `${iso}:00Z` : `${iso}Z`);
  return new Date(ms + min * 60000).toISOString().slice(0, 16);
}

function interpolate15(fields, gammaDeg) {
  const times = (fields && fields.time) || [];
  const sp = (fields && fields.wind_speed_10m) || [];
  const dr = (fields && fields.wind_direction_10m) || [];
  const gu = (fields && fields.wind_gusts_10m) || [];
  const out = { times: [], speeds: [], dirs: [], gusts: [] };
  for (let i = 0; i < times.length - 1; i++) {
    const sa = Number(sp[i]), sb = Number(sp[i + 1]);
    const ga = Number(gu[i]), gb = Number(gu[i + 1]);
    const da = Number(dr[i]), db = Number(dr[i + 1]);
    for (let k = 0; k < 4; k++) {
      const f = k / 4;
      out.times.push(addMin(times[i], k * 15));
      out.speeds.push(sa + f * (sb - sa));
      out.gusts.push(ga + f * (gb - ga));
      out.dirs.push(lerpAngle(da, db, f));
    }
  }
  if (times.length) {
    const n = times.length - 1;
    out.times.push(times[n]);
    out.speeds.push(Number(sp[n]));
    out.gusts.push(Number(gu[n]));
    out.dirs.push(Number(dr[n]));
  }
  return out;
}

// Current local (America/Chicago) date + hour + minute.
function chicagoNow(now) {
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Chicago', year: 'numeric', month: '2-digit',
    day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  });
  const p = {};
  for (const part of fmt.formatToParts(now || new Date())) p[part.type] = part.value;
  return {
    date: `${p.year}-${p.month}-${p.day}`,
    hour: parseInt(p.hour, 10) % 24,
    minute: parseInt(p.minute, 10),
  };
}

// The entries of a local date, each tagged with its absolute series index.
function selectDay(series, dateStr) {
  const day = [];
  for (let i = 0; i < series.length; i++) {
    if (series[i].time.slice(0, 10) === dateStr) day.push({ ...series[i], seriesIndex: i });
  }
  return day;
}

// Index (within `day`) of the current 15-min bucket (17:12 -> 17:00, 17:52 -> 17:45).
function currentIndex(day, now) {
  const { hour, minute } = chicagoNow(now);
  const target = `${String(hour).padStart(2, '0')}:${String(Math.floor(minute / 15) * 15).padStart(2, '0')}`;
  for (let i = 0; i < day.length; i++) {
    if (day[i].time.slice(11, 16) === target) return i;
  }
  return 0;
}

function buildUrl(lat, lon) {
  return `${API}?latitude=${lat}&longitude=${lon}&hourly=${HOURLY}` +
    `&minutely_15=${MINUTELY}` +
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

// Full ingest: fetch + parse + gamma + t_eff. Prefers native minutely_15; falls
// back to hourly expanded 4x. fetchImpl injectable for tests.
async function ingest(opts = {}) {
  const point = opts.point || DEFAULT_POINT;
  const gamma = opts.gamma != null ? opts.gamma : 0;
  const json = opts.json || await fetchWind(point.lat, point.lon);
  const m = json && json.minutely_15;
  let series;
  if (m && m.time && m.time.length > 1) {
    series = buildSeriesFrom(
      m.time, m.wind_speed_10m || [], m.wind_direction_10m || [],
      m.wind_gusts_10m || [], gamma, STEP_H,
    );
  } else {
    const f = interpolate15(json && json.hourly ? json.hourly : {}, gamma);
    series = buildSeriesFrom(f.times, f.speeds, f.dirs, f.gusts, gamma, STEP_H);
  }
  const now = opts.now || new Date();
  const date = chicagoNow(now).date;
  const day = selectDay(series, date);
  return {
    point, gamma, series, day, currentIndex: currentIndex(day, now),
    raw: json, stepMin: 15,
  };
}

module.exports = {
  DEFAULT_POINT, API, gammaToGrid, bearingDelta, lerpAngle, computeTeff, seedTeff,
  buildSeries, buildSeriesFrom, interpolate15,
  chicagoNow, selectDay, currentIndex, buildUrl, fetchWind, pointFromQuery, ingest,
};
