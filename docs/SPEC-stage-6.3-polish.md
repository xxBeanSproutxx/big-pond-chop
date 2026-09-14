# SPEC — Stage 6.3 polish: water-mask cleansing, map containment, 60 fps scrub, header copy

**Status:** DRAFT FOR REVIEW — **no production file may change until this spec is approved.**
**Base revision:** `87a52cb` (main, `origin/main`, tag `stage-6.2-polish`; live at
https://xxbeansproutxx.github.io/big-pond-chop/ = 6.2, production smoke green).
**Author:** Hermes (architect) · **Reviewer/approver:** Reid (product lead).
**Recon artifacts:** all numbers below are measured, not estimated. Scripts:
`tmp/s63_mask_recon.py`, `tmp/s63_outline_check.py`, `tmp/s63_blob_diff.py`,
`tmp/s63_geo_perf_recon.py`, `tmp/s63_paint_audit.py`, `tmp/s63_attrib.py`
(throwaway recon, safe to delete; nothing in them writes to the repo).

---

## 0. Scope, sequencing, non-goals

Four independent items, shipped in this order (each is separately reversible):

| # | Item | Risk | Reversible by |
|---|------|------|---------------|
| 1 | Water-mask cleansing (offline pipeline → new `tables.v1.bin`) | medium (data) | `git checkout public/tables.v1.bin` + re-run exporter from the old DEM |
| 2 | Map containment (`maxBoundsViscosity`, `setMaxBounds`, `minZoom` floor) | low | revert `src/render.js` map-init block |
| 3 | 60 fps scrub glide (compositing layer + velocity-gated encodes) | low | revert CSS + the paint scheduler |
| 4 | Header gust copy trim (`24 mph Gust` → `24 Gust`) | trivial | revert markup + 3 gates |

**Non-goals:** no changes to the wave physics, the 96-frame/15-min grid, the header's 72 px
ceiling, the docked corner geometry from 6.2, the API contract, or the fetch/path sampling
grid. Item 1 is the only item that changes shipped bytes in `public/`.

**Hard sequencing note:** item 1 changes `public/tables.v1.bin`. Items 2–4 must be developed
on top of the *regenerated* blob, and the full harness must be run against that tree, so the
golden fixtures are regenerated exactly once (see §6.3).

---

## 1. Item 1 — Water-mask cleansing (remove disconnected satellite lakes)

### 1.1 Problem (measured)

`public/tables.v1.bin` currently carries **six** separate water bodies. Decoded from the
shipped blob (`tmp/s63_mask_recon.py`, `scipy.ndimage.label`, identical result for 4- and
8-connectivity — there are no sub-cell channels anywhere):

| comp | cells | area | centroid (lat, lon) | depth ft (min/med/max) | inside DOW outline |
|------|-------|------|--------------------|------------------------|--------------------|
| **#1** | **52,738** | **527.38 km²** | 46.2424, −93.6466 | 0.0 / 30.8 / **40.0** | **98.4 %** → Mille Lacs proper |
| #2 | 345 | 3.45 km² | 46.3351, −93.8053 | 0.0 / 6.8 / 42.0 | 0.0 % (0.93 km clear) |
| #3 | 322 | 3.22 km² | 46.2058, −93.8129 | 0.0 / 0.2 / 42.0 | 0.0 % (0.92 km clear) |
| #4 | 317 | 3.17 km² | 46.3560, −93.7723 | 0.0 / 1.8 / 42.0 | 0.0 % (1.93 km clear) |
| #5 | 169 | 1.69 km² | 46.1110, −93.7239 | 0.0 / 2.2 / 12.8 | 0.0 % (3.25 km clear) |
| #6 | 104 | 1.04 km² | 46.3666, −93.8067 | 0.0 / 3.8 / 5.8 | 0.0 % (4.62 km clear) |

Total water = 53,995 cells = 539.95 km²; satellites = **1,257 cells = 12.57 km² = 2.33 %**
of all water. The 4-connectivity/8-connectivity identity is the proof that no dropped body is
joined to Mille Lacs by a channel at 100 m resolution.

**Safety check that matters most** (`tmp/s63_outline_check.py`): against the authoritative
DOW-derived outline `~/projects/oruxmaps-data/bathy/millelacs_work/ml_outline_4326.geojson`
(540.3 km², bounds lat 46.110–46.368 / lon −93.825…−93.461), **zero cells of components
#2–#6 fall inside the outline**, and the nearest approach of each body to the outline is
0.92–4.62 km of land. Conclusion: "keep the largest component" cannot delete real Mille Lacs
water. (Those centroids sit in Hazelton / Roosevelt / Kathio townships; naming them "Round /
Shakopee / Holt" is plausible but **unverified** — cosmetic only, the filter is geometric. No
name lookup is required to ship.)

Why it matters visually today: all five bodies lie inside the display rectangle, so the wave
raster paints false colour on them. Satellites occupy ≈ **9,415 px of the 780×796 field
raster ≈ 2.3 % of painted water px** (2.74 px per bathy cell). They also pollute the headline
statistic: `p10Ft = ui.p10(f.capped)` (src/render.js:991) is a percentile over *all* water
cells in the raster, and the dropped cells are shallow (median depth 2.2 ft) — i.e. they sit
at the low end of the distribution and drag the "Waves: x–y ft" floor down.

### 1.2 Algorithm / math diff

In `tools/export_tables.py` → `build_bathy(bd, land)` (100 m display grid), after `land` is
derived from the 20×20 min-depth downsample and **before** `build_fetch` is called:

```python
from scipy import ndimage           # scipy 1.17.1 / numpy 2.4.3 verified in the venv

# 6.3: keep only the largest contiguous water body (Mille Lacs proper). The DEM mask
# carries satellite lakes; rays/paints must not see them.
struct4 = ndimage.generate_binary_structure(2, 1)          # 4-connectivity
lab, n_lab = ndimage.label(~land, structure=struct4)
sizes = np.bincount(lab.ravel()); sizes[0] = 0
keep = int(np.argmax(sizes))
if sizes[keep] < 50000:      # 6.2 ships 52,738 cells for Mille Lacs
    raise SystemExit("mask regression: largest water body is %d cells" % sizes[keep])
dropped = (~land) & (lab != keep)
log_mask_receipt(n_lab, sizes, dropped, keep)   # new: counts + centroids into the receipt
land = land | dropped
```

Nothing else in the pipeline changes: `build_fetch(bd, land)` receives the masked `land`, so
the 300 m sampling points that sat inside a dropped body immediately ray-die (the first cell
is land) → `fetch = LAND_U16`, `path = 0`, exactly as the writers already handle land.

**Connectivity choice:** 4-connectivity (`generate_binary_structure(2, 1)`). Measured: 4- and
8-connectivity produce the *same* six components on this DEM, so the choice is risk-free here;
4-connectivity is the conservative default (8-connectivity would merge diagonal touches if a
future DEM introduces a 1-px pinch point). The `>= 50000` assertion is the guard that turns a
future DEM change into a loud failure instead of silently deleting real water.

### 1.3 Byte-level impact (measured on the shipped blob)

Blob = 613,320 B = depth 166,440 (292×285 u16) + fetch 297,920 (16×98×95 u16) + path 148,960
(16×98×95 u8).

| section | what changes | count | bytes |
|---|---|---|---|
| depth | water → `LAND` (65535) | 1,257 cells | 2,514 |
| fetch | `→ LAND_U16` at the 144 affected sampling points (of their 2,304 direction entries, 2,242 were valid) | 2,242 u16 | 4,484 |
| path | `→ 0` | 1,786 u8 | 1,786 |
| **total content change** | | | **≈ 8,784 B (1.43 %)** |
| **file size** | **unchanged** | | **613,320 B (0 B delta)** |

Fetch-grid reach: 144 of 9,310 sampling points (1.55 %) sit in satellite water today.

**`meta.v1.json` must be regenerated in the same run** — one summary stat genuinely moves:

| meta range | before | after | note |
|---|---|---|---|
| `fetchEff_decam` | [2, 2335] | **[2, 2335] (unchanged)** | the dropped entries were never the extremes |
| `depth_ft` | [0, 42.0] | **[0, 40.0]** | three dropped bodies sat at the 42 ft clamp (comps #2/#3/#4); the kept lake's own deepest cell is 40.0 ft |
| `pathEff_ft` | [0, 34] | [0, 34] (unchanged) | 0 was already in range |

**Invariance proof for the kept lake:** every fetch/path entry whose sampling point lies in
component #1 is bit-identical after the change. A ray from a kept cell terminates at the first
land cell, and every dropped body is separated from #1 by land (§1.1), so no ray from a kept
cell can see a dropped cell. Therefore the three golden parity point queries in the exporter
(`deep_mud_basin`, `garrison_reef`, `cove_bay_se_reach` — all inside Mille Lacs) must return
**identical** depth/fetch/path values. Any movement there is a defect, not a data update.

### 1.4 Runtime consequences

* Wave field over Mille Lacs: **bit-identical** (same fetch/path/depth inputs).
* Raster: 5 satellite lakes stop being painted; ≈2.3 % of painted water px disappear.
* `p10Ft` / "Waves: x–y ft": population shrinks by 2.33 % of water cells, all at the shallow
  end ⇒ the value can only move **up** or stay flat. Exact delta is measured in the build
  against a pinned frame (§6.2 gate P4) — no regression if it moves up, a defect if it moves
  down.
* `maxHsFt` / peak: unchanged unless a satellite cell held the global max — it cannot, the
  satellites are ≤42 ft deep small bodies with ≤ few-km fetch; gate P4 asserts the peak
  location stays inside component #1.

### 1.5 Item-1 gates

* **P1** exporter assertion: 6 components in, 5 dropped, keep = 52,738 cells; receipt JSON
  written next to the blob (component count/sizes/centroids, dropped inventory).
* **P2** parity: `tests/parity.test.js` green; the three golden point queries **bit-identical**
  (depth + fetch + path).
* **P3** blob: size exactly 613,320 B; meta ranges as in §1.3 (`depth_ft` max = 40.0).
* **P4** runtime: for one pinned frame, `body.dataset.p10Ft` moves up or flat and the peak
  stays inside the kept component; the 5 satellite centroids sample as **land** through the
  app's own `lonlatToGrid`/`depthAt` path (a new harness probe, group [20]).
* **P5** visual: raster probe at the 5 centroids returns no wave colour (screenshot receipt).

---

## 2. Item 2 — Map containment (iOS-style rubber-band bounds)

### 2.1 Current state (measured)

```js
map = L.map('map', { zoomControl: true, zoomSnap: 0.1, zoomDelta: 0.5, touchZoom: true,
                     zoomAnimation: true, wheelPxPerZoomLevel: 90 });        // src/render.js:596
const fitLake = () => map.fitBounds(llBounds,
  { paddingTopLeft: [12, headerBand() + 12], paddingBottomRight: [12, 12], maxZoom: 12 });
```
No `minZoom`, no `maxBounds`, no `maxBoundsViscosity` ⇒ at the fit zoom a user can pan
indefinitely into empty space (the reported defect) and can zoom out without limit.

Display bounds (`displayBounds(warp)`): S 46.10703175, W −93.82864604, N 46.37098528,
E −93.45724836 → span 0.2640° lat × 0.3714° lon = **29.4 km N-S × 28.6 km E-W**.

### 2.2 Fit-zoom math (derived + verified)

Leaflet's `getBoundsZoom` = `zoom + log2(min(size.x/boundsPx.x, size.y/boundsPx.y))` with the
size taken **after** subtracting the fit padding, then `Math.floor(z/0.1)*0.1` (zoomSnap 0.1),
clamped by `maxZoom: 12`. Replicated in `tmp/s63_geo_perf_recon.py`; cross-checked live at
390×844 (Leaflet tile z = 11, which is `Math.round(zoom) + 1` because `detectRetina: true` on
a DSF-2 device ⇒ true zoom 10.4 ✓).

Padding = `paddingTopLeft [12, header+12]` + `paddingBottomRight [12, 12]` = (24, header+24)
with `header = 72` ⇒ (24, 96).

| viewport | map band | fit zoom (raw) | fit zoom (snapped) | visible N-S at fit |
|---|---|---|---|---|
| 360×800 | 360×738 | 10.313 | **10.30** | 79.7 km (lake = 29.4 km) |
| 390×844 | 390×782 | 10.437 | **10.40** | 79.5 km |
| 414×896 | 414×834 | 10.528 | **10.50** | 79.8 km |
| 768×1024 | 768×962 | 11.460 | **11.40** | 50.2 km |
| 1440×900 | 1440×838 | 11.417 | **11.40** | 43.0 km |

Consequence to plan around: **the fit is width-bound**, so in portrait the visible vertical
span (≈79 km) is ~2.7× the lake's N-S span. Some empty land above/below the lake at the fit
zoom is unavoidable on a phone; containment has to come from the zoom floor + pan box, not
from the fit itself.

### 2.3 What `pad(0.20)` actually does (measured, not assumed)

`lakeBounds.pad(0.20)` = +0.0528° lat / +0.0743° lon on **each** side = **+5.9 km N-S and
+5.7 km E-W per side** → padded span 0.36953° × 0.5200°. Probe
(`tmp/s63_bounds_probe.html` + runner) with the real fit options at 390×782, viscosity 0.75:

* `setMaxBounds(padded)` does **not** move the centre on its own (`centerMoved = 0.000000`).
* At the fit zoom (10.4) the visible span is 0.56291° lat × 0.40590° lon vs the padded box
  0.36953° × 0.5200° ⇒ **the view is TALLER than the box (by 21.5 km) and narrower than it**.
  Measured behaviour: the long axis **centres itself** — the first vertical drag collapses the
  centre onto the box centre — while the short axis clamps exactly at the padded edges
  (east pan stops at −93.38275 vs padded east −93.38297 ✓).
* At fit+1 and fit+2 (view 0.28130° / 0.14065° lat) **both** axes clamp exactly at the padded
  edges (verified: north edge 46.42396 vs padded north 46.42378; south edge 46.05459 vs padded
  south 46.05424).
* ⚠️ **The vertical centring eats the header clearance.** The fit's centre is deliberately
  shifted north by `((paddingBR − paddingTL)/2)` = 42 px ⇒ fitted centre 46.26939 vs lake/box
  centre 46.23901 = **+0.03038° = 3.38 km ≈ 29 px at fit zoom**. Once the box centres the long
  axis, that 29 px comes back out and the lake sits ~29 px higher than the fit intended: the
  effective top reserve drops from 96 px to **≈67 px — under the 72 px header band**, which
  breaks the 6B.2 "shoreline stays visible under the floating band" contract.

### 2.4 Proposed design

```js
const lakeBounds = L.latLngBounds(llBounds);
const fitLake = () => {
  map.setMinZoom(0);                        // measure the fit free of our own floor  (see trap)
  map.fitBounds(llBounds, fitOpts);
  const fitZoom = map.getZoom();            // snapped, post-maxZoom(12)
  const fitCenter = map.getCenter();        // carries the header offset
  const halfLat = (lakeBounds.getNorth() - lakeBounds.getSouth()) * (1 + 2 * 0.20) / 2;
  const halfLng = (lakeBounds.getEast() - lakeBounds.getWest()) * (1 + 2 * 0.20) / 2;
  map.setMaxBounds(L.latLngBounds(              // pan box re-centred on the FITTED centre
    [fitCenter.lat - halfLat, fitCenter.lng - halfLng],
    [fitCenter.lat + halfLat, fitCenter.lng + halfLng]));
  map.setMinZoom(fitZoom);                      // zoom floor = this viewport's fit
  if (map.getZoom() < fitZoom) map.setZoom(fitZoom);
};
```
plus `maxBoundsViscosity: 0.75` in the map options (Leaflet 1.9.4 supports it; default 0.0 =
hard edge, 1.0 = stiff wall — 0.75 is the rubber-band feel requested).

Why build the box from `fitCenter ± half(paddedSpan)` instead of plain `lakeBounds.pad(0.20)`:
it keeps the fit's 29 px header offset intact when the long axis centres (§2.3), at the cost of
an asymmetric margin — **9.26 km of pan slack north of the shore, 2.50 km south, 5.7 km
east/west**. That asymmetry is exactly where the slack is useful (the view already sits north of
the lake centre), and the shoreline + its roads stay reachable in every direction.

**Layout bounds after the change** (390×844, DSF 2):

| quantity | value |
|---|---|
| pan box (lat) | 46.08463 … 46.45416 (0.36953°) |
| pan box (lng) | −93.90295 … −93.38295 (0.5200°) |
| margins around the lake | N 9.26 km · S 2.50 km · E 5.70 km · W 5.70 km |
| `minZoom` at 360 / 390 / 414 / tablet | 10.3 / 10.4 / 10.5 / 11.4 |
| measurable cost of the floor | none — `getBoundsZoom` already computed this value |
| behaviour at fit zoom | long axis locked to the box centre, short axis pans ±5.7 km E-W |
| behaviour at fit+1 and deeper | both axes clamp exactly at the box edges |

**Trap to code around:** `getBoundsZoom` reads `this.getMinZoom()` as its clamp, so with a
floor already installed, a shrink (rotation, browser chrome appearing) can return a *higher*
zoom than the true fit and crop the lake. Hence `setMinZoom(0)` before measuring and
`setMinZoom(fitZoom)` after — the order in the code block above matters and must be commented.

**Trap 2 (verify, don't assume):** the fit must be re-run on resize/orientation change
(`fitLake()` already runs on `load`; add `resize` + `orientationchange` with a debounce) or the
floor goes stale in the same direction.

### 2.5 Item-2 gates

* **C1** after load at 360×800 and 390×844: `map.getMinZoom() === map.getZoom()` (the fit zoom
  is the floor) and the lake's N-S edges are inside the padded box.
* **C2** header clearance: the lake's north edge sits ≥ 96 px below the viewport top *before*
  and *after* a synthetic vertical drag (this is the gate that would have caught §2.3).
* **C3** drag past each edge at fit+1: the centre stops at the box edge (±0.5 px) and the view
  never shows more than 5 px beyond it; with viscosity 0.75 a mid-drag read shows overshoot
  that settles back within 250 ms of release (rubber-band receipt).
* **C4** zoom floor: `#h-*`/wheel/pinch zoom-out attempts leave `map.getZoom() >= fitZoom`
  (drive `map.zoomOut()` ×3 and assert), and the lake still spans ≥95 % of the map width.
* **C5** regression: group [19] corner/geometry gates + the 72 px header ceiling stay green at
  all four viewports (the pan box must not disturb the 6.2 corner dock).

---

## 3. Item 3 — Timeline scrubber 60 fps glide

### 3.1 Baseline (measured, 6.2 as shipped, 390×844 DSF 2)

Rest profile (finger down, no motion, 2.58 s): frames p50 **16.7**, p90 **16.8**, max **17.0**,
0 frames > 33 ms, 0 encode/swap events ⇒ the app *can* hold 60 fps; the hitching is drag work.

| profile | duration | velocity | frames | p50 | p90 | max | frames > 33 ms | long tasks | blob URLs / img `src` writes |
|---|---|---|---|---|---|---|---|---|---|
| slow drag (6 px steps) | 1.90 s | 0.127 px/ms | 84 | 16.6 | **46.1** | **84.6** | **22** | **5 (314 ms total, max 84 ms)** | 22 / 22 |
| flick (`move(steps=40)`) | 0.90 s | 0.267 px/ms | 48 | 16.7 | **41.4** | **45.0** | **7** | 0 (>50 ms) | 7 / 7 |
| hold still | 2.58 s | ≈0 | 156 | 16.7 | 16.8 | 17.0 | 0 | 0 | 0 / 0 |

Attribution (`tmp/s63_attrib.py`, `PerformanceObserver('longtask')` + `URL.createObjectURL` /
`HTMLImageElement.src` interception): **every stall lines up 1:1 with a raster encode + overlay
swap** (22 encodes → 22 stalls → 5 long tasks; 7 → 7). Each swap costs **40–85 ms of main
thread** (worker blob → object URL → `<img>` decode → composite). The tape and the pill are not
the cost — the rest profile is a clean 60 fps.

Pointer-path audit (instrumented `getBoundingClientRect` / `getComputedStyle`, 40-move drag):
**1 `getBoundingClientRect` (from `refreshRailRect()` in `pointerdown`) and 1
`getComputedStyle` for the whole drag** — the move handler is already DOM-read-free and
rAF-coalesced (`scrubRaf`), and `shouldPaintMap()` (src/render.js:90) is the only throttle
(`MAP_PAINT_MIN_MS = 72`). So there is no layout thrashing to fix; there is *heavy main-thread
work to move off the finger path*.

Tape compositing: computed transform during drag = `matrix(1, 0, 0, 1, −247.792, 0)` — a 2D
translate, no dedicated layer (`#track-tape` CSS is `position:absolute; transition: transform
.32s linear`, no `will-change`).

### 3.2 Proposed design

**(a) GPU layer.** Add to `#track-tape` in `index.html`:
```css
#track-tape { … ; will-change: transform; }
```
Deliberately **no** `transform: translate3d(0, 0, 0)` in the stylesheet: the JS writer sets
`translateX(px)` inline every frame, which overrides the style rule, so the 3D hint would be a
no-op at drag time. Forcing it would mean rewriting the writer to emit `translate3d(...)` — and
that changes the computed transform from `matrix(...)` to `matrix3d(...)`, which the harness's
transform parsers (group [19] scrub gates, Home-settle determinism gate) read. `will-change`
alone promotes the layer; keep the writer as-is, zero harness churn.

**(b) Velocity-gated encode/swap.** Extend the existing scheduler; no new timers, reuse the
`scrubRaf` coalescing:

```
on each move-rAF:
  v = 0.7 * v_prev + 0.3 * (|Δx| / Δt)                      // px/ms, EMA α = 0.3
  if v >= V_HI (0.25 px/ms ≈ 250 px/s):   paints suspended
  elif v <  V_LO (0.08 px/ms ≈ 80 px/s):  paints at MAP_PAINT_MIN_MS (72 ms)
  else:                                    paints at the drag interval (see (c) decision)
  on the first frame after a suspension with v < V_LO: force one paint (catch-up from finger down)
  safety valve: if suspended for > 1.2 s continuously, allow one paint (anti-freeze)
  pointerup: unchanged full-res settle (showFrame(dragIdx, paintGen) path)
```

**(c) The measured gap in the stated requirement.** A *slow* drag (0.127 px/ms — below any
sensible "high velocity" threshold, yet 22 encodes → 22 stalls) would not be covered by (b)
alone. Reaching 0 frames > 33 ms therefore needs one of:

* **D3.4-A** shrink the drag-time raster: encode at a reduced width while the finger is down
  (e.g. `min(viewportWidth, 512)` instead of the current 780) and restore full width on the
  settle. Encode cost scales ~with pixel count (≈2.3× cheaper at 512); no visual change at drag
  speed, full detail returns at rest.
* **D3.4-B** raise the drag-time throttle from 72 ms to ~120 ms (22 → ~16 encodes; a ~27 %
  reduction — insufficient on its own, measurable in the build).
* **D3.4-C** accept the slow-drag profile as-is and gate only the fast path.

**Recommendation: (a) + (b) + D3.4-A**, then measure. Rationale: (b) protects the tape/pill from
main-thread stalls regardless; (a) makes the tape keep gliding even through an 85 ms stall;
D3.4-A is what actually removes the stalls below the flick threshold. If D3.4-A lands green,
D3.4-B/C are unnecessary.

### 3.3 Expected profile / gates

Targets (390×844 DSF 2, same three profiles as §3.1, measured with `tmp/s63_attrib.py`):

| gate | target |
|---|---|
| G1 flick (v ≥ 0.25 px/ms) | frames > 33 ms = **0**; p90 ≤ **20 ms** |
| G2 slow drag (v ≈ 0.12) | frames > 33 ms ≤ **2**; p90 ≤ **25 ms** |
| G3 hold still | unchanged: p90 ≤ 17 ms, max ≤ 20 ms |
| G4 tape continuity | the tape transform advances on ≥ 95 % of frames during a flick (i.e. the layer glides through stalls) and its computed form stays `matrix(...)` (no matrix3d) |
| G5 existing bench | `tools/qa/scrub_bench.py`: swaps ≤ 12, latency median ≤ 25 ms (both currently green; must stay green), plus the reported p90 ≤ 30 ms |
| G6 settle correctness | group [19] continuous-scrub + Home-settle gates green; released frame == the throttled target index (`expectedIdx` check) |

---

## 4. Item 4 — Header gust micro-copy

### 4.1 Exact diff

`index.html:288` — remove one span from the gust badge:

```html
<!-- before -->
<span id="pill-gust" class="pill" aria-label="Gust"><span id="gust">24</span><span class="unit">mph</span><span id="gust-u">Gust</span></span>
<!-- after -->
<span id="pill-gust" class="pill" aria-label="Gust 24 mph"><span id="gust">24</span><span id="gust-u">Gust</span></span>
```
Renders `[17 mph] · [24 Gust]`. `#lake`/`#mph` are untouched, so the speed badge keeps the
WIND_HEAT tier tint (`#pill-lake { background: var(--tint…) }`) and white numerals/unit.

`src/render.js` (~line 1104, next to `gustEl.textContent = pills.gust`): keep the badge's
`aria-label` in sync so the unit survives for assistive tech —
`pillGustEl.setAttribute('aria-label', 'Gust ' + pills.gust + ' mph')`. (Today the static
`aria-label="Gust"` already hides the number from screen readers; this fixes that as a
side effect of the trim.)

CSS: `.unit` (10 px/500/#cbd5e1) stays — `#mph` uses it. `#gust-u` (10 px/500/#cbd5e1) stays.
No new CSS, no layout-shape change beyond ~20 px less ink.

### 4.2 Gates/tests that must be updated (closed list)

| file | line(s) | change |
|---|---|---|
| `tests/render.test.js` | 439–440 | required-id list: `gust-u` stays, no change needed for `mph` (lake's) |
| `tests/render.test.js` | 454–458 | row-order array `['pill-lake','mph','dot','pill-gust','gust','gust-u']` still valid — verify no `unit` child expectation exists; add a negative: `#pill-gust .unit` must be **absent** |
| `tools/qa/stage5_check.py` | 1659–1660 | `gustUnitEl` probe must **not** push a missing-id error when the unit is deliberately gone |
| `tools/qa/stage5_check.py` | 1747, 1913 | drop the `gust .unit` width ratio + the `gust-unit_w` clause in `[19.2]` (keep `mph_w ≥ 17`) |
| `tools/qa/live_smoke.py` | 125, 135, 139 | `fam`/`ids` lists drop `#gust-u`? no — keep `#gust-u`; instead assert the *absence* of `#pill-gust .unit` and that the served DOM shows `24 Gust` |
| `tools/qa/live_smoke.py` | ~147–150 | expected badge texts: gust = `'24 Gust'` |
| `docs/*` | specs/receipts that quote the old copy | update only where 6.3 receipts supersede |

### 4.3 Item-4 gates

* **H1** header ceiling stays 72.00 px and row ink ≤ available width at all four viewports.
* **H2** `[17 mph]` badge unchanged: tint + white unit + tabular numerals.
* **H3** rendered gust badge text is exactly `24 Gust` (live smoke + harness), `#pill-gust .unit`
  absent in the deployed bytes, `aria-label` carries the unit.

---

## 5. Architecture & data flow (cross-cutting)

```
build time (offline)                     runtime (browser)
────────────────────────────────────     ────────────────────────────────────────────────
ml_dem_utm.tif (5 m)                     src/tables.js  parseTables(tables.v1.bin)
   └─ load_dem()          ─┐                └─ depth[292×285] fetch[16][98][95] path[…]
      build_bathy()        │  [1] NEW mask filter (scipy.label, keep largest)
         └─ 100 m grid  ───┘                src/render.js
             ├─ build_fetch() (ray-cast, 300 m)     ├─ computeFrame() → capped Hs per cell
             └─ write tables.v1.bin + meta.v1.json  │     └─ ui.p10()/peak → headline     [1]
                                                    ├─ paintRaster() → blob → worker encode
                                                    │     └─ L.imageOverlay swap            [3]
                                                    ├─ L.map() init  ── [2] bounds/zoom floor
                                                    └─ deck pointer handlers → tape/pill    [3]
```

Item ownership: **[1]** offline only (`tools/export_tables.py` → `public/tables.v1.bin` +
`public/meta.v1.json`, both regenerated together); **[2]** map-init + fit only
(`src/render.js`); **[3]** CSS (one rule) + the paint scheduler in `src/render.js`; **[4]**
`index.html` markup + one `aria-label` write in `src/render.js` + the gates in §4.2.

## 6. Verification plan

### 6.1 Per-item (fast loop)
`node tests/{parity,wind,render,ui}.test.js` after every edit batch; item 1 adds an exporter
assertion (P1) and a pixel probe (P5).

### 6.2 Full gate matrix (before commit)
| suite | what it proves | pass bar |
|---|---|---|
| `node tests/*.test.js` | unit contracts incl. the [14] header block | 4/4 files green |
| `tools/qa/stage5_check.py` group [19] | 72 px ceiling, badges, corners, continuous scrub, settle | all gates green |
| **new group [20]** | item 1 runtime (satellite centroids = land, p10 move), item 2 containment (C1–C4), item 3 profiles (G1–G3) | all gates green |
| `tools/qa/stage5_check.py` (full) | the 6.2 baseline set | ≥ 23 ok; the two known FAILs (`[14] live seam` data-dependent, `[17]` intermittent long-task) tracked separately and **not** counted as 6.3 regressions |
| `tools/qa/scrub_bench.py` | drag latency + swaps | G5 |
| `tools/qa/live_smoke.py` (post-deploy) | deployed bytes carry the new chrome | 16 ok / 0 FAIL, extended for §4 |

### 6.3 Fixture regeneration (item 1, once)
`tools/golden_fixtures_gen.py` must be re-run **only** if any golden fixture embeds satellite
cells; the parity point queries must come back unchanged (they are the guard). Regeneration is
recorded in the receipts with a before/after diff of the fixture values that moved and why.

### 6.4 Receipts
`docs/STAGE-6.3-RECEIPTS.md`: recon numbers (§1–§4 tables), the per-item gates with raw output,
the four profiles' frame data before/after, the blob before/after hash + size, and the
regenerated-meta table. Screenshots: 360/390 header, satellite lakes before/after, containment
drag receipts, mid-drag pill.

## 7. Decision table (approval required)

| id | decision | recommendation | alternatives | impact if deferred |
|---|---|---|---|---|
| **D1.1** | Connectivity for the component filter | **4-connectivity** (`generate_binary_structure(2,1)`) — measured identical to 8 on this DEM | 8-connectivity (merges diagonal pinches); largest + min-area threshold | none — both give the same 5 drops today |
| **D1.2** | Filter at the 100 m bathy grid or the 5 m source DEM | **100 m grid** (that is what feeds `tables.v1.bin`; 83 k cells, instant) | 5 m DEM (33 M cells, re-derives the downsample) | none for the blob; the atlas project's own mask is separate (out of scope) |
| **D1.3** | Guard on the keep-rule | **assert keep ≥ 50,000 cells** + receipt log | no guard | a future DEM change could silently delete real water |
| **D1.4** | Accept `meta.depth_ft` max moving 42.0 → 40.0 | **accept + regenerate meta in the same run** | keep stale meta (lies about the data) | stale meta is a correctness bug |
| **D1.5** | Satellite naming in receipts | **centroid + area + township** (verified); names only if confirmed | web-verify Round/Shakopee/Holt before shipping | cosmetic only |
| **D2.1** | `minZoom` mode | **dynamic = this viewport's fit zoom**, recomputed in `fitLake()` (with the `setMinZoom(0)`-before-measure guard) | static 10.3 (smallest phone) or 10.4 | static lets tablets zoom 1.0 out past the fit (lake smaller than the view) |
| **D2.2** | Pan-box construction | **`fitCenter ± half(paddedSpan)`** — preserves the 29 px header offset | plain `lakeBounds.pad(0.20)` (vertical lock eats the offset ⇒ 67 px clearance, breaks 6B.2) | the 6B.2 shoreline-vs-header contract silently regresses |
| **D2.3** | Viscosity | **0.75** (as specified) | 0.5 (softer) / 1.0 (rigid) | feel only |
| **D2.4** | Accept the long-axis lock at the fit zoom | **accept** (iOS-like: vertical drag springs back; E-W pans ±5.7 km) | enlarge the vertical pad to ±15 km (lets users pan into empty counties — contradicts the goal) | if rejected, the containment goal is not met on portrait phones |
| **D3.1** | `will-change` lifetime on `#track-tape` | **permanent** (one 2310×62 layer ≈ 2.3 MB at DSF 2; it transforms every frame in playback too) | gesture-scoped (set on pointerdown, cleared after pointerup) | gesture-scoped risks a promotion hitch at drag start |
| **D3.2** | `translate3d` in CSS | **do not add** — the inline `translateX` overrides it; adding it means rewriting the writer + harness parsers | rewrite the writer to emit `translate3d` (matrix3d churn) | redundant no-op if added naively |
| **D3.3** | Velocity thresholds | **V_HI 0.25 px/ms, V_LO 0.08 px/ms**, EMA α = 0.3, −1.2 s anti-freeze valve | tighter (0.15/0.05); no valve | no valve risks a frozen map on a long slow drag |
| **D3.4** | How to reach the slow-drag target (§3.2c) | **A: shrink the drag-time raster width (780 → ≤512), restore on settle** | B: raise the throttle to ~120 ms (insufficient alone); C: gate the fast path only | C leaves 22 stalls / 1.9 s in the common case |
| **D3.5** | Drag-time raster width value | **512 device px** (≈2.3× cheaper encode than 780; on a 390 CSS px phone that is a 1.52× upscale *during the drag only*, full 780 restored at settle) | 640 (1.22× upscale, 1.48× cheaper) / 384 (soft) | too low softens the drag preview visibly |
| **D4.1** | Gust copy | **`[24 Gust]`** + dynamic `aria-label="Gust 24 mph"` | keep `24 mph Gust`; drop the word as well (`24`) | ambiguity for screen-reader users if no label fix |
| **D4.2** | Gate updates in §4.2 | **apply as listed, in one commit** | split CSS/markup/gates commits | a stale gate blocks CI on correct output |

**Approval request:** confirm D1.1–D1.5, D2.1–D2.4, D3.1–D3.5, D4.1–D4.2 (or mark the ones to
change). Defaults marked in bold are what the build will implement.

## 8. File manifest (closed list — nothing else may be touched)

| item | file | change |
|---|---|---|
| 1 | `tools/export_tables.py` | mask filter + receipt log + keep-assertion |
| 1 | `public/tables.v1.bin`, `public/meta.v1.json` | regenerated (size unchanged; meta `depth_ft` max 40.0) |
| 2 | `src/render.js` | map options (+viscosity), `fitLake()` rework, resize/orientation refit |
| 3 | `index.html` | `#track-tape { will-change: transform; }` |
| 3 | `src/render.js` | velocity EMA + paint gating; drag-time raster width constant |
| 4 | `index.html` | gust badge markup |
| 4 | `src/render.js` | gust `aria-label` write |
| tests | `tests/render.test.js`, `tools/qa/stage5_check.py`, `tools/qa/live_smoke.py` | §4.2 list + the new [20] group |
| docs | `docs/STAGE-6.3-RECEIPTS.md` (new) | receipts |

## 9. Risks, rollback, open questions

* **R1 (data):** a wrong mask removes real water. Mitigations: DOW-outline check (0 % inside),
  4-/8-connectivity agreement, the 50 k-cell assertion, golden parity invariance (§1.3).
  Rollback: `git checkout public/tables.v1.bin public/meta.v1.json`.
* **R2 (containment):** the vertical lock is a deliberate behaviour change that a user could
  read as "the map won't move". Mitigation: C3 receipt + the 12 px E-W slack at fit; if Reid
  dislikes it on-device, D2.4's alternative is a one-line pad change.
* **R3 (perf):** D3.4-A softens the mid-drag raster. Mitigation: restore full width at settle
  (existing path) and compare screenshots at drag vs rest.
* **R4:** the two pre-existing harness FAILs (`[14] live seam` — live-API data-dependent;
  `[17]` intermittent long-task, reproduced on the 6.1 baseline) must be re-confirmed on the
  6.3 tree so they are not silently attributed to this stage.
* **Open question O1:** should the same mask filter be applied to the OruxMaps atlas pipeline
  (`bathy/millelacs_work`) where the satellite lakes are a visual (not wave) artifact? Out of
  scope here; flagged for the atlas project.
* **Open question O2:** item 3's thresholds were calibrated against a headless Chromium at
  DSF 2. A real-device (Android/Brave) pass before tagging is recommended; the gate numbers in
  §3.3 are the CI bars, not on-device promises.
