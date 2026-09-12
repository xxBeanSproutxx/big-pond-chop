'use strict';
// Stage 3 UI helper tests: palette stops, headline formatting, spot naming, sectors.
// Run: node tests/ui.test.js
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const ui = require('../src/ui');

const ROOT = path.join(__dirname, '..');
const spots = JSON.parse(fs.readFileSync(path.join(ROOT, 'public', 'spots.v1.json'), 'utf8'));
const meta = JSON.parse(fs.readFileSync(path.join(ROOT, 'public', 'meta.v1.json'), 'utf8'));
const features = spots.features;
const centroid = ui.centroidOfCorners(meta.wgs84_corners);

let failures = 0;
function check(name, fn) {
  try { fn(); console.log(`  ok   ${name}`); }
  catch (e) { failures++; console.log(`  FAIL ${name}: ${e.message}`); }
}
const eq = (a, b, m) => assert.deepStrictEqual(a, b, m);

console.log('\n== [1] palette stops (colorForHs) ==');
check('stop boundaries are exact, land/flat water transparent', () => {
  eq(ui.colorForHs(1), [6, 182, 212, 255], '1 ft cyan');
  eq(ui.colorForHs(2), [245, 158, 11, 255], '2 ft amber');
  eq(ui.colorForHs(3.5), [234, 88, 12, 255], '3.5 ft orange-red');
  eq(ui.colorForHs(4.5), [220, 38, 38, 255], '4.5 ft crimson');
  eq(ui.colorForHs(5.5), [190, 24, 93, 255], '5.5 ft magenta');
  eq(ui.colorForHs(6), [190, 24, 93, 255], '6+ clamps to magenta');
  eq(ui.colorForHs(0), [0, 0, 0, 0], 'flat water');
  eq(ui.colorForHs(-2), [0, 0, 0, 0], 'land/negative');
  eq(ui.colorForHs(NaN), [0, 0, 0, 0], 'NaN');
});
check('interpolates smoothly between stops and stays opaque on water', () => {
  const a = ui.colorForHs(1), b = ui.colorForHs(2), mid = ui.colorForHs(1.5);
  for (let k = 0; k < 3; k++) {
    assert.ok(mid[k] >= Math.min(a[k], b[k]) && mid[k] <= Math.max(a[k], b[k]),
      `channel ${k} outside segment bounds`);
  }
  assert.strictEqual(mid[3], 255, 'water alpha opaque');
  assert.notDeepStrictEqual(mid, a);
  assert.notDeepStrictEqual(mid, b);
  console.log(`       1.5 ft -> rgb(${mid.slice(0, 3).join(',')})`);
});
check('legend breakpoints and overlay opacity are pinned', () => {
  eq(ui.HS_BREAKS, [0, 1, 2, 3.5, 4.5, 6]);
  assert.strictEqual(ui.OVERLAY_OPACITY, 0.72);
});

console.log('\n== [2] percentile (p10) ==');
check('percentile ignores land/zero cells and interpolates', () => {
  assert.strictEqual(ui.percentile([1, 2, 3, 4, 5], 0), 1);
  assert.strictEqual(ui.percentile([1, 2, 3, 4, 5], 1), 5);
  assert.strictEqual(ui.percentile([1, 2, 3, 4, 5], 0.5), 3);
  assert.strictEqual(ui.p10([0, 0, 0]), 0, 'all land -> 0');
  const v = [0, 0, ...Array.from({ length: 100 }, (_, i) => i + 1)];
  const p10 = ui.p10(v);
  assert.ok(Math.abs(p10 - 10.9) < 1e-9, `p10 ${p10}`);
  console.log(`       p10 of 1..100 = ${p10}`);
});

console.log('\n== [3] sectors ==');
check('8-way sector relative to the lake centroid', () => {
  assert.strictEqual(ui.sectorFor(centroid.lat + 0.1, centroid.lon, centroid), 'N');
  assert.strictEqual(ui.sectorFor(centroid.lat, centroid.lon + 0.1, centroid), 'E');
  assert.strictEqual(ui.sectorFor(centroid.lat - 0.1, centroid.lon, centroid), 'S');
  assert.strictEqual(ui.sectorFor(centroid.lat, centroid.lon - 0.1, centroid), 'W');
  console.log(`       centroid ${centroid.lat.toFixed(4)}, ${centroid.lon.toFixed(4)}`);
});

