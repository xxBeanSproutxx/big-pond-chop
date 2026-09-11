'use strict';
// Stage 4A wind tests: t_eff vectors A-F, dtH scaling, shortest-arc interpolation,
// seed continuity, 96-frame day, 15-min currentIndex, live ingest + perf.
// Run: node tests/wind.test.js
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { performance } = require('perf_hooks');
const { decodeTables, BATHY_CELLS } = require('../src/tables');
const {
  gammaToGrid, computeTeff, seedTeff, interpolate15, buildSeriesFrom,
  ingest, chicagoNow, currentIndex,
} = require('../src/wind');
const { computeFrame } = require('../src/render');

const ROOT = path.join(__dirname, '..');
let failures = 0;
function check(name, fn) {
  try { fn(); console.log(`  ok   ${name}`); }
  catch (e) { failures++; console.log(`  FAIL ${name}: ${e.message}`); }
}

function series(bearings, speeds) {
  return bearings.map((b, i) => ({ bearingGrid: b, speedMph: speeds[i] }));
}
function eq(a, b, msg) {
  assert.strictEqual(a.length, b.length, `${msg} length`);
  for (let i = 0; i < a.length; i++) assert.strictEqual(a[i], b[i], `${msg}[${i}] got ${a[i]} want ${b[i]}`);
}

console.log('\n== [1] t_eff persistence vectors A-F (dtH = 1 unchanged) ==');
check('A: steady 12 mph from 315 for 8 h (+1.0/h)', () => {
  const out = computeTeff(series(Array(8).fill(315), Array(8).fill(12)));
  eq(out, [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.0, 6.0], 'A');
});
check('B: 5 h 20 mph 315 then +90 deg shift', () => {
  const out = computeTeff(series([315, 315, 315, 315, 315, 0], Array(6).fill(20)));
  eq(out, [0.5, 1.5, 2.5, 3.5, 4.5, 0.5], 'B');
});
check('C: lull (2 mph) resets, recovery climbs from 0', () => {
  const out = computeTeff(series([315, 315, 315, 315], [12, 12, 2, 10]));
  eq(out, [0.5, 1.5, 0, 1.0], 'C');
});
check('D: saturates at 6.0 and stays', () => {
  const out = computeTeff(series(Array(14).fill(315), Array(14).fill(12)));
  assert.strictEqual(out[11], 6.0, 'D hit cap');
  assert.strictEqual(out[13], 6.0, 'D stays capped');
});
check('E: exactly +30 deg counts as within tolerance', () => {
  const out = computeTeff(series([315, 345], [12, 12]));
  eq(out, [0.5, 1.5], 'E');
});
check('F: +31 deg resets to 0.5', () => {
  const out = computeTeff(series([315, 346], [12, 12]));
  eq(out, [0.5, 0.5], 'F');
});

console.log('\n== [1b] dtH t_eff: 15-min accumulation, reset + floor unchanged ==');
check('dtH=0.25 accumulates per step', () => {
  const out = computeTeff(series(Array(5).fill(315), Array(5).fill(12)), 0.25);
  eq(out, [0.5, 0.75, 1.0, 1.25, 1.5], 'dtH quarter');
  console.log(`       ${out.join(', ')}`);
});
check('dtH=0.25 reset is 0.5 (not scaled) and 4 mph floor still 0', () => {
  const out = computeTeff(series([315, 45, 45], [12, 12, 3]), 0.25);
  eq(out, [0.5, 0.5, 0], 'dtH reset/floor');
});
check('dtH=1 matches a plain +1.0 accumulator exactly', () => {
  const s = series([300, 301, 302, 303], [20, 20, 20, 20]);
  assert.deepStrictEqual(computeTeff(s, 1), computeTeff(s));
});

console.log('\n== [1c] seedTeff continuity across midnight ==');
check('six steady hourly steps seed 5.5 h and carry the bearing', () => {
  const tail = series(Array(6).fill(315), Array(6).fill(12));
  const seed = seedTeff(tail, { dtH: 1 });
  assert.strictEqual(seed.tEffH, 5.5);
  assert.strictEqual(seed.bearingGrid, 315);
  const firstStep = Math.min(6.0, seed.tEffH + 1.0);
  console.log(`       seed ${seed.tEffH} h -> first hour ${firstStep} h`);
  assert.strictEqual(firstStep, 6.0);
});
check('empty tail seeds a neutral state', () => {
  const seed = seedTeff([], { dtH: 1 });
  assert.strictEqual(seed.tEffH, 0);
  assert.strictEqual(seed.bearingGrid, 0);
});

