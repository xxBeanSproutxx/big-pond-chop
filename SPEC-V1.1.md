# SPEC — v1.1 "decorate the proven deck" (big-pond-chop, branch v1.1)

## Goal
Add the three missing features to v1's PROVEN UI — rain line, temps, sunrise/sunset —
with the wind path byte-for-byte untouched. v1 stays the engine, the fetch stays one
call, the deck keeps its structure. This is decoration, not architecture.

## Files allowed to touch
- `src/wind.js` (add 2 fields to the existing Open-Meteo URL + parse them — nothing else)
- `src/render.js` (deck lanes + sun tick calls only)
- `index.html` (minimal CSS for the two new lanes)
- `src/sun-times.mjs` (NEW — crib EXACTLY from big-pond-chop-v2; it is tested there)
- `sw.js` (cache bump ONLY: bpc-cache-v1 → bpc-cache-v2, plus one SHELL line for sun-times.mjs)
- `tests/**` (one new suite + fixtures only)

## Out of scope (hard bans — do not touch)
- The wind path: `computeFrame`, `wave-math.js`, `tables.js`, any wave/Hs computation, the
  v1 impact/tape scrub math. If a diff touches any of these, the implementation is WRONG.
- No delay math, no worker, no new fetches, no model blending, no 15-day horizon.
- No redesign of the 62px deck beyond adding lanes inside it.

## Context you need
- v1 samples Open-Meteo native 15-min series for Mille Lacs (44.0, -93.5-ish — read the
  exact coords from src/wind.js). Adding `&temperature_unit=fahrenheit` and `&precipitation_unit=inch`
  to the EXISTING buildUrl()/buildDualUrl() adds `temperature_2m` and `precipitation`
  to the same hourly/15-min response. Parse them alongside wind; missing values → null
  (render skips). DO NOT change cache headers, timezone, past_days, or horizon params.
- Sunrise/sunset util: copy `/home/reid/projects/big-pond-chop-v2/src/sun-times.mjs`
  verbatim, and its tests from `/home/reid/projects/big-pond-chop-v2/tests/sun-times.test.mjs`.
  Call it with the lake center coords already in wind.js.
- The deck is built per-day in render.js (~line 1000+, `buildDeck` region; see
  `pxPerDay`, `dayPartitions`, `.day-heat` wind ribbon with embedded mph labels).
  Study it before writing. v2's working implementations to crib: rain SVG polyline +
  under-fill + 2.5px drizzle floor + peak labels with droplet (see
  `git -C /home/reid/projects/big-pond-chop-v2 show ef52999:src/render.js`, search
  `precip`); heat-mapped temp labels (search `tempLabelColor` in the same file —
  <=40F icy blue, 60s neutral, >=85F amber).
- All lane work happens INSIDE each existing day block of the track-tape. Layers top
  to bottom: temp labels (~12px), rain line (~14px SVG), existing wind ribbon (unchanged
  height and DOM). Deck grows by ~26px via one CSS var change. Zero new DOM outside
  day blocks.

## Changes (do exactly these)
1. `src/wind.js`: add the two unit params to buildUrl + buildDualUrl; parse
   `temperature_2m` → `tempF`, `precipitation` → `precipIn` on each entry (null-safe).
2. `src/sun-times.mjs`: copy from v2 repo verbatim.
3. `src/render.js`:
   a. Import sun-times.mjs (CJS-safe dynamic import like v2 does — src/ is CJS here).
   b. Per day block: sunrise + sunset 1px tick + 8px sun glyph at the correct x using
      the day's real frame spacing (NOT a fixed per-frame assumption). Muted amber,
      title="Sunrise 7:17a" (America/Chicago).
   c. Temp lane: 3-hourly temp labels, heat-colored via cribbed `tempLabelColor`,
      skip nulls, ~10px font, never overlapping the rain line below.
   d. Rain lane: per-day SVG polyline + translucent under-fill, height scaled to the
      day's max (2.5px floor for measurable precip, cap 0.25in), droplet-labeled
      peaks >=0.05in only. Flat hairline when dry.
4. `index.html`: CSS for .day-temp, .day-rain (+ svg), sun tick/glyph; deck height
   62px → 88px via its existing var/constant.
5. `sw.js`: bump cache, add sun-times.mjs to SHELL.
6. `tests/sun-times.test.mjs`: copied verbatim from v2. `tests/weather.test.js`: NEW —
   assert wind.js URL carries both unit params; parse fixture has tempF/precipIn with
   null passthrough. Follow existing suites' style (`node --test tests/`).

## Done-when
- `node --test tests/` — all suites green (existing 5 + 2 new).
- `python3 tools/qa/pwa_check.py` — 11/11 ok.
- `python3 tools/qa/scrub_bench.py` — PASS, p50 within 1ms of v1's 16.65-16.70ms bar.
- `git diff` shows ZERO changes to wave-math.js, tables.js, or any Hs/impact computation.
- Every day block shows: temps on top, rain line, wind ribbon unchanged beneath.
