# big-pond-chop — BUILD SPEC (stage 4A: engine — 15-min time base, lazy frame pipeline, masked field smoothing, zoom-aware raster)

Status: **APPROVED by Reid 2026-09-11.** Stages 1-3 are frozen. Build **ONE commit**.

Follow the **ponytail ruleset (laziest correct implementation)**. Report the ACTUAL shipped API back.
If any number in this spec conflicts with observed reality, **trust reality and say so** — do not
burn budget reconciling a stale number.

## Goal

Move the app to a 15-minute time base (96 frames/day), replace the eager whole-day precompute with a
lazy frame builder + LRU cache, add water-masked field-domain smoothing, and make the display raster
zoom-aware — **without touching the physics, the bundle format, or the page chrome**.

## Files allowed to touch

- `src/wind.js`
- `src/render.js`
- `tests/wind.test.js`, `tests/render.test.js`
- `tools/bench_frames.js` (new)
- `docs/BUILD-SPEC-STAGE4A.md` (this file — you may append a `## Notes / shipped API` section)

**FROZEN — do not edit, do not "fix":** `src/wave-math.js`, `src/tables.js`,
`public/*` (`tables.v1.bin`, `meta.v1.json`, `warp.v1.json`, `spots.v1.json`),
`tests/parity.test.js`, `tests/ui.test.js`, `index.html`, `src/ui.js`.

## Context you need (measured — trust these over guesses)

- Today the app precomputes the whole 24-frame day in `mount()`; measured **11-14 ms per frame**
  (desktop headless Chromium), 265-335 ms/day. Most of that is `gatherRaster` + `p10` + copies,
  not the 3.5 ms of wave math.
- The overlay canvas is **384x392 px** and the map stretches it **up to 7.4x** when zoomed in
  (0.93x at fit, 2.63x at z13, 7.43x at z14) -> visible 100 m blocks. The bilinear gather also
  mixes land (value 0) with water values -> a colored fringe over the shoreline. Both are display
  bugs; the numbers in `public/tables.v1.bin` are correct and stay correct.
- Open-Meteo `minutely_15` at Mille Lacs is **native 15-min data** (verified: second differences are
  non-zero; hour marks agree with the hourly series exactly, max delta 0.000 mph), ~6 KB/day/variable.
- Physics live in `src/wave-math.js`: `computeField(tables, speedMph, dirTrueDeg, out, opts)` fills the
  capped Hs field per bathy cell; `opts.outAfterKs` (post-Ks Hs, ft) and `opts.outTs` (period, s) carry
  the per-cell values the readout needs. Do not change any of it.
- t_eff rule today (`wind.js` `computeTeff`): speed < 4 mph -> 0; bearing change > 30 deg -> 0.5;
  else `min(6.0, prev + 1.0)`. **The `+1.0` is PER HOUR** and must become per-step.

## 1. `src/wind.js` — 15-minute time base

1a. `buildUrl()`: add `&minutely_15=wind_speed_10m,wind_direction_10m,wind_gusts_10m`
    (keep the `hourly=` param — it is the fallback and the hour-mark cross-check).

1b. **Probe first (30 s, curl is fine):** does `minutely_15` honour `past_days=1`? Record the answer
    in your Notes section. If yes -> request it. If no -> request `minutely_15` with `forecast_days=2`
    only and rely on the seeding rule in 1d for persistence across midnight.

1c. New pure `interpolate15(fields, gammaDeg)` -> the same `{times, speeds, dirs, gusts}` shape
    4x-expanded: **linear** for speed/gust; **shortest-arc** for direction in TRUE bearing space
    (350 -> 10 interpolates through 0, never 180). Gamma is applied by the caller path, as today.

1d. Step-aware t_eff: `computeTeff(series, dtH = 1)` accumulates `prev + dtH`, caps at 6.0, and keeps
    the 4 mph floor and the `>30 deg -> 0.5` reset EXACTLY as they are (the reset is not scaled by dtH).
    **`dtH = 1` must reproduce today's numbers bit-for-bit** (existing tests pin this).
    Add `seedTeff(hourlyTail, { dtH: 1 })` -> `{ tEffH, bearingGrid }` computed over **yesterday's last
    up-to-6 hourly entries**, so the first frames of today inherit persistence across midnight.
    Skip seeding when the minutely series already includes a past day.

1e. `buildSeriesFrom(times, speeds, dirs, gusts, gammaDeg, dtH)` becomes the single construction path;
    `buildSeries(hourly, gamma)` stays as a `dtH = 1` wrapper (tests import it).

1f. `ingest()` returns additionally `stepMin: 15` (or 60 on the fallback path) and a `day` with
    **96 entries** for today. `currentIndex(day, now)` snaps to the current 15-min bucket in
    Chicago local time (17:12 -> the 17:00 frame; 17:52 -> the 17:45 frame).

1g. Fallback: if `json.minutely_15` is missing or empty -> build from hourly, then `interpolate15`
    to reach 96 frames (`stepMin` 15). Never throw on a missing `minutely_15`.

## 2. `src/render.js` — lazy pipeline + LRU + rAF-coalesced rendering

