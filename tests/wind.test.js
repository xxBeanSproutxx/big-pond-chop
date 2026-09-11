'use strict';
// Stage 2 wind tests: t_eff vectors A-F, gamma mapping, live 24-hour table, perf.
// Run: node tests/wind.test.js
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { performance } = require('perf_hooks');
const { decodeTables, BATHY_CELLS } = require('../src/tables');
const { gammaToGrid, computeTeff, ingest, chicagoNow } = require('../src/wind');
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

console.log('\n== [1] t_eff persistence vectors A-F ==');
// NOTE (ambiguity): the spec formula says t_eff = min(6, prev + 1.0), and
// vectors C("...0, 1.0")/D(caps at 6 in 8 h) require +1.0, but the literal
// numbers printed for A/B use a 0.5-step. The normative formula + vectors C/D
// (and the task recap) win, so A/B are asserted at +1.0 here.
check('A: steady 12 mph from 315 for 8 h (+1.0/h per formula)', () => {
  const out = computeTeff(series(Array(8).fill(315), Array(8).fill(12)));
  console.log(`       A ${out.join(', ')}   (spec literal wrote 0.5,1,1.5,...,4)`);
  eq(out, [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.0, 6.0], 'A');
});
check('B: 5 h 20 mph 315 then +90 deg shift (+1.0/h per formula)', () => {
  const out = computeTeff(series([315, 315, 315, 315, 315, 0], Array(6).fill(20)));
  console.log(`       B ${out.join(', ')}   (spec literal wrote 0.5,1,1.5,2,2.5,0.5)`);
  eq(out, [0.5, 1.5, 2.5, 3.5, 4.5, 0.5], 'B');
});
check('C: lull (2 mph) resets, recovery climbs from 0', () => {
  const out = computeTeff(series([315, 315, 315, 315], [12, 12, 2, 10]));
  console.log(`       C ${out.join(', ')}   (third=0 from lull, fourth=0+1.0)`);
  eq(out, [0.5, 1.5, 0, 1.0], 'C');
});
check('D: saturates at 6.0 and stays', () => {
  const out = computeTeff(series(Array(14).fill(315), Array(14).fill(12)));
  console.log(`       D ${out.join(', ')}`);
  assert.strictEqual(out[11], 6.0, 'D hit cap');
  assert.strictEqual(out[13], 6.0, 'D stays capped');
});
check('E: exactly +30 deg counts as within tolerance', () => {
  const out = computeTeff(series([315, 345], [12, 12]));
  console.log(`       E ${out.join(', ')}`);
  eq(out, [0.5, 1.5], 'E');
});
check('F: +31 deg resets to 0.5', () => {
  const out = computeTeff(series([315, 346], [12, 12]));
  console.log(`       F ${out.join(', ')}`);
  eq(out, [0.5, 0.5], 'F');
});

console.log('\n== [2] gamma -> bearing_grid ==');
const meta = JSON.parse(fs.readFileSync(path.join(ROOT, 'public', 'meta.v1.json'), 'utf8'));
check('dir_true 0 -> bearing_grid 0.474 (gamma -0.474)', () => {
  const bg = gammaToGrid(0, meta.gamma_deg);
  console.log(`       gamma=${meta.gamma_deg} dir_true=0 -> bearing_grid=${bg}`);
  assert.ok(Math.abs(bg - 0.474) < 1e-9, `got ${bg}`);
});

console.log('\n== [3] live Open-Meteo ingest + 24-hour field table ==');
const tables = decodeTables(fs.readFileSync(path.join(ROOT, 'public', 'tables.v1.bin')));
(async function main() {
  let data;
  try {
    data = await ingest({ gamma: meta.gamma_deg });
  } catch (e) {
    console.log(`  FAIL live ingest: ${e.message}`);
    failures++;
    return finish();
  }
  console.log(`  point ${data.point.lat},${data.point.lon} | local date ${chicagoNow().date} | ` +
    `series ${data.series.length} h, today ${data.day.length} h, current idx ${data.currentIndex}`);
  assert.strictEqual(data.day.length, 24, `today should have 24 entries, got ${data.day.length}`);

  const scratch = {
    out: new Float64Array(BATHY_CELLS),
    afterKs: new Float64Array(BATHY_CELLS),
    ts: new Float64Array(BATHY_CELLS),
  };
  console.log('  local time        mph  gust dir  bearing_grid  t_eff  Hs_max  roller');
  const frames = [];
  for (let i = 0; i < data.day.length; i++) {
    const e = data.day[i];
    const f = computeFrame(tables, e, { gamma: meta.gamma_deg, ...scratch });
    frames.push(f);
    console.log(`  ${e.time.replace('T', ' ')}  ${e.speedMph.toFixed(0).padStart(3)}  ` +
      `${e.gustMph.toFixed(0).padStart(3)}  ${e.dirTrueDeg.toFixed(0).padStart(3)}  ` +
      `${e.bearingGrid.toFixed(2).padStart(11)}  ${e.tEffH.toFixed(1).padStart(5)}  ` +
      `${f.maxHs.toFixed(2).padStart(6)}  ${f.rollerFt.toFixed(2).padStart(6)}`);
  }
  check('all 24 frames produced a finite lake-max Hs', () => {
    for (const f of frames) assert.ok(Number.isFinite(f.maxHs) && f.maxHs > 0, `bad maxHs ${f.maxHs}`);
  });
  check('Hs_max cap: roller uses post-Ks pre-0.6d value', () => {
    for (const f of frames) {
      const d = tables.depth[f.maxIdx] * 0.25;
      const expect = Math.min(1.67 * f.afterKs[f.maxIdx], 0.78 * d);
      assert.ok(Math.abs(f.rollerFt - expect) < 1e-9, `roller ${f.rollerFt} vs ${expect}`);
    }
  });

  console.log('\n== [4] per-hour field benchmark (blending enabled) ==');
  const ITERS = 3;
  for (let w = 0; w < 2; w++) for (const e of data.day) computeFrame(tables, e, { gamma: meta.gamma_deg, ...scratch });
  const t0 = performance.now();
  for (let it = 0; it < ITERS; it++) for (const e of data.day) computeFrame(tables, e, { gamma: meta.gamma_deg, ...scratch });
  const msPerHour = (performance.now() - t0) / (ITERS * data.day.length);
  console.log(`  ms/hour (blended, incl. lake-max scan): ${msPerHour.toFixed(3)} (budget <= 6)`);
  check('budget <= 6 ms/hour', () => assert.ok(msPerHour <= 6, `${msPerHour} ms`));

  finish();
})().catch((e) => { console.error(e); failures++; finish(); });

function finish() {
  console.log(`\n${failures === 0 ? 'ALL TESTS PASSED' : failures + ' TEST(S) FAILED'}`);
  process.exit(failures === 0 ? 0 : 1);
}
