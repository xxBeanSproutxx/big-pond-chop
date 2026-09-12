# BUILD SPEC — Stage 5J: polish & fixes (calm lake, 24h tape labels, calm tier, legend card + wind strip)

Repo: /home/reid/projects/big-pond-chop (branch `stage5j`, off `main` @ 383126e)

## Goal

Five items. All measured root causes are pinned below — do not re-diagnose, implement.

### 1. Calm lake renders as dead gray (calm water currently = transparent)

`src/ui.js` `colorForHs()` returns `[0,0,0,0]` for `hs <= 0`, and `src/render.js`
`paintRaster()` writes that alpha straight to the PNG — so a 0.0 ft lake is fully
transparent and the desaturated basemap (gray) shows through. Land and calm water are
currently indistinguishable at the paint step, but they are distinguishable: the frame
build already computes a per-display-pixel land fraction
(`landMaskRaster(warp, tables, W, H)` at render.js ~L800, available alongside `smooth`
at both paint call sites).

- `src/ui.js`: change the 0.0 ft stop colour `HS_STOPS[0]` from `0x1e,0x40,0xaf` to a deep
  glassy navy `0x0f,0x27,0x44` (#0f2744). Add exported `CALM_RGBA = [0x0f, 0x27, 0x44, 255]`
  and note in a comment that it must equal `HS_STOPS[0]`'s rgb (single source of truth —
  the legend's 0 ft colour and the map's calm colour are the same colour).
- `src/render.js`: `paintRaster(ctx, raster, W, H, landFrac)` — for each pixel:
  `raster[k] > 0` → `ui.colorForHs(raster[k])` (unchanged); `raster[k] <= 0` →
  `landFrac && landFrac[k] < 0.5 ? CALM_RGBA : [0, 0, 0, 0]`.
  `encodeOffscreen(raster, W, H, landFrac)` forwards it. Both call sites in the frame
  build pass the `landFrac` they already have. Land stays exactly transparent; calm water
  is opaque navy at the layer's existing `OVERLAY_OPACITY` (0.72 — leave it).
- Effect to expect: continuous ramp, no jump — 0.01 ft now interpolates from #0f2744 toward
  cyan, so the field no longer pops from transparent to saturated blue.

### 2. 24h tape: day label disappears, sub-ticks incomplete, midnight boundary unmarked

MEASURED (390x844, local): 24h = 96 frames 00:00→23:45 = ONE day block 550 px wide in a
374 px viewing window (density `max(550, windowW)`/96 = 5.7292 px/frame). Currently:
- the day header is a single label centred at 50 % of the block (= tape middle), so it
  scrolls off-screen and the evening half of the tape has no day context at all;
- 3-h sub-ticks run h = 0,3,…,21 → the last tick is 21:00, leaving the final 3 h
  (21:00→24:00) and the day boundary at the tape's right edge unmarked.

Fix in `renderTimeline()` (src/render.js), keeping the existing day-block structure:
- **Day header repeats across wide blocks.** When a block's width `w > 275` (24h mode:
  550 px; 7d blocks stay 190 px and keep the current single centred header), render the day
  label once per 6-hour cell, centred at `left = ((h + 3) / 24) * w` for h = 0, 6, 12, 18
  (i.e. 68.75 / 206.25 / 343.75 / 481.25 px at 550 px), each `translateX(-50%)`. In 24h every
  point of the tape is then within ~69 px of a visible day label (window 374 px → 2–3 labels
  on screen). Same class `day-head`; no new markup contract.
- **Sub-ticks complete + midnight boundary tick.** Keep h = 0,3,…,21. Position rules become
  clip-proof by construction: the h=0 tick is left-anchored (`left: 3px; transform: none`),
  the middle ticks stay centred/`translateX(-50%)` with the existing clamp, and **the LAST
  block only** gets a right-anchored `"12"` boundary tick (`right: 2px; left: auto;
  transform: none`) marking 24:00 / midnight over the day boundary line. Do NOT add that
  right-edge tick to non-last blocks (7d would render two `12`s ~5 px apart at each day join).
  Give the left-anchored and boundary ticks the extra class `edge` and style
  `.day-sub.edge { color: #e8f0f7; }` so midnight reads stronger than the 3-h ticks.