2a. `FRAME_MINUTES = 15`. `PLAY_INTERVAL_MS` stays **333** (a 96-frame loop is 32 s).

2b. Replace the whole-day precompute with `frameFor(idx)` lazy building + an LRU:
    - entry = `{ url, stats: { maxHs, maxIdx, rollerFt, hlMax, p10Ft, peakLat, peakLon, entry }, pinVals }`
      (`url` = the encoded data URL, so a re-visited frame needs no re-render).
    - cache key = `` `${idx}|${pinIdx}|${W}x${H}` ``; placing or clearing a pin CLEARS the cache.
    - max 8 entries, evict least-recently-used; expose a byte gauge for the bench.
    - `stats` must be identical to what the old `buildFrames()` produced (same math path, same scratch
      reuse — the pinned peak/roller/p10 numbers must not move).

2c. **rAF-coalesced rendering (required).** `input` on the scrubber and the play tick both set a
    pending frame index and schedule exactly ONE `requestAnimationFrame` that renders the LATEST
    pending index. Fast thumb dragging must never queue more than one render, and a stale index must
    never be painted after a newer one.

2d. Keep these exports and their signatures (tests import them):
    `computeFrame`, `gatherRaster`, `paintRaster`, `hmaxFt`, `gridToLonlat`, `lonlatToGrid`,
    `pickDisplayDims`, `displayBounds`, `bilinearSample`, `TILE_URL`, `TILE_ATTRIBUTION`,
    `TILE_MAX_ZOOM`, `OVERLAY_OPACITY`, `PLAY_INTERVAL_MS`, `SCALE_FT`.

2e. `?hour=17` still selects the 17:00 frame; add `?frame=<index>`. `body.dataset.hour` keeps the
    full ISO string (now with `:15`/`:30`/`:45`) and gains `data-step-min`.

2f. Keep `data-precomputeMs` / `data-frameMs` as the app's own timings (e2e recipes read them); on the
    lazy path report the most recent frame build's cost. Do not rename them.

2g. `mount()` internals may change, but **every DOM id it writes to must stay exactly as it is**
    (no chrome changes this stage; `index.html` is frozen).

## 3. `src/render.js` — display smoothing + zoom-aware raster

3a. `landMaskRaster(warp, tables, W, H)` -> `Float32Array` of land fraction per display pixel
    (`LAND_U16` -> 1). Cache per W x H.

3b. `smoothRaster(raster, landFrac, radius = 2)` -> a NEW `Float32Array`; separable 5-tap kernel;
    weights multiplied by `(1 - landFrac)` with weight normalization (`Σ w*v / Σ w`) so land never
    contributes. Pure-land pixels stay **exactly 0**; inputs are never mutated; the result never
    exceeds the input's max.

3c. `targetWidth(clientWidth, dpr, lo = 512, hi = 1536)`. Gather at that width instead of the
    hard-coded 384. Re-gather on `zoomend` + `resize`, **debounced 150 ms**, keeping the previous
    image visible until the new one is ready (no blank flash).

3d. Smoothing is **DISPLAY-ONLY**: the tap readout keeps reading `tables.depth` + `wave-math` at the
    tapped cell, and the header stats keep using the **unsmoothed** field. The palette
    (`colorForHs`) is unchanged.

3e. **Do NOT use CSS `filter: blur()`** anywhere (rejected: it blurs across the shoreline and cannot
    be masked). No `image-rendering` override — the overlay `<img>` stays default-smooth.

## 4. `tools/bench_frames.js` (new, Node-only, no DOM)

Print a table: ms/frame for (a) math only, (b) + gather @384, (c) + gather @780, (d) + smooth,
(e) + colorize; the 96-frame totals for each; and the LRU peak bytes at 780 px.
Exit 1 (with a clear FAIL line) if ms/frame @384 > 15, or @780 > 30, or LRU peak bytes > 8 MB.

## Done when

1. `node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js`
   — all four print `ALL TESTS PASSED`.
2. The parity numbers are **unchanged** versus stages 1-3 (same worst-|delta| and residual lines).
3. New tests exist and pass for: `dtH` t_eff (with the 0.5 reset and 4 mph floor unchanged),
   shortest-arc interpolation (350 -> 10 = 10 degrees, not 180), a 96-entry day, `currentIndex` at
   15-min buckets, `seedTeff` continuity across midnight, `smoothRaster` invariants (max not raised,
   pure land exactly 0, inputs unmutated), `targetWidth` clamps, LRU eviction order and the pinIdx in
   the key.
4. `node tools/bench_frames.js` prints **PASS** with the numbers above.
5. **ONE git commit**: `Stage 4A: 15-min time base, lazy frame pipeline, masked field smoothing, zoom-aware gather`
   — and the diff touches ONLY the allowed files.

## Out of scope (do not touch)

`index.html`, `src/ui.js`, `tests/ui.test.js` (stage 4B); the tier chip / compass badge / 12-h clock /
skeleton / touch targets (4B); `src/wave-math.js`, `src/tables.js`, `public/*` (frozen); the tap card
DOM; any palette change; any change to the SPM math, the bundle layout, the t_eff rule constants, or
the gamma mapping.