console.log('\n== [4] spot naming / describePin ==');
check('a point near Spirit Island names the feature', () => {
  const lat = 46.15173 + 0.01, lon = -93.64465;
  const spot = ui.nameSpot(lat, lon, features, { name: 'S', shore: false });
  assert.strictEqual(spot.kind, 'feature', 'expected a feature');
  assert.strictEqual(spot.name, 'Spirit Island');
  const line = ui.describePin(spot);
  assert.ok(/^\d+\.\d mi [NSEW]{1,2} of Spirit Island$/.test(line), `got "${line}"`);
  console.log(`       ${line}`);
});
check('a mid-basin point falls back to Open water - <sector> Basin', () => {
  const spot = ui.nameSpot(centroid.lat, centroid.lon, features, { name: 'SW', shore: false });
  assert.strictEqual(spot.kind, 'open');
  assert.strictEqual(ui.describePin(spot), 'Open water - SW Basin');
});
check('a near-shore open-water point says Shore', () => {
  const spot = ui.nameSpot(centroid.lat, centroid.lon, features, { name: 'NW', shore: true });
  assert.strictEqual(ui.describePin(spot), 'Open water - NW Shore');
});
check('beyond 4 km is open water even if a feature is nearest', () => {
  const spot = ui.nameSpot(centroid.lat, centroid.lon, features, { name: 'SW', shore: false });
  assert.ok(spot.kind === 'open');
});

console.log('\n== [5] headline (formatHeadline) ==');
const frame = {
  p10Ft: 0.8, maxHsFt: 3.4, rollerFt: 3.93,
  peakLat: 46.15173, peakLon: -93.64465,
  features, sector: { name: 'S', shore: false },
};
check('line 1 is a lake-wide range, one decimal', () => {
  const h = ui.formatHeadline(frame);
  assert.strictEqual(h.range, 'Waves: 0.8 - 3.4 ft');
  console.log(`       ${h.range}`);
});
check('line 2 pairs the peak roller with a short location label', () => {
  const h = ui.formatHeadline(frame);
  assert.ok(h.peak.startsWith('Peak: 3.9 ft · '), h.peak);
  assert.ok(h.peak.endsWith('Spirit Island'), h.peak);
  console.log(`       ${h.peak}`);
});
check('never a bare single number (range + peak words present)', () => {
  const h = ui.formatHeadline(frame);
  assert.ok(h.range.includes(' - '), 'range missing dash');
  assert.ok(/peak/i.test(h.peak), 'peak word missing');
  const open = ui.formatHeadline({
    ...frame, peakLat: centroid.lat, peakLon: centroid.lon, sector: { name: 'SW', shore: false },
  });
  assert.strictEqual(open.peak, 'Peak: 3.9 ft · SW Basin');
  const shore = ui.formatHeadline({
    ...frame, peakLat: centroid.lat, peakLon: centroid.lon, sector: { name: 'NE', shore: true },
  });
  assert.strictEqual(shore.peak, 'Peak: 3.9 ft · NE Shore');
  console.log(`       ${open.peak} / ${shore.peak}`);
});

console.log('\n== [6] stage-4b windLine ==');
check('normal, calm, and missing gust', () => {
  assert.strictEqual(ui.windLine(14, 26), 'Wind: 14 mph · Gusts 26 mph');
  assert.strictEqual(ui.windLine(14.4, 25.6), 'Wind: 14 mph · Gusts 26 mph');
  assert.strictEqual(ui.windLine(2.9, 26), 'Wind: calm');
  assert.strictEqual(ui.windLine(0, 0), 'Wind: calm');
  assert.strictEqual(ui.windLine(14), 'Wind: 14 mph');
  assert.strictEqual(ui.windLine(14, NaN), 'Wind: 14 mph');
  assert.strictEqual(ui.windLine(14, undefined), 'Wind: 14 mph');
  assert.strictEqual(ui.windLine(3, 5), 'Wind: 3 mph · Gusts 5 mph');
});
check('never emits NaN / undefined / Infinity', () => {
  for (const [s, g] of [[NaN, 10], [Infinity, 10], [10, Infinity], [undefined, undefined], [10, null]]) {
    const out = ui.windLine(s, g);
    assert.ok(!/NaN|undefined|Infinity/.test(out), `bad output "${out}"`);
  }
});