- Result: ticks per block = 9 (h=0 left-anchored "12", 03…09, "12", 03…09, plus boundary "12"
  on the last block), every label fully inside its block, and the evening ends on a visible
  `12` at the boundary instead of a blank 3-h gap.

### 3. Calm-water condition badge

`src/ui.js` `comfortTier()`: add `CALM_TIER_MPH = 4` and `CALM_HS_FT = 0.5`. When the computed
key is `green` AND (`maxHsFt < 0.5` OR (`windMph` finite and `< 4`)), return
`{ key: 'green', label: 'Calm · Flat' }`. The red/amber/yellow precedence is unchanged — never
label a rough sea "Calm · Flat". `src/render.js`: pass `windMph: e.speedMph` into the
`comfortTier` call (showFrame ~L924).

### 4. Legend card into the map corner; deck footer becomes a live wind strip

- **Wave colour bar moves out of the deck.** Delete the `.deck-ramp` row (`#ramp-bar`,
  `#ramp-ticks`) from `index.html` and add a compact non-interactive card inside `#map`:
  ```html
  <div id="legend-card" aria-hidden="true">
    <div id="legend-card-bar"></div>
    <div id="legend-card-ticks"><span>0</span><span>1</span><span>2</span><span>3.5</span><span>4.5</span><span>6+</span></div>
  </div>
  ```
  Dock it bottom-right: `position:absolute; right:10px; bottom:100px; z-index:500;
  pointer-events:none;` with the app's card chrome (bg `rgba(16,38,58,.85)`, border-radius 8px,
  padding 6px 8px), bar 11 px tall, tick row 8 px font `#9fc3dd`, bar width ~150 px.
  `bottom:100px` clears the lifted attribution (item 5) and the bottom-left tap card.
- `src/render.js`: the existing `#legend-bar` init block is dead code (no such element) —
  repoint it at `#legend-card-bar` and keep the same six-stop gradient formula
  (`v/6*100 %` positions) so the bar still matches `ui.HS_STOPS` (with the new calm stop).
- **Deck footer = wind status strip.** The deck's second row becomes
  ```html
  <div class="deck-row deck-wind" id="wind-strip" role="status">Wind: —</div>
  ```
  20 px tall (deck total stays 68 px), font 11 px `#cfe3f2`, tabular-nums, nowrap + ellipsis.
- `src/ui.js`: add pure `windStrip(speedMph, gustMph, bearingDeg)` →
  `Wind: 15 mph · Gusts 16 mph · From NW 315°` (reuse `CALM_MPH` / `windLine` / `compass`
  semantics: calm or non-finite speed → `Wind: calm`; finite bearing adds ` · From <sector> <deg>°`;
  no bearing → omit the From clause).
- `src/render.js`: write the strip **in `updateScrubUi(idx)`** — that is the single UI path the
  reticle already uses every animation frame during a drag AND from `showFrame` — so the strip
  is synchronized with the active centre needle at all times (skip the write when the string is
  unchanged). Keep the existing header `#wind-info` and the map `#wind-badge` (not in scope).

### 5. Layout cleanups

- `index.html` inline CSS (it is linked after leaflet.css, so an equal-specificity rule wins):
  `.leaflet-bottom { bottom: calc(var(--deck-h) + 6px); }` — the amber pill floats 20 px above
  the deck edge and the OSM attribution currently overlaps it (measured: pill x 161–229,
  attribution box x 155.9–390, both in the y band 756–776 at 390x844).
- Header delimiter: add an explicit separator `<span class="sep" aria-hidden="true">·</span>`
  between `#wind-info` and `#frame-info` inside `#secondary` (keep the 6 px column-gap) so calm
  states read `Wind: calm · H/L 0.000` and windy states read
  `Wind: 27 mph · Gusts 33 mph · H/L 0.047` — never a bare concatenation.

