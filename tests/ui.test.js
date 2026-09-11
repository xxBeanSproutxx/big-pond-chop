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
check('a mid-basin point falls back to Open water - <sector> basin', () => {
  const spot = ui.nameSpot(centroid.lat, centroid.lon, features, { name: 'SW', shore: false });
  assert.strictEqual(spot.kind, 'open');
  assert.strictEqual(ui.describePin(spot), 'Open water - SW basin');
});
check('a near-shore open-water point says shore', () => {
  const spot = ui.nameSpot(centroid.lat, centroid.lon, features, { name: 'NW', shore: true });
  assert.strictEqual(ui.describePin(spot), 'Open water - NW shore');
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
check('line 2 pairs the peak roller with a location label', () => {
  const h = ui.formatHeadline(frame);
  assert.ok(h.peak.startsWith('Peak roller 3.9 ft at '), h.peak);
  assert.ok(h.peak.includes('Spirit Island area (S basin)'), h.peak);
  console.log(`       ${h.peak}`);
});
check('never a bare single number (range + peak words present)', () => {
  const h = ui.formatHeadline(frame);
  assert.ok(h.range.includes(' - '), 'range missing dash');
  assert.ok(/peak/i.test(h.peak), 'peak word missing');
  const open = ui.formatHeadline({
    ...frame, peakLat: centroid.lat, peakLon: centroid.lon, sector: { name: 'SW', shore: false },
  });
  assert.strictEqual(open.peak, 'Peak roller 3.9 ft at SW basin');
  console.log(`       ${open.peak}`);
});

console.log(`\n${failures === 0 ? 'ALL TESTS PASSED' : failures + ' TEST(S) FAILED'}`);
process.exit(failures === 0 ? 0 : 1);
