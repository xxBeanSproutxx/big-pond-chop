# big-pond-chop — BUILD SPEC (stage 2: page + live wind + display)

Stage 1 (`docs/BUILD-SPEC.md`, commit `c237784`) is frozen: `public/tables.v1.bin`,
`public/meta.v1.json`, `src/tables.js`, `src/wave-math.js` and `tests/parity.test.js`
all pass as-is. Do not change stage-1 behaviour or the pinned golden files.

## Goal

One phone-first page that renders **today's wave field for Mille Lacs** from the stage-1
tables plus **live Open-Meteo wind**, with an hour scrubber, a colour-coded canvas overlay,
and the **Hs + Peak Roller** verdict for every hour frame.

## Files allowed to touch
- `index.html` (new)
- `src/wind.js` (new) — Open-Meteo ingest, t_eff persistence pass, gamma mapping
- `src/render.js` (new) — affine warp, canvas paint, Leaflet overlay, map readout
- `src/wave-math.js` (extend only: direction blending + t_eff duration input; stage-1 exports must keep working)
- `tests/wind.test.js` (new), `tests/render.test.js` (new)
- `tools/export_warp.py` (new) — writes `public/warp.v1.json`
- `public/warp.v1.json` (new, generated)
- `docs/` notes if needed

## Done when
1. `python3 tools/export_warp.py` writes `public/warp.v1.json` (affine coefficients, both directions, plus grid dims/corners) and prints its fit residual.
2. `node tests/wind.test.js` and `node tests/render.test.js` pass; `node tests/parity.test.js` still passes.
3. Served over HTTP, `index.html` loads headless at a 390x844 viewport with **no console errors**, shows the map with the overlay for the current hour, and exposes the current frame's numbers in the DOM (see §4).
4. `node tests/wind.test.js` prints: the 24 hourly entries (local time, wind speed/direction, bearing_grid, t_eff, Hs lake-max, roller at that cell) and a per-hour field benchmark (budget <= 6 ms/hour with blending enabled).

## 1. t_eff persistence rule (PINNED — implement exactly)

Forward pass over the hourly wind array, in time order. `t_eff` is in **hours**.

- If `|Δbearing| <= 30` deg versus hour T-1 **and** speed(T) >= 4 mph:
  `t_eff = Math.min(6.0, t_eff(T-1) + 1.0)`
- If `|Δbearing| > 30` deg (vs T-1): `t_eff = 0.5`
- If speed(T) < 4 mph: `t_eff = 0`
- Order of evaluation: the speed test wins over nothing else — the three cases are mutually
  exclusive as written; evaluate in the order listed and assert that in the tests.
- Seed: ingest `past_days=1` so hour 0 of the displayed day HAS real predecessors; run the
  pass over the whole returned series and display today. If no predecessor exists at all
  (history missing), the first hour is `0.5`.
- The `t_eff` used for a displayed hour is the value AFTER applying that hour's transition.
- Duration input to the model: `F_dur = U_A * (t_eff * 3600)` metres, `F_used = min(F_eff, F_dur)`.

Pinned test vectors (bearing degrees, speed mph -> expected t_eff, hours):
```
A: steady 12 mph from 315 for 8 h -> 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0
B: 5 h at 20 mph 315, then 00 deg (90 deg shift) at 20 mph -> 0.5,1.0,1.5,2.0,2.5, then 0.5
C: 12 mph 315, 12 mph 315, then 2 mph 315, then 10 mph 315 -> 0.5, 1.0, 0, 1.0
D: 12 mph 315 x 8 h (saturating) -> caps at 6.0, stays 6.0
E: exactly +30 deg shift, 12 mph -> counts as within tolerance (t_eff keeps climbing)
F: +31 deg shift, 12 mph -> reset to 0.5
```

## 2. Wind ingest + grid convergence (PINNED)

- Source: Open-Meteo hourly forecast — `wind_speed_10m`, `wind_direction_10m`, `wind_gusts_10m`,
  one lake-wide point (default 46.22, -93.657; allow override via a `?lat=&lon=` query param).
  Endpoint shape: `https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m&wind_speed_unit=mph&timezone=America%2FChicago&past_days=1&forecast_days=2`
