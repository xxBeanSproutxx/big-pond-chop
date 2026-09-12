# STAGE 5J — RECEIPTS (polish & fixes: calm lake, 24h tape labels, calm tier, legend card + wind strip)

> **SUPERSEDED — Reid rejected this visual direction (2026-09-12).** The floating legend card, the
> bottom wind text strip and the 6-hour repeating day header were all reversed in **Stage 5K**
> (`docs/STAGE-5K-RECEIPTS.md`); the calm-water colour was also reworked from opaque navy to a
> translucent tint. Kept as history: the land/calm separation, the tick edge work, the calm tier
> rule, the `.leaflet-bottom` lift, the header delimiter and the `[18]` gate all survive in 5K.
> The 5J branch was never merged.

Branch `stage5j` (off `main` @ 383126e). **Not merged/deployed** — see "Status" at the bottom.

Spec: `docs/BUILD-SPEC-STAGE5J.md`. Implementation: OpenCode worker; recon, gates and visual
verification re-run by the orchestrator (worker summaries are self-reports, not contracts).

## 1. Calm lake no longer renders as dead gray

**Root cause (measured):** `ui.colorForHs()` returned `[0,0,0,0]` for `hs <= 0`, and
`render.paintRaster()` wrote that alpha straight into the PNG — so at 0.0 ft the entire lake was
transparent and the *desaturated basemap* showed through (the "flat dead gray"). Land pixels
produce the same 0, which is why land and calm water could not previously be told apart at paint
time — but the per-display-pixel land fraction is already computed for smoothing.

- `src/ui.js`: `HS_STOPS[0]` `#1e40af` → **`#0f2744`** (deep glassy navy); new exported
  `CALM_RGBA = [15, 39, 68, 255]`, pinned by test to equal `HS_STOPS[0]`'s rgb (one source of
  truth: the legend's 0 ft colour *is* the map's calm colour).
- `src/render.js`: `paintRaster(ctx, raster, W, H, landFrac)` — `raster[k] > 0` → ramp;
  `else landFrac[k] < 0.5 ? CALM_RGBA : [0,0,0,0]` (land stays exactly transparent).
  `encodeOffscreen()` forwards `landFrac`; both paint paths (async blob + sync fallback) pass it.
- **Measured, forced-calm run** (Open-Meteo response rewritten to 2 mph in flight so every frame is
  calm): lake median pixel `rgb(68, 87, 107)`, 100 % of sampled lake pixels blue-dominant;
  previously fully transparent (gray basemap). Chip reads `Calm · Flat`, deck strip reads
  `Wind: calm`. Screenshot: `tmp/5j-shots/5j-calm-24h.png` (delivered in chat).
- **Note for review:** the navy is composited at the layer's `OVERLAY_OPACITY = 0.72`, so ~28 % of
  the desaturated basemap still bleeds through (hence 68,87,107 rather than a deeper navy). Knob if
  a richer glass is wanted: raise `OVERLAY_OPACITY` (0.85 → ≈48,68,90) — deliberately **not**
  changed here because it re-saturates every hot frame too.
- Side benefit: the ramp is now continuous — 0.01 ft interpolates *from* `#0f2744` instead of
  jumping from transparent to saturated blue.
- Land-bleed gate `[10.1]` still passes: `land_alpha=[0,0,0,0] mid_lake_alpha=[255,255]`.

## 2. 24h tape: day label, sub-ticks, midnight boundary

**Root cause (measured, 390×844):** the 24h tape is **one** day block — 96 frames 00:00→23:45,
550 px wide in a 374 px viewing window (density `max(550, windowW)/96` = 5.7292 px/frame). The day
header was a *single* label centred at 50 % of the block (tape middle), so it left the window as
soon as the reticle moved off mid-day → the whole evening half had no day context. Sub-ticks ran
h = 0…21, so the last tick was 21:00 and the final 3 h + the day-boundary line were blank.

- Wide blocks (`w > 275`) now repeat the day header once per **6-hour cell** (`(h+3)/24*w`), so
  every point of the tape is within ~69 px of a visible day label. 7d blocks (190 px) keep the
  single centred header — unchanged.
