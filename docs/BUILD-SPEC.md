# big-pond-chop — BUILD SPEC (stage 1: tables + math core)

## Goal
Implement the data export + wave math core for the Mille Lacs wave map, such that the JS runtime reproduces the Python export math within 0.01 ft on the three golden fixtures.

## Files allowed to touch
- `tools/export_tables.py` (new)
- `src/tables.js` (new)
- `src/wave-math.js` (new)
- `tests/parity.test.js` (new)
- `tests/fixtures/golden.json` (new — copy of `.golden-fixtures.json`)
- `docs/` notes only if needed

## Done when
1. `python3 tools/export_tables.py` runs against the DEM at
   `/home/reid/projects/oruxmaps-data/bathy/millelacs_work/ml_dem_utm.tif`
   and writes `public/tables.v1.bin` + `public/meta.v1.json` into the repo, printing a receipt
   (grid dims, value ranges, clamped-cell count, blob bbox, byte size, sha256).
2. `node tests/parity.test.js` passes: for each of the three fixtures, `Hs_ft`, `T_s`, `Ks`,
   `capped_ft` from the JS module match the exporter's Python values within **0.01 ft** (T within 0.01 s).
3. The exporter prints the three fixture values and they match `tests/fixtures/golden.json`
   within 0.01 ft (the golden file was computed with the methodology below — do not change it).

## Out of scope
`index.html`, the Leaflet UI, hosting, fetch/API integration, CI. Stage 2.

---

## 1. Grids, dims, and the ordering contract (do not transpose)

| grid | dims (rows × cols) | cell size | source |
|---|---|---|---|
| bathy | **292 × 285** | 100 m | DEM (5 m) depth-preserving downsample (min-depth per block, sentinel-aware) |
| fetch tables | **98 × 95**, per direction, 16 directions | 300 m | computed from the bathy grid |

- DEM facts: 5,686 × 5,840 float32, 5.0 m/px, UTM zone 15N, origin (E,N) = (436230, 5135360) at pixel (0,0)'s top-left corner; nodata is the float32 sentinel **3.4e38** (not NaN); depths are negative feet below datum.
- Raster row index increases **southward**; column index increases **eastward**.
- Coarse grid: `rows_c = 98`, `cols_c = 95`; coarse cell (r, c) centre coincides with bathy cell `(min(3r+1, 291), min(3c+1, 284))`. Sampling: `row_c = clamp((row-1)/3, 0, 97)`, `col_c = clamp((col-1)/3, 0, 94)`.
- **Bundle order is `[dir][row][col]`** with `dir = 0..15` at 22.5 deg steps starting at 0 deg (true north). Assert in code AND tests:
  `assert fetch.shape == (16, 98, 95)` in Python; in JS `assert(fetch.length === 16*98*95)` plus a round-trip test that a value written at (dir=3, row=70, col=12) reads back at the same index.
- Land/dry cells: depth value `65535`; fetch `65535` means "no water in this direction" (treat as 0 m of fetch); path depth `0`.

## 2. Bundle format (little-endian, no padding)

| offset | content | dtype | units |
|---|---|---|---|
| 0 | depth grid 292 rows × 285 cols, row-major | uint16 | ft × 4 (0.25 ft); 65535 = land |
| 166,440 | fetchEff 16 × 98 × 95 | uint16 | decametres (10 m); 65535 = invalid |
| 464,360 | pathEff 16 × 98 × 95 | uint8 | ft |
| total | 613,320 bytes | | |

- `meta.v1.json`: dims for both grids, cell sizes, UTM origin + EPSG:32615, the four WGS84 corner lat/lngs of the bathy grid, gamma = -0.474 deg, direction list, offsets, units, datum note, clamped-blob receipt, sha256 of the .bin.
- JS reader must use `DataView(..., true)` (explicit little-endian) — never rely on platform endianness.

## 3. Model (exact — SPM 1984 eqs (3-39)/(3-40), verified 2026-09-11)