- `fetch(..., {cache:'no-store'})` — live on open, tap to refresh. No key, no proxy.
- Gamma from `public/meta.v1.json` (`gamma_deg`, stored `-0.474`):
  `bearing_grid = ((dir_true - gamma) % 360 + 360) % 360` — pin a test (`dir_true = 0` -> `bearing_grid = 0.474`).
- **Direction blending (from the approved design — no snapping):** the runtime blends the
  two nearest bearings of the 16-table set: with `b = bearing_grid / 22.5`, `i0 = floor(b) % 16`,
  `w = b - floor(b)`, `F_eff = (1-w)*F[i0] + w*F[i1]`, and the same blend for path depth.
  ONE growth evaluation per cell. Continuity test: scanning bearing 0->360 in 0.5 deg steps on a
  fixture cell, the largest jump between consecutive `Hs` values must be <= 0.05 ft.

## 3. display contract (PINNED — per hour frame)

- Per cell: `Hs_capped_ft = min(Ks * Hs_ft, 0.6 * d_local_ft)` (stage-1 definition),
  `Hmax_ft = min(1.67 * (Ks * Hs_ft), 0.78 * d_local_ft)` — the roller uses the post-Ks,
  pre-0.6d value, exactly as `tests/fixtures/golden.json` defines `roller_ft`.
- Header per frame: **Hs** (lake max, ft) and the **Hmax roller at that same cell**, plus
  steepness H/L, the hour label, and the wind (speed, gust, direction). One frame, two numbers —
  never one number alone.
- Colour overlay = `Hs` (canvas -> Leaflet `imageOverlay`). Legend with ft scale, land transparent.
- Tap/click anywhere on the lake: local readout (Hs, Hmax, H/L, depth, distance-to-shore is NOT required).
- Hourly scrubber (`<input type=range>`), local-time labels, current hour selected on load,
  day backfill behind it. Precompute the day once (< 2 s), then scrub from memory.
- Offline / fetch failure: render nothing broken — keep the last field, show a visible
  "wind unavailable — refresh" note.

## 4. Warp / placement (PINNED)

- `tools/export_warp.py` fits and writes `public/warp.v1.json`:
  `{"dims":[cols,rows], "corners":{"nw":[lon,lat],"se":[lon,lat]}, "grid_to_lonlat":[a,b,c], "grid_to_lonlat_row":[a,b,c], "lonlat_to_grid":[a,b,c], "lonlat_to_grid_row":[a,b,c], "max_residual_m": N, "source":"pyproj EPSG:32615 <-> EPSG:4326 least-squares affine over the bathy grid"}`
  with the measured residual printed in the receipt (affine fit over the 292x285 bathy grid; the
  orchestrator measured ~34 m worst case — reproduce that order of magnitude).
- Runtime: compute the field on the stage-1 UTM grid (83,220 cells), then gather it into the
  display raster with the `lonlat_to_grid` affine (bilinear sample of the UTM grid at the
  computed row/col), paint that raster to a canvas, and place the canvas with Leaflet
  `imageOverlay` using the raster's lat/lng corner bounds. No client-side projection math beyond
  the affine.
- DOM contract for the headless check (needed for external verification):
  `<body>` carries `data-hour`, `data-hs-ft`, `data-hmax-ft`, `data-wind-mph`,
  `data-bearing-grid`, `data-teff-h` for the currently displayed frame, updated on every scrub.

## Out of scope

Hosting/Pages, on-device perf, sharing to the group, per-cell wind interpolation, animation/radar
loop, gust physics (gusts are displayed only), boat ramps, webcams, depth contour layers, accounts.

## Receipts to print when done

(a) `python3 tools/export_warp.py` output (coefficients + residual).
(b) `node tests/wind.test.js` — the 24-hour table + t_eff vectors + benchmark ms/hour.
(c) `node tests/render.test.js` — affine round-trip error, blend continuity, roller definition.
(d) Headless load proof: the DOM data-attributes for the current hour (and after scrubbing to two
    other hours), plus a screenshot file path.