console.log('\n== [7] stage-4b compass ==');
check('sector + degText at the 8 principal bearings', () => {
  assert.deepStrictEqual(ui.compass(0, 10), { sector: 'N', degText: '0°', arrowDeg: 0 });
  assert.deepStrictEqual(ui.compass(45, 10), { sector: 'NE', degText: '45°', arrowDeg: 45 });
  assert.deepStrictEqual(ui.compass(90, 10), { sector: 'E', degText: '90°', arrowDeg: 90 });
  assert.deepStrictEqual(ui.compass(180, 10), { sector: 'S', degText: '180°', arrowDeg: 180 });
  assert.deepStrictEqual(ui.compass(315, 10), { sector: 'NW', degText: '315°', arrowDeg: 315 });
  assert.deepStrictEqual(ui.compass(359, 10), { sector: 'N', degText: '359°', arrowDeg: 359 });
});
check('wrap-around normalizes, arrowDeg === normalizeDeg(bearing)', () => {
  assert.deepStrictEqual(ui.compass(360, 10), { sector: 'N', degText: '0°', arrowDeg: 0 });
  assert.deepStrictEqual(ui.compass(720, 10), { sector: 'N', degText: '0°', arrowDeg: 0 });
  assert.deepStrictEqual(ui.compass(-45, 10), { sector: 'NW', degText: '315°', arrowDeg: 315 });
  for (const b of [0, 45, 90, 180, 315, 359, 360, 722, -90]) {
    assert.strictEqual(ui.compass(b, 10).arrowDeg, ui.normalizeDeg(b));
  }
});
check('calm (< 3 mph) -> Calm with null arrow', () => {
  eq(ui.compass(315, 2), { sector: 'Calm', degText: '', arrowDeg: null });
  eq(ui.compass(315, 0), { sector: 'Calm', degText: '', arrowDeg: null });
  eq(ui.compass(NaN, 10), { sector: 'Calm', degText: '', arrowDeg: null });
});

console.log('\n== [8] stage-4b comfortTier ==');
check('locked boundaries (first match wins)', () => {
  assert.strictEqual(ui.comfortTier({ maxHsFt: 1, rollerFt: 4.0, hlMax: 0.01 }).key, 'red');
  assert.strictEqual(ui.comfortTier({ maxHsFt: 3.4, rollerFt: 3.9, hlMax: 0.01 }).key, 'amber');
  assert.strictEqual(ui.comfortTier({ maxHsFt: 3.5, rollerFt: 1, hlMax: 0.01 }).key, 'amber');
  assert.strictEqual(ui.comfortTier({ maxHsFt: 2.0, rollerFt: 0.5, hlMax: 0.01 }).key, 'yellow');
  assert.strictEqual(ui.comfortTier({ maxHsFt: 0.5, rollerFt: 1.5, hlMax: 0.01 }).key, 'yellow');
  assert.strictEqual(ui.comfortTier({ maxHsFt: 1.99, rollerFt: 1.49, hlMax: 0.01 }).key, 'green');
});
check('H/L 0.055 alone is red even with tiny waves', () => {
  const t = ui.comfortTier({ maxHsFt: 0.2, rollerFt: 0.2, hlMax: 0.055 });
  assert.strictEqual(t.key, 'red');
  assert.strictEqual(t.label, 'Dangerous · Stay Home');
  assert.strictEqual(ui.comfortTier({ maxHsFt: 5.0, rollerFt: 0, hlMax: 0 }).key, 'red');
});
check('labels are exact', () => {
  assert.strictEqual(ui.comfortTier({ maxHsFt: 6, rollerFt: 6, hlMax: 0.1 }).label, 'Dangerous · Stay Home');
  assert.strictEqual(ui.comfortTier({ maxHsFt: 4, rollerFt: 0, hlMax: 0 }).label, 'Heavy Rollers');
  assert.strictEqual(ui.comfortTier({ maxHsFt: 2.5, rollerFt: 0, hlMax: 0 }).label, 'Walleye Chop');
  assert.strictEqual(ui.comfortTier({ maxHsFt: 0.5, rollerFt: 0.5, hlMax: 0 }).label, 'Fishable · Light Chop');
});
check('missing / NaN inputs never throw or return undefined', () => {
  for (const s of [{}, null, undefined, { maxHsFt: NaN, rollerFt: NaN, hlMax: NaN }]) {
    const t = ui.comfortTier(s);
    assert.strictEqual(t.key, 'green');
    assert.strictEqual(t.label, 'Fishable · Light Chop');
  }
});
check('monotonic: raising max or roller never yields a less-severe tier', () => {
  const rank = { green: 0, yellow: 1, amber: 2, red: 3 };
  const tier = (m, r) => rank[ui.comfortTier({ maxHsFt: m, rollerFt: r, hlMax: 0 }).key];
  for (let m = 0; m <= 6.01; m += 0.1) {
    for (let r = 0; r < 5; r += 0.1) {
      assert.ok(tier(m + 0.1, r) >= tier(m, r), `max ${m}->${m + 0.1} @ roller ${r}`);
      assert.ok(tier(m, r + 0.1) >= tier(m, r), `roller ${r}->${r + 0.1} @ max ${m}`);
    }
  }
});