```
U_A   = 0.71 * U^1.23                     # U = 10 m wind, m/s
F~    = g*F_m / U_A^2                     # g = 9.81
h~    = g*d_m / U_A^2
P1    = tanh(0.530 * h~^0.75)
P2    = tanh(0.833 * h~^0.375)
Hs_m  = 0.283 * (U_A^2/g) * P1 * tanh(0.00565 * sqrt(F~) / P1)
T_s   = 7.54 * (U_A/g) * P2 * tanh(0.0379 * (F~)^(1/3) / P2)
```
- **Duration**: `F_dur = U_A * t_eff`; use `F_used = min(F_eff, F_dur)` then evaluate the growth equation ONCE. (`t_eff` = persistence rule, stage 2 input; for the fixtures use 8 h.)
- **Shoaling**: `Ks = sqrt(cg(d_path)/cg(d_local))` from the dispersion relation `omega^2 = g*k*tanh(k*h)` (solve k by bisection), `cg = n*c`, `n = 0.5*(1 + 2kh/sinh(2kh))`; clamp Ks to [0.7, 1.6].
- **Caps (UNITS: feet)**: `Hs_final_ft = min(Ks * Hs_ft, 0.6 * d_local_ft)`; roller `= min(1.67 * Ks * Hs_ft, 0.78 * d_local_ft)`; steepness `H/L` with L from the dispersion relation at the local depth.
- Every symbol in code carries its unit suffix (`F_m`, `d_ft`, `Hs_ft`, `T_s`) — a mixed-unit expression is a bug (the reference run produced `min(Hs_m, 0.6*d_ft)` = wrong by 3x).

## 4. Fixture methodology (must match exactly — this is what golden.json encodes)

- Effective fetch: 5 bearings at wind_dir ± {45, 22.5, 0, 22.5, 45} deg, weights `cos(delta)` normalised. Ray-cast from the cell centre in **40 m steps**; a ray terminates at a land cell OR depth < 1 ft. Ray length = summed step length while water. Path depth = mean depth (ft) sampled along that ray.
- Effective = weighted mean of the 5 rays (fetch and path depth separately).
- Wind: 30 mph = 13.4112 m/s, direction 315 deg (NW).
- Ks from the dispersion relation with T from eq (3-40) at `d_path` vs `d_local`.

### Golden fixtures (tests/fixtures/golden.json — copy from `.golden-fixtures.json`)
| name | UTM E | UTM N | lat | lon | d_local | F_eff | d_path | Hs_ft | T_s | Ks | capped_ft | roller_ft | H/L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| deep_mud_basin | 445300 | 5125830 | 46.283841 | -93.710064 | 40.0 | 4.5906 mi | 30.0028 | 2.3563 | 2.9147 | 1.0012 | 2.3591 | 3.9397 | 0.0542 |
| garrison_reef (bar) | 450995 | 5107250 | 46.117066 | -93.634215 | 6.0017 | 8.3986 mi | 21.742 | 2.8953 | 3.3672 | 0.9586 | 2.7754 | 4.6349 | 0.0665 |
| cove_bay_se_reach | 463555 | 5110120 | 46.143682 | -93.471892 | 10.0002 | 4.7668 mi | 13.6934 | 2.1449 | 2.8109 | 0.9694 | 2.0793 | 3.4725 | 0.0552 |

Fixture points are given in **UTM** (E, N) — convert to bathy grid indices with `col = (E-436230)/100`, `row = (5135360-N)/100`, rounded.

## 5. Tests required (tests/parity.test.js + python asserts)
1. **Parity**: JS `Hs_ft`, `T_s`, `Ks`, `capped_ft` vs golden.json within 0.01 (fixtures above).
2. **Dim/ordering**: bundle length; `(dir,row,col)` round-trip; `[dir][row][col]` ≠ `[dir][col][row]` assertion (write a marker at an asymmetric index and read it back).
3. **Endianness**: a multibyte value written by the Python writer reads back identically in JS.
4. **Unit guards**: assert `Hs_final_ft == min(Ks*Hs_ft, 0.6*d_local_ft)` with all operands in feet.
5. **Model invariants**: SPM shallow reduced to deep power law within 1.2% for F~ in [100,1000] at deep water; duration identity `Hs(F_dur = U_A*t) == Hs(t)`; LUT path vs exact `Math.tanh` ≤ 1e-5 m.

## 6. Environment (verified on this box)
- python3 with numpy, PIL, pyproj 3.7.2 — **no GDAL, no rasterio**. Do not use gdalwarp.
- node v22 (has `node --test`), bun available.
- Run from the repo root. Do not modify anything outside the repo except reading the DEM path above.
