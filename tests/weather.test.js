'use strict';
// v1.1 weather fields: URL carries temp/precip unit params; parse fixture has
// tempF/precipIn with null passthrough.
const assert = require('assert');
const { buildUrl, buildDualUrl, buildSeriesFrom, DEFAULT_POINT, SHORE_POINT } = require('../src/wind');

let failures = 0;
function check(name, fn) {
  try { fn(); console.log(`  ok   ${name}`); }
  catch (e) { failures++; console.log(`  FAIL ${name}: ${e.message}`); }
}

console.log('\n== [v1.1] URL carries temp + precip unit params ==');
check('buildUrl includes temperature_unit and precipitation_unit', () => {
  const u = buildUrl(46.22, -93.657);
  assert.ok(u.includes('temperature_unit=fahrenheit'), 'missing temperature_unit');
  assert.ok(u.includes('precipitation_unit=inch'), 'missing precipitation_unit');
  assert.ok(u.includes('precipitation_probability'), 'missing precipitation_probability');
});
check('buildDualUrl includes temperature_unit and precipitation_unit', () => {
  const u = buildDualUrl(DEFAULT_POINT, SHORE_POINT);
  assert.ok(u.includes('temperature_unit=fahrenheit'), 'dual missing temperature_unit');
  assert.ok(u.includes('precipitation_unit=inch'), 'dual missing precipitation_unit');
});
check('URL still has wind_speed_unit, hourly, minutely_15, forecast_days', () => {
  const u = buildUrl(1, 2);
  assert.ok(u.includes('wind_speed_unit=mph'), 'wind unit gone');
  assert.ok(u.includes('hourly='), 'hourly param gone');
  assert.ok(u.includes('minutely_15='), 'minutely_15 param gone');
  assert.ok(u.endsWith('forecast_days=2'), 'forecast_days suffix gone');
});

console.log('\n== [v1.1] buildSeriesFrom with temp/precip arrays ==');
check('passes tempF and precipIn to entries', () => {
  const s = buildSeriesFrom(
    ['2026-09-11T00:00', '2026-09-11T00:15'],
    [10, 12], [0, 0], [14, 16], 0, 1,
    [72, 68], [0.0, 0.05],
  );
  assert.strictEqual(s.length, 2);
  assert.strictEqual(s[0].tempF, 72);
  assert.strictEqual(s[0].precipIn, 0);
  assert.strictEqual(s[1].tempF, 68);
  assert.strictEqual(s[1].precipIn, 0.05);
});
check('null values pass through as null', () => {
  const s = buildSeriesFrom(
    ['2026-09-11T00:00'], [10], [0], [14], 0, 1,
    [null], [null],
  );
  assert.strictEqual(s[0].tempF, null);
  assert.strictEqual(s[0].precipIn, null);
});
check('missing arrays -> null fields', () => {
  const s = buildSeriesFrom(['2026-09-11T00:00'], [10], [0], [14], 0);
  assert.strictEqual(s[0].tempF, null);
  assert.strictEqual(s[0].precipIn, null);
  assert.strictEqual(s[0].precipProb, null);
});
check('undefined in array -> null', () => {
  const s = buildSeriesFrom(
    ['2026-09-11T00:00'], [10], [0], [14], 0, 1,
    [undefined], [undefined], [undefined],
  );
  assert.strictEqual(s[0].tempF, null);
  assert.strictEqual(s[0].precipIn, null);
  assert.strictEqual(s[0].precipProb, null);
});
check('passes precipProb (chance %) to entries', () => {
  const s = buildSeriesFrom(
    ['2026-09-11T00:00', '2026-09-11T00:15'],
    [10, 12], [0, 0], [14, 16], 0, 1,
    [72, 68], [0.0, 0.05], [30, 45],
  );
  assert.strictEqual(s[0].precipProb, 30);
  assert.strictEqual(s[1].precipProb, 45);
});

console.log(`\n${failures === 0 ? 'ALL TESTS PASSED' : failures + ' TEST(S) FAILED'}`);
process.exit(failures === 0 ? 0 : 1);