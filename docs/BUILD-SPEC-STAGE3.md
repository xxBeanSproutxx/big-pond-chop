# big-pond-chop — BUILD SPEC (stage 3: UI/UX refinements)

Stages 1 and 2 are frozen. `tests/parity.test.js`, `tests/wind.test.js`, `tests/render.test.js`
must keep passing; do not change the physics, the bundle format, the t_eff rule, or the gamma mapping.

## Goal

Four UI/UX refinements to `index.html` + `src/render.js` (+ small supporting modules), ahead of
publishing: honest headline stats, a legible basemap/palette, a play/pause radar loop, and a
polished tap readout.

## Files allowed to touch
- `index.html`
- `src/render.js`, `src/ui.js` (new: pure formatting + palette + spot-naming helpers)
- `tests/ui.test.js` (new), `tests/render.test.js` (extend)
- `src/wind.js` only if the tick/loop needs a hook (no rule changes)
- `docs/` notes

`public/spots.v1.json` is PROVIDED (OSM feature list, 21 named bays/islands). Consume it; do not
edit it. `public/meta.v1.json`, `public/warp.v1.json`, `public/tables.v1.bin` are read-only.

## 1. Headline stats — never imply the whole lake is blown out

Two-line verdict block, plain language, one decimal:

- Line 1: `Waves: <p10> - <max> ft` (lake-wide 10th percentile to lake-wide max, over water cells
  only) — this is the honest "how much of the lake is blown out" read.
- Line 2: `Peak roller <Hmax_at_peak> ft` + the peak's location label, e.g.
  `at Spirit Island area (NW basin)`. Location = the tap-readout naming function applied to the
  peak cell (nearest named feature within 4 km, else `<sector> basin` / `<sector> shore`).
- Keep the wind line (`<speed> mph gust <gust> · <bearing>°`) and `H/L` in the secondary row.
- Never render a bare single Hs number without the range and the word "peak"/"max" nearby.
- Pure function `formatHeadline(frame)` in `src/ui.js`, unit-tested (percentile, rounding, labels).

## 2. Basemap + palette (sunlight legibility)

- Tiles: **CARTO Positron** `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png`,
  attribution `&copy; OpenStreetMap contributors &copy; CARTO`. Max zoom 19, `detectRetina: true`.
  (The default OSM green/wetland tiles clash with the overlay — that is the bug being fixed.)
- Palette (Hs, ft) — smooth interpolation between these stops, overlay opacity ~0.72, land alpha 0:
  - `< 1`   deep blue    `#1E40AF`
  - `1 - 2` vibrant cyan `#06B6D4`
  - `2 - 3.5` amber      `#F59E0B`
  - `3.5 - 4.5` orange-red `#EA580C`
  - `>= 4.5` crimson      `#DC2626` → past `5.5` magenta `#BE185D`
- Legend: swatch strip with breakpoints `0 / 1 / 2 / 3.5 / 4.5 / 6+` and a "hs ft" caption, placed
  over the map, readable in sunlight (chip background, >= 4.5:1 text contrast).
- Pure function `colorForHs(hsFt)` in `src/ui.js`, unit-tested at the stop boundaries.

## 3. Play / Pause radar loop

- Button beside the hour scrubber. **SVG icons** (no emoji glyphs), visible text label
  `Play` / `Pause`, min touch target 44x44 px, `aria-pressed`, keyboard reachable.
- Behaviour: loops the 24 precomputed frames at ~3 fps (333 ms per frame), wrapping 23 -> 0.
  Precompute the whole day before the first play so playback never stutters; report the measured
  per-frame cost.
- Pauses on: user scrub, tap on the map, tab hidden (`visibilitychange`), button toggle.
- `prefers-reduced-motion: reduce` -> never autostart (it is manual anyway) and shorten the frame
  transition to a plain swap.
- The Play button must not trigger a network refresh; it replays the cached day.

## 4. Tap readout — persistent pin + callout card

- Tapping/clicking the lake drops a **persistent pin** (`circleMarker`, distinct colour) and opens a
  **card** that stays until dismissed (× button, 44x44) or another tap. The card follows the hour:
  scrubbing updates its numbers for the pinned point.
- Card contents, one per line, plain labels:
  - `Spot:` nearest named feature within 4 km, formatted `<distance> mi <bearing> of <Name>`
    (e.g. `1.2 mi NE of Spirit Island`); otherwise `Open water - <sector> basin` / `<sector> shore`.
  - `Coords:` lat, lon to 4 decimals.
  - `Depth:` local depth, ft (1 decimal).
  - `Hs:` local significant wave height, ft (1 decimal).
  - `Hmax:` local peak roller, ft (1 decimal).
  - `H/L:` steepness (3 decimals).
- Sectors: 8-way (N/NE/E/SE/S/SW/W/NW) relative to the lake centroid from `meta.v1.json` corners;
  "shore" = within 0.25 mi (400 m) of a land cell, else "basin".
- Tapping while playing pauses playback (rule 3) and keeps the pin.
- Pure function `nameSpot(lat, lon, features, sector)` + `describePin(...)` in `src/ui.js`,
  unit-tested against the provided feature list (e.g. a point near Spirit Island returns
  `... of Spirit Island`; a mid-basin point returns an `Open water - ...` form).

## Done when

1. `node tests/ui.test.js`, `node tests/render.test.js`, `node tests/wind.test.js`,
   `node tests/parity.test.js` all pass.
2. Headless load at 390x844 (chromium, `--virtual-time-budget`) with **no console errors**:
   - the verdict block contains a range, a peak roller and a location label;
   - the tile host in the network log is `basemaps.cartocdn.com`;
   - `Play` advances `data-hour` over >= 3 successive samples and wraps;
   - a synthesised tap on the map produces a pin element and a card with all six fields.
3. Screenshots saved to `/tmp/bpc-s3-*.png` (verdict at a windy hour, mid-play frame, tapped card).

## Out of scope

Publishing to Pages, sharing, per-cell wind, animations beyond the frame loop, spot gazetteers the
project does not own, emoji iconography, dark-mode basemap toggle (Positron only this stage).

## Receipts to print when done

(a) the four test suites' tails; (b) the DOM verdict text + palette stop values; (c) the play-loop
sample series of `data-hour`; (d) the tapped-card text; (e) the headless console-error list (must be
empty apart from favicon 404); (f) per-frame cost and full-day precompute time.