console.log('\n== [9] stage-4b formatClockLocal ==');
check('12-hour wall clock in America/Chicago', () => {
  assert.strictEqual(ui.formatClockLocal('2026-09-11T00:00'), '12:00 AM CDT');
  assert.strictEqual(ui.formatClockLocal('2026-09-11T12:00'), '12:00 PM CDT');
  assert.strictEqual(ui.formatClockLocal('2026-09-11T17:15'), '5:15 PM CDT');
  assert.strictEqual(ui.formatClockLocal('2026-09-11T05:00'), '5:00 AM CDT');
});
check('winter is CST; the fall-back DST day does not throw', () => {
  assert.strictEqual(ui.formatClockLocal('2026-01-15T17:15'), '5:15 PM CST');
  const before = ui.formatClockLocal('2026-11-01T00:30');
  const after = ui.formatClockLocal('2026-11-01T03:30');
  assert.ok(/^\d{1,2}:\d{2} (AM|PM) C[SD]T$/.test(before), before);
  assert.ok(/^\d{1,2}:\d{2} (AM|PM) C[SD]T$/.test(after), after);
  console.log(`       ${before} / ${after}`);
});

console.log('\n== [10] stage-5b rampGradient ==');
check('ramp gradient contains the six Hs stops in order', () => {
  const g = ui.rampGradient();
  const stops = [
    ['rgb(30, 64, 175)', '0%'],
    ['rgb(6, 182, 212)', '16.7%'],
    ['rgb(245, 158, 11)', '33.3%'],
    ['rgb(234, 88, 12)', '50%'],
    ['rgb(220, 38, 38)', '66.7%'],
    ['rgb(190, 24, 93)', '100%'],
  ];
  assert.ok(g.startsWith('linear-gradient(90deg, '), g);
  let at = -1;
  for (const [rgb, pct] of stops) {
    const idx = g.indexOf(`${rgb} ${pct}`);
    assert.ok(idx > at, `missing or out of order: ${rgb} ${pct} in ${g}`);
    at = idx;
  }
  console.log(`       ${g}`);
});

console.log('\n== [11] stage-5d dayLabel ==');
check('short + long weekday from calendar math (no TZ-parse)', () => {
  assert.strictEqual(ui.dayLabel('2026-09-11T00:00'), 'Fri 11');
  assert.strictEqual(ui.dayLabel('2026-09-11T00:00', true), 'Friday 11');
  assert.strictEqual(ui.dayLabel('2026-09-17T00:00'), 'Thu 17');
  assert.strictEqual(ui.dayLabel('2026-09-17T00:00', true), 'Thursday 17');
  assert.strictEqual(ui.dayLabel('2026-09-04T12:00'), 'Fri 4');
  assert.strictEqual(ui.dayLabel('2026-09-04T12:00', true), 'Friday 4');
  console.log(`       ${ui.dayLabel('2026-09-11T00:00')} / ${ui.dayLabel('2026-09-11T00:00', true)}`);
});
check('bad input -> empty string', () => {
  for (const bad of ['', 'nonsense', null, undefined, '2026-13-45', '2026-02-30']) {
    assert.strictEqual(ui.dayLabel(bad), '', `bad ${bad}`);
    assert.strictEqual(ui.dayLabel(bad, true), '', `bad long ${bad}`);
  }
});

console.log(`\n${failures === 0 ? 'ALL TESTS PASSED' : failures + ' TEST(S) FAILED'}`);
process.exit(failures === 0 ? 0 : 1);