console.log('\n== [1d] shortest-arc interpolation (350 -> 10) ==');
check('interpolate15 expands 4x and passes through 0', () => {
  const out = interpolate15({ time: ['2026-09-11T00:00', '2026-09-11T01:00'], wind_speed_10m: [10, 20], wind_direction_10m: [350, 10], wind_gusts_10m: [12, 24] });
  assert.strictEqual(out.times.length, 5, '1 gap -> 4 + final');
  assert.strictEqual(out.times[0], '2026-09-11T00:00');
  assert.strictEqual(out.times[1], '2026-09-11T00:15');
  assert.strictEqual(out.times[4], '2026-09-11T01:00');
  assert.deepStrictEqual(out.dirs.map((d) => Math.round(d)), [350, 355, 0, 5, 10]);
  assert.ok(Math.abs(out.speeds[1] - 12.5) < 1e-9, `speed ${out.speeds[1]}`);
  assert.notStrictEqual(Math.round(out.dirs[2]), 180);
  console.log(`       dirs ${out.dirs.join(', ')}`);
});

console.log('\n== [2] gamma -> bearing_grid ==');
const meta = JSON.parse(fs.readFileSync(path.join(ROOT, 'public', 'meta.v1.json'), 'utf8'));
check('dir_true 0 -> bearing_grid 0.474 (gamma -0.474)', () => {
  const bg = gammaToGrid(0, meta.gamma_deg);
  assert.ok(Math.abs(bg - 0.474) < 1e-9, `got ${bg}`);
});

console.log('\n== [2b] buildSeriesFrom is the single 15-min construction path ==');
check('gamma applied and dtH honored', () => {
  const s = buildSeriesFrom(
    ['2026-09-11T00:00', '2026-09-11T00:15'],
    [12, 12], [0, 0], [16, 16], meta.gamma_deg, 0.25,
  );
  assert.strictEqual(s.length, 2);
  assert.ok(Math.abs(s[0].bearingGrid - 0.474) < 1e-9);
  assert.strictEqual(s[0].tEffH, 0.5);
  assert.strictEqual(s[1].tEffH, 0.75);
});

function synthMinutely(date) {
  const time = [], sp = [], dr = [], gu = [];
  for (let i = 0; i < 96; i++) {
    const h = Math.floor(i / 4), m = (i % 4) * 15;
    time.push(`${date}T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`);
    sp.push(12 + 4 * Math.sin(i / 6));
    dr.push((315 + 5 * Math.sin(i / 5) + 360) % 360);
    gu.push(18 + 4 * Math.sin(i / 6));
  }
  return { minutely_15: { time, wind_speed_10m: sp, wind_direction_10m: dr, wind_gusts_10m: gu } };
}
function synthHourly(date) {
  const time = [], sp = [], dr = [], gu = [];
  for (let d = -1; d <= 1; d++) {
    for (let h = 0; h < 24; h++) {
      const day = new Date(Date.parse(`${date}T00:00:00Z`) + d * 86400000).toISOString().slice(0, 10);
      time.push(`${day}T${String(h).padStart(2, '0')}:00`);
      sp.push(12 + 4 * Math.sin((d * 24 + h) / 6));
      dr.push((315 + 5 * Math.sin((d * 24 + h) / 5) + 360) % 360);
      gu.push(18);
    }
  }
  return { hourly: { time, wind_speed_10m: sp, wind_direction_10m: dr, wind_gusts_10m: gu } };
}