- Sub-ticks stay 3-hourly; the h=0 tick is now **left-anchored** (`left:3px`, no translate) and both
  it and the boundary tick carry `.edge` (brighter). The **24h final block** gets a right-anchored
  `12` marking 24:00/midnight over the day-boundary line.
- Measured: day headers fully inside the window = **1 / 2 / 2 / 2 / 1** at idx 0 / 24 / 48 / 72 / 95
  (was: 0 after mid-day); sub-ticks per 24h block = **9** (`12,03,06,09,12,03,06,09,12`); **0**
  clipped labels at every sampled position; 7d unchanged (8 ticks per block, min `12`-gap 85.6 px).
- **Deliberate scoping:** the right-edge boundary tick is scoped to the 24h horizon, not "last block
  of any horizon" — in 7d it would double the label at the tape end and, more importantly, break the
  un-authorised `[16]` and `live_smoke` "8 ticks per block" assertions. Open item if wanted (see
  Status).

## 3. Calm-water condition badge

`comfortTier()` gained `CALM_TIER_MPH = 4` / `CALM_HS_FT = 0.5`: a **green** sea under 0.5 ft or
under 4 mph reads **`Calm · Flat`**. Red/amber/yellow precedence is untouched — a rough sea can
never be relabelled calm (unit-pinned, incl. `5 ft @ 2 mph → Dangerous · Stay Home`).
`showFrame` passes `windMph: e.speedMph`. Verified live in the forced-calm run: chip `Calm · Flat`.

## 4. Wave colour bar into a map card + live wind strip in the deck

- The deck's second row is no longer the static ramp: `.deck-ramp` (`#ramp-bar`, `#ramp-ticks`) is
  gone, and `#legend-card` (bar + six tick labels, `pointer-events:none`, no interaction) now docks
  **inside `#map`** bottom-right. `src/render.js` paints `#legend-card-bar` from `ui.HS_STOPS` (the
  dead `#legend-bar` lookup is repointed — it had had no element since 5B).
- The deck footer is now `#wind-strip`: `Wind: {speed} mph · Gusts {gust} mph · From {dir} {deg}°`,
  written **inside `updateScrubUi()`** — the single UI path the reticle already uses every animation
  frame during a drag *and* from `showFrame` — so it is synchronized with the active centre needle by
  construction (text write skipped when unchanged).
- Measured during a real 5-step drag (idx 24 → 73): **5 distinct pill times ↔ 5 distinct strip
  values**, e.g. `8:30 AM → Wind: 25 mph · Gusts 32 mph · From NW 304°`, `6:15 PM → Wind: 19 mph ·
  Gusts 20 mph · From NW 298°`; after release the strip matches the settled frame
  (`dataset.windMph = 18.8` → `19 mph`). Deck height unchanged at **68 px**, strip flush to the
  deck bottom (delta 0.0 px).

## 5. Layout cleanups

- `.leaflet-bottom { bottom: calc(var(--deck-h) + 6px); }` → computed **74 px**. Measured rects:
  amber pill `x 161–229, y 756–776`; attribution now `y 685–702` → **overlap = false** (was:
  attribution box `x 155.9–390` in the same y band as the pill).
- Header delimiter: an explicit `·` separator span between `#wind-info` and `#frame-info`, so calm
  reads **`Wind: calm · H/L 0.000`** and windy reads `Wind: 27 mph · Gusts 33 mph · H/L 0.047`.

## Gate receipts

- Node suites: `parity/wind/render/ui` → **4 × exit 0** (`ALL TESTS PASSED`), re-run by the
  orchestrator on the final tree. New checks: calm-water paint (water `CALM_RGBA` @ alpha 255, land
  alpha 0), `CALM_RGBA` ↔ `HS_STOPS[0]` agreement, ramp gradient low stop, `windStrip` (7 cases),
  calm-tier precedence (6 cases).