## Receipts to include in your final message

(a) the four suite tails; (b) the bench table + PASS; (c) `git show --stat` for your commit;
(d) the shipped API (exact new/changed signatures); (e) the `minutely_15` past_days finding;
(f) anything you could not do, stated plainly.

## Notes / shipped API

### `minutely_15` + `past_days=1` finding (1b)

**Honoured.** `GET …&minutely_15=wind_speed_10m,…&past_days=1&forecast_days=2` returns
`minutely_15` spanning `yesterday 00:00 → tomorrow 23:45` (288 points / 3 days), i.e. the
native past day is included exactly like `hourly`. Requested as-is; no `forecast_days`-only
workaround needed.

Consequence: `ingest()` always has a past day in the series, so **`seedTeff` is not wired into
the shipped path** — `computeTeff` runs over the whole 3-day series *before* `selectDay`, so
today's first frame already inherits yesterday's tail. `seedTeff` is still implemented, exported
and unit-tested as specified.

### Reality over spec (numbers that conflicted)

- **`stepMin` on the fallback is 15, not 60.** The fallback builds hourly then runs
  `interpolate15` to reach 96 frames; the *output* cadence is 15 min. Shipped `stepMin: 15` on
  both paths (the spec's "60 on the fallback path" describes the source cadence, not the frame
  cadence).
- **`smoothRaster` needs dims.** A flat `Float32Array` carries no shape, so the literal 3-arg
  signature cannot be separable/blur correctly. Shipped
  `smoothRaster(raster, landFrac, W, H, radius = 2)`.
- **Not every frame has waves.** At 15-min resolution a real sub-4 mph lull occurs; t_eff resets
  to 0 and the SPM field is legitimately all-zero for that frame. The old "every frame has
  `maxHs > 0`" assertion no longer holds and is now `maxHs >= 0` (the smoke suite reports the
  calm count).

### Shipped API

`src/wind.js` (new/changed):
```
buildUrl(lat, lon)                         // + &minutely_15=wind_speed_10m,wind_direction_10m,wind_gusts_10m
computeTeff(series, dtH = 1)               // +1.0*h per step; reset/floor unchanged; dtH=1 bit-identical
seedTeff(hourlyTail, { dtH = 1 } = {})     // -> { tEffH, bearingGrid } over last <=6 entries
interpolate15(fields, gammaDeg)            // -> { times, speeds, dirs, gusts } 4x, shortest-arc dirs
buildSeriesFrom(times, speeds, dirs, gusts, gammaDeg, dtH = 1)   // single construction path
buildSeries(hourly, gammaDeg)              // unchanged wrapper, dtH = 1
lerpAngle(a, b, f)                         // new pure helper
chicagoNow(now)                            // now also returns { minute }
currentIndex(day, now)                     // snaps to 15-min bucket
ingest(opts)                               // also returns { stepMin }
```

`src/render.js` (new/changed):
```
FRAME_MINUTES = 15
targetWidth(clientWidth, dpr, lo = 512, hi = 1536)
landMaskRaster(warp, tables, W, H)         // Float32Array land fraction, cached per WxH
smoothRaster(raster, landFrac, W, H, radius = 2)   // new Float32Array, masked separable binomial
cacheKey(idx, pinIdx, W, H)
frameBytes(entry)
createFrameCache({ max = 8, sizeOf = frameBytes }) // LRU with bytes/peakBytes/size/keys/clear
```
Unchanged exports kept with identical signatures: `SCALE_FT`, `TILE_URL`, `TILE_ATTRIBUTION`,
`TILE_MAX_ZOOM`, `OVERLAY_OPACITY`, `PLAY_INTERVAL_MS`, `gridToLonlat`, `lonlatToGrid`,
`displayBounds`, `pickDisplayDims`, `bilinearSample`, `gatherRaster`, `hmaxFt`, `computeFrame`,
`paintRaster`, `mount`.

`mount()` internals (lazy path): `frameFor(idx)` builds once per `` `${idx}|${pinIdx}|${W}x${H}` ``
and caches `{ url, stats, pinVals }`; placing/clearing a pin clears the cache; `rAF` coalesces
scrubber/play. `data-precomputeMs` = cumulative build ms, `data-frameMs` = most recent build ms.
`?hour=17` selects the 17:00 frame; `?frame=<index>` added; `body.dataset.stepMin` added.

### Bench (Node, `node tools/bench_frames.js`)

```
  stage                       width   ms/frame   96-frame
  (a) math only                 384       1.51      144.9
  (b) + gather                  384       3.05      293.2
  (c) + gather                  780       8.11      779.0
  (d) + smooth                  780      18.79     1803.8
  (e) + colorize                780      27.72     2661.2
  LRU peak bytes @780        : 2798368 (2.67 MB)
PASS
```
(Stable over runs; ~27.7-29.0 ms/frame @780 vs the 30 ms gate after the interior fast path in
`smoothRaster`. No CSS `blur()`/`image-rendering` was introduced.)