(async function main() {
  const DATE = '2026-09-11';
  const at1712 = new Date(Date.UTC(2026, 8, 11, 22, 12)); // 17:12 CDT
  const at1752 = new Date(Date.UTC(2026, 8, 11, 22, 52)); // 17:52 CDT

  console.log('\n== [3] 96-frame day from minutely_15 + currentIndex buckets ==');
  let data;
  try {
    data = await ingest({ json: synthMinutely(DATE), gamma: meta.gamma_deg, now: at1712 });
  } catch (e) {
    console.log(`  FAIL synthetic ingest: ${e.message}`);
    failures++;
    return finish();
  }
  console.log(`  synthetic minutely day: ${data.day.length} frames, stepMin ${data.stepMin}`);
  check('minutely path yields a 96-entry day, stepMin 15', () => {
    assert.strictEqual(data.day.length, 96);
    assert.strictEqual(data.stepMin, 15);
  });
  check('currentIndex 17:12 -> the 17:00 frame (index 68)', () => {
    assert.strictEqual(currentIndex(data.day, at1712), 68);
  });
  check('currentIndex 17:52 -> the 17:45 frame (index 71)', () => {
    assert.strictEqual(currentIndex(data.day, at1752), 71);
  });

  let fb;
  try {
    fb = await ingest({ json: synthHourly(DATE), gamma: meta.gamma_deg, now: at1712 });
  } catch (e) {
    console.log(`  FAIL fallback ingest: ${e.message}`);
    failures++;
    return finish();
  }
  console.log(`  fallback hourly->15min day: ${fb.day.length} frames, stepMin ${fb.stepMin}`);
  check('missing minutely_15 falls back to hourly 4x, still 96 frames', () => {
    assert.strictEqual(fb.day.length, 96);
    assert.strictEqual(fb.stepMin, 15);
    assert.strictEqual(currentIndex(fb.day, at1712), 68);
  });

  console.log('\n== [4] live Open-Meteo ingest + 96-frame field table ==');
  const tables = decodeTables(fs.readFileSync(path.join(ROOT, 'public', 'tables.v1.bin')));
  let live;
  try {
    live = await ingest({ gamma: meta.gamma_deg });
  } catch (e) {
    console.log(`  FAIL live ingest: ${e.message}`);
    failures++;
    return finish();
  }
  console.log(`  point ${live.point.lat},${live.point.lon} | local date ${chicagoNow().date} | ` +
    `series ${live.series.length} @ ${live.stepMin} min, today ${live.day.length}, current idx ${live.currentIndex}`);
  check('live day has 96 frames', () => assert.strictEqual(live.day.length, 96, `got ${live.day.length}`));

  const scratch = {
    out: new Float64Array(BATHY_CELLS),
    afterKs: new Float64Array(BATHY_CELLS),
    ts: new Float64Array(BATHY_CELLS),
  };
  console.log('  local time        mph  gust dir  bearing_grid  t_eff  Hs_max  roller');
  const frames = [];
  for (let i = 0; i < live.day.length; i++) {
    const e = live.day[i];
    const f = computeFrame(tables, e, { gamma: meta.gamma_deg, ...scratch });
    frames.push(f);
    if (i % 4 === 0) {
      console.log(`  ${e.time.replace('T', ' ')}  ${e.speedMph.toFixed(0).padStart(3)}  ` +
        `${e.gustMph.toFixed(0).padStart(3)}  ${e.dirTrueDeg.toFixed(0).padStart(3)}  ` +
        `${e.bearingGrid.toFixed(2).padStart(11)}  ${e.tEffH.toFixed(2).padStart(5)}  ` +
        `${f.maxHs.toFixed(2).padStart(6)}  ${f.rollerFt.toFixed(2).padStart(6)}`);
    }
  }
  check('all 96 frames produced a finite, non-negative lake-max Hs', () => {
    let calm = 0;
    for (const f of frames) {
      assert.ok(Number.isFinite(f.maxHs) && f.maxHs >= 0, `bad maxHs ${f.maxHs}`);
      if (f.maxHs === 0) calm++;
    }
    console.log(`       ${calm} calm frame(s) (<4 mph lull -> t_eff 0)`);
  });
  check('Hs_max cap: roller uses post-Ks pre-0.6d value', () => {
    for (const f of frames) {
      const d = tables.depth[f.maxIdx] * 0.25;
      const expect = Math.min(1.67 * f.afterKs[f.maxIdx], 0.78 * d);
      assert.ok(Math.abs(f.rollerFt - expect) < 1e-9, `roller ${f.rollerFt} vs ${expect}`);
    }
  });

  console.log('\n== [5] per-frame field benchmark (blending enabled) ==');
  const ITERS = 2;
  for (const e of live.day) computeFrame(tables, e, { gamma: meta.gamma_deg, ...scratch });
  const t0 = performance.now();
  for (let it = 0; it < ITERS; it++) for (const e of live.day) computeFrame(tables, e, { gamma: meta.gamma_deg, ...scratch });
  const msPerFrame = (performance.now() - t0) / (ITERS * live.day.length);
  console.log(`  ms/frame (blended, incl. lake-max scan): ${msPerFrame.toFixed(3)} (budget <= 6)`);
  check('budget <= 6 ms/frame', () => assert.ok(msPerFrame <= 6, `${msPerFrame} ms`));

  finish();
})().catch((e) => { console.error(e); failures++; finish(); });

function finish() {
  console.log(`\n${failures === 0 ? 'ALL TESTS PASSED' : failures + ' TEST(S) FAILED'}`);
  process.exit(failures === 0 ? 0 : 1);
}