- `tools/qa/stage5_check.py` (orchestrator re-run on the final tree):
  **`SUMMARY: 23 ok, 1 FAIL`** — the single FAIL is `[14] live seam` (pre-existing, see below).
  All other groups ok, including `[10.1] land bleed (land_alpha=[0,0,0,0] mid_lake_alpha=[255,255])`,
  `[15] deck geometry (deckH=68.0, wind-strip-bottom=deck-bottom)`,
  `[16] tape architecture (24h tape 550 / window 374 / runway 176; 7d 7 blocks, subs [8×7])`,
  `[17] scrub decoupling (moves=31, swaps=11<=12, long-max=0<=50)` and
  `[9] playback perf (frameMs avg 42.8 / max 48.8)`.
  - New gate `[18] timeline labels (5J)`: PASS — heads per idx, left-edge `12`, last-block boundary
    `12`, 9 ticks, 3-hourly labels complete, all labels inside their blocks, 7d counts + no
    duplicate `12` at a day join.
  - `[7a] ramp location` rewritten (ramp now **in-map**, not in-deck; new low stop `rgb(15,39,68)`),
    `[15] deck geometry` and `[7b] touch ergonomics` now measure `#wind-strip`; `[7b]` was
    **tightened**: the second-row drag must land on the wind strip itself. No gate was weakened.
  - `[14] live seam` is the only non-ok line — **pre-existing**, unrelated to 5J
    (`SEAM 2026-09-14 frame=288 dSpeed=1.80 dDir=7.00`, gate `dDir <= 6`; it read `dDir 10.00` on
    5I). Still the open "gate vs ramp" decision.
- `live_smoke.py` (local URL): **10 ok / 0 FAIL**.
- Independent orchestrator verifier (`/tmp/bpc-5j/verify5j.py`, phone viewport 390×844 @2×, real
  browser, calm data injected at the network layer): **17 ok / 0 FAIL** on the final tree.
- Physics untouched: `git diff main -- src/wind.js src/wave-math.js src/tables.js public/` = **0 lines**.

## Visual receipts (phone viewport, 390×844 @2× — full-size PNGs in `tmp/5j-shots/`)

| shot | what it shows |
| ---- | ------------- |
| `5j-calm-24h.png` | forced-calm lake: solid glassy navy water (no gray), chip `Calm · Flat`, strip `Wind: calm` |
| `5j-24h-start.png` | 24h @ 00:00 — pill `12 AM`, day label `Saturday 12` + `12 03 06…` ticks, legend card bottom-right, attribution lifted clear |
| `5j-24h-evening.png` | 24h @ 23:45 — `06 09` then the new boundary `12`, day label still on screen, strip `Wind: 15 mph · Gusts 16 mph · From N 345°` |
| `5j-7d.png` | 7d parity — 7 day blocks, labels intact, strip live, no duplicate boundary label |

## Files changed (`git diff --stat main`)

```
 docs/BUILD-SPEC-STAGE5J.md | 161 +++++++++++++
 index.html                 |  31 +++++---
 src/render.js              |  80 ++++++++++++------
 src/ui.js                  |  44 ++++++++---
 tests/render.test.js       |  32 ++++++--
 tests/ui.test.js           |  33 ++++++++-
 tools/qa/live_smoke.py     |   2 +-
 tools/qa/stage5_check.py   | 154 ++++++++++++++++++++++-----
```

Orchestrator post-gate tweak: `#wind-strip` got `aria-live="off"` (a `role="status"` region that
rewrites every playback frame would queue an announcement per frame); applied after the worker's
gates, so **both** the harness and the independent verifier were re-run on that final tree.

## Status

- Branch `stage5j`, **not merged, not tagged, not pushed** — the deployed site is still 5I.
- Open item carried forward: the 7d tape's final block has no right-edge midnight tick (see §2);
  adding it needs the `[16]` `all(c == 8)` and `live_smoke` per-block assertions relaxed to
  "8, or 9 on the last block".
- Open item carried forward: `[14] live seam` (pre-existing), `[17]` long-task headroom,
  `tmp/5j-shots/` is gitignored (shots are chat receipts, not repo artifacts).