## Files allowed to touch

- `index.html`
- `src/ui.js`, `src/render.js`
- `tests/ui.test.js`, `tests/render.test.js`
- `tools/qa/stage5_check.py`, `tools/qa/live_smoke.py`

Nothing else. Explicitly out of scope: `src/wind.js`, `src/wave-math.js`, `src/tables.js`,
`public/**`, `docs/**` (receipts are written by the orchestrator), any new npm/CDN dependency,
any physics or data change.

## Test/gate contract updates (authorised, and the ONLY ones allowed)

- `tools/qa/stage5_check.py`:
  - `check_ramp_location` ([7a]): the six-stop ramp now lives INSIDE `#map`, not `#deck` —
    invert the in-deck/in-map assertions, keep the six-stop + gradient checks, and use the new
    low stop `rgb(15, 39, 68)`. Update the comment to say 5J moved it (it previously records the
    5B move).
  - `check_deck_geometry` ([15]): `.deck-ramp` no longer exists → measure `#wind-strip`
    (`.deck-wind`) instead; keep `deckH <= 72` and the flush-to-deck-bottom assertion.
  - `check_touch_ergonomics` ([7b]): the drag that starts in the second deck row must target
    `.deck-wind` / `#wind-strip`.
  - NEW group `[18] timeline labels (5J)`: in 24h, for each of idx 0 / 24 / 48 / 72 / 95, assert
    at least one `.day-head` whose rect lies inside `#timeline`'s rect; assert the block(s) carry
    a left-anchored `12` edge tick and the LAST block carries a right-anchored `12` boundary tick;
    assert every sub-tick rect is inside its own block rect (no clipping) and that the 3-hourly
    labels are all present; then widen to 7d, assert each day block still carries its ticks and
    that no two `12` ticks sit within 20 px of each other at a day join (no duplicate boundary
    label).
- `tools/qa/live_smoke.py`: `.deck-ramp` rect reference → `#wind-strip`; keep everything else.
- Node suites: update only the assertions that pin the changed contracts — the 0.0 ft stop
  colour, `CALM_RGBA` ↔ `HS_STOPS[0]` agreement, the calm tier label, `windStrip` output, the
  deck's frozen-id list (`ramp-bar`/`ramp-ticks` out, `legend-card-bar`/`legend-card-ticks`/
  `wind-strip` in), and the ramp-gradient test (new low colour).

**Never weaken a gate to make it pass.** If a gate legitimately fails, fix the product; if a gate
is wrong, report it verbatim in your summary instead of editing it beyond the list above.

## Done-when (all must be true, with the command output as proof)

1. `node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js` → all four exit 0.
2. `git diff main -- src/wind.js src/wave-math.js src/tables.js public/` → 0 lines (physics untouched).
3. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py` → every group prints `ok`, including the new `[18]`. The pre-existing `[14] live seam` finding (`dDir 10.00°`) and the marginal `[17]` long-task headroom are the only tolerated non-ok lines; report them verbatim if they appear.
4. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/live_smoke.py --url http://127.0.0.1:8791/index.html` → all ok (the local server is already running on port 8791; if it is not, start one, e.g. `python3 -m http.server 8791` from the repo root — do not kill port 8791's process).
5. Manual measurement evidence in your summary: (a) 24h at idx 0/48/95 — count of `.day-head` rects inside the window and the sub-tick list; (b) the calm-water PNG pixel for a 0-wind raster via the exported paint path or a unit assertion showing `CALM_RGBA` at alpha 255 for water and alpha 0 for land; (c) the deck height and `#wind-strip` text for a windy frame; (d) `.leaflet-bottom` offset and the pill/attribution rects (no overlap).

## Procedure

- Follow the ponytail ruleset (laziest correct implementation; no speculative abstraction).
- Work on the current branch (`stage5j`). Commit in logical steps with `stage5j:` prefixes; do NOT
  merge, tag, or push.
- Re-run the harness after each significant edit; keep the tree clean of stray files.
