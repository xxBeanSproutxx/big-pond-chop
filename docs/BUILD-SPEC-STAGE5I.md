# BUILD-SPEC — Stage 5I: wind badge flow-vector flip + copy

## Goal

Flip the `#wind-badge` compass arrow from into-wind (at the source) to the
downwind flow vector, and make the copy unambiguous (`From <SECTOR> <deg>°`,
aria "blowing toward"). Physics, badge CSS/layout, and the true-referenced
bearing are unchanged.

## Files allowed to touch

- `src/ui.js` — `compass()`
- `src/render.js` — badge block in `showFrame()`
- `index.html` — static `#wind-badge` placeholder
- `tests/ui.test.js` — block [7]
- `tools/qa/stage5_check.py` — `check_compass()`
- `tools/qa/wind_arrow_sweep.py` — new re-runnable sweep
- `docs/BUILD-SPEC-STAGE5I.md` — this file

Nothing else. `src/wind.js`, `src/wave-math.js`, `public/` must show zero diff.

## Done-when

- The five source/test files are edited exactly per §2 and nothing else changed.
- `node tests/parity.test.js`, `node tests/render.test.js`, `node tests/ui.test.js`,
  `node tests/wind.test.js` all pass (parity byte-identical; physics untouched).
- `tools/qa/stage5_check.py` runs to completion and check [6] `compass badge` is ok
  with the `(downwind)` label.
- `tools/qa/wind_arrow_sweep.py` reports `96/96 ok, 0 FAIL`.
- `git diff pre-stage5i -- src/wind.js src/wave-math.js public/` is empty.
- `git diff pre-stage5i --stat` shows only the seven files above.
- Commit on branch `stage5i` with message
  `Stage 5I: wind badge flow-vector flip + copy (from-text, downwind arrow)`.

## Out of scope

Merging, pushing, editing any other file, touching physics, changing badge
CSS/layout, adding config knobs, fixing anything noticed (report it instead).

## §2 Exact change spec

### Change 1 — `src/ui.js` (compass) — flip to flow vector

```js
// Compass metadata. Text fields describe the SOURCE (fromDeg); arrowDeg points
// DOWNWIND (flow vector = from + 180) so the arrow reads as "where the air is
// going". Calm (< 3 mph) or a non-finite bearing -> all-null fields.
function compass(bearingDeg, speedMph) {
  if (speedMph != null) {
    const s = Number(speedMph);
    if (!Number.isFinite(s) || s < CALM_MPH)
      return { sector: 'Calm', degText: '', fromDeg: null, arrowDeg: null };
  }
  const b = Number(bearingDeg);
  if (!Number.isFinite(b)) return { sector: 'Calm', degText: '', fromDeg: null, arrowDeg: null };
  const deg = normalizeDeg(b);
  return {
    sector: SECTORS[Math.round(deg / 45) % 8],
    degText: `${Math.round(deg)}°`,
    fromDeg: deg,
    arrowDeg: (deg + 180) % 360,
  };
}
```

(`fromDeg` is new — it exists so the aria label and the harness can name the
source bearing without re-deriving it.)

### Change 2 — `src/render.js`, badge block — copy + aria

```js
    const c = ui.compass(e.dirTrueDeg, e.speedMph);
    if (c.arrowDeg == null) {
      badgeArrow.style.display = 'none';
      badgeText.textContent = 'Calm';
      windBadge.setAttribute('aria-label', 'Wind calm');
    } else {
      badgeArrow.style.display = 'block';
      badgeArrow.style.transform = `rotate(${c.arrowDeg}deg)`; // downwind flow vector
      badgeText.textContent = `From ${c.sector} ${c.degText}`;
      windBadge.setAttribute('aria-label',
        `Wind from ${c.sector} at ${Math.round(c.fromDeg)} degrees, ` +
        `blowing toward ${Math.round(c.arrowDeg)} degrees`);
    }
```

Text: `S 188°` → **`From S 188°`**.

### Change 3 — `index.html`, static placeholder (pre-first-frame only)

```html
    <div id="wind-badge" role="img"
         aria-label="Wind from NW at 315 degrees, blowing toward SE at 135 degrees">
      ...
      <span id="wind-badge-text">From NW 315°</span>
```

### Change 4 — `tools/qa/stage5_check.py`, `check_compass()` — new contract

```python
    from_deg = (v["grid"] + gamma) % 360      # source bearing shown in the text
    expected_arrow = (from_deg + 180) % 360   # flow vector: arrow points DOWNWIND
    text_ok = bool(re.match(r"^From [NSEW]{1,2} \d{1,3}°$", v["text"]))
    m = re.match(r"^From [NSEW]{1,2} (\d{1,3})°$", v["text"])
    text_deg_ok = bool(m) and abs(int(m.group(1)) - round(from_deg)) <= 0.5
    ...
    delta = min(abs(angle - expected_arrow), 360 - abs(angle - expected_arrow))
    ...
    aria_ok = bool(v["aria"]) and re.match(
        r"^Wind from [NSEW]{1,2} at \d+ degrees, blowing toward \d+ degrees$",
        v["aria"]) is not None
    ok = text_ok and text_deg_ok and angle is not None and delta <= 1.5 and in_quadrant \
         and clear_zoom and aria_ok
    record(6, "compass badge", ok,
           "text='%s' from=%.2f° arrow=%.2f° expected=%.2f° (downwind) delta=%.2f "
           "top-right=%s clear-zoom=%s aria='%s'"
           % (v["text"], from_deg, angle if angle is not None else float("nan"),
              expected_arrow, delta, in_quadrant, clear_zoom, v["aria"]))
```

Calm branch unchanged.

### Change 5 — `tests/ui.test.js`, block [7] — new expectations

```js
console.log('\n== [7] stage-4b compass (from-text, downwind arrow) ==');
check('sector + degText are the SOURCE; arrowDeg is DOWNWIND (from + 180)', () => {
  assert.deepStrictEqual(ui.compass(0, 10),   { sector: 'N',  degText: '0°',   fromDeg: 0,   arrowDeg: 180 });
  assert.deepStrictEqual(ui.compass(45, 10),  { sector: 'NE', degText: '45°',  fromDeg: 45,  arrowDeg: 225 });
  assert.deepStrictEqual(ui.compass(90, 10),  { sector: 'E',  degText: '90°',  fromDeg: 90,  arrowDeg: 270 });
  assert.deepStrictEqual(ui.compass(180, 10), { sector: 'S',  degText: '180°', fromDeg: 180, arrowDeg: 0 });
  assert.deepStrictEqual(ui.compass(315, 10), { sector: 'NW', degText: '315°', fromDeg: 315, arrowDeg: 135 });
  assert.deepStrictEqual(ui.compass(359, 10), { sector: 'N',  degText: '359°', fromDeg: 359, arrowDeg: 179 });
});
check('wrap-around normalizes; arrowDeg === (normalizeDeg(b) + 180) % 360', () => {
  assert.deepStrictEqual(ui.compass(360, 10), { sector: 'N', degText: '0°', fromDeg: 0, arrowDeg: 180 });
  assert.deepStrictEqual(ui.compass(720, 10), { sector: 'N', degText: '0°', fromDeg: 0, arrowDeg: 180 });
  assert.deepStrictEqual(ui.compass(-45, 10), { sector: 'NW', degText: '315°', fromDeg: 315, arrowDeg: 135 });
  for (const b of [0, 45, 90, 180, 315, 359, 360, 722, -90]) {
    assert.strictEqual(ui.compass(b, 10).arrowDeg, (ui.normalizeDeg(b) + 180) % 360);
  }
});
check('calm (< 3 mph) -> Calm with null arrow', () => {
  eq(ui.compass(315, 2), { sector: 'Calm', degText: '', fromDeg: null, arrowDeg: null });
  eq(ui.compass(315, 0), { sector: 'Calm', degText: '', fromDeg: null, arrowDeg: null });
  eq(ui.compass(NaN, 10), { sector: 'Calm', degText: '', fromDeg: null, arrowDeg: null });
});
```

## Gate commands

```
node tests/parity.test.js
node tests/render.test.js
node tests/ui.test.js
node tests/wind.test.js
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/wind_arrow_sweep.py
git diff pre-stage5i -- src/wind.js src/wave-math.js public/
git diff pre-stage5i --stat
```

## Rollback

`git checkout pre-stage5i` (tag) restores the pre-Stage-5I tree.
