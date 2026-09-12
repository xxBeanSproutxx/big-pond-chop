# BUILD SPEC — Stage 5M: three-tier scrolling tape (day / hours / wind), strip removal, opacity balance

Repo: /home/reid/projects/big-pond-chop (branch `stage5m`, off `stage5l` @ a65347c)

Reid's brief (2026-09-12) — the 5L wind strip was a misunderstanding:

> We do not want a single dynamic text string at the bottom displaying the current wind speed. We
> want a full wind speed row integrated directly into the scrolling timeline tape so all hours
> display their forecasted wind speed at a glance.

Deliver exactly this:

## 1. Three-tier scrolling tape inside `#track-tape`

Each day block gets three aligned rows — **all of them children of the day block**, so they translate
with the tape under the stationary reticle:

| row | element | content |
| --- | ------- | ------- |
| top | `.day-head` | day header (`Saturday 12`) — unchanged, still the single sticky header on the wide 24h block |
| middle | `.day-sub` | hour ticks `12 03 06 09 12 03 06 09 12` — unchanged anchors (h=0 left-anchored, others centred, last-block boundary `12` right-anchored) |
| bottom | `.day-wind` **(new)** | wind speed in mph, **aligned directly under its hour tick** |

- **Layout**: remove the deck's second row (see §2) and let the tape row use the full deck height:
  `#deck` stays **68 px** (`--deck-h` unchanged → map real estate unchanged), `#track`/`#timeline`
  become **68 px** tall. Rows: `.day-head` top **6 px** (11 px bold, unchanged), `.day-sub` top
  **28 px** (10 px, unchanged font/colour), `.day-wind` top **48 px** — 10 px,
  `font-weight: 600`, `color: #e8f0f7`, `font-variant-numeric: tabular-nums`, `white-space: nowrap`.
- **Data**: add a pure, exported helper to `src/render.js`:
  ```js
  // h = 0,3,…,21 -> Math.round(speedMph) of the frame in [start, end) whose local time is hh:00.
  // Missing frame or non-finite speed is skipped (no label). Returns [{ h, mph }].
  function tickWinds(entries, start, end)
  ```
  Build the labels from it in `renderTimeline()`; values are plain integers (no padding, no unit
  suffix). **No wind value on the boundary `12` tick** (there is no 24:00 frame inside the block) —
  the wind row therefore carries exactly the 8 three-hourly values per block, in both 24h and 7d.
- **Alignment is the acceptance criterion**: each `.day-wind` span must use the *same* anchor rule and
  the *same* left offset as its `.day-sub` sibling (h=0 → `left:3px`, `transform:none`;
  others → `left: clamp(6, w-6, (h/24)*w)` with `translateX(-50%)`), so the centres line up within
  **1.5 px** at every density (550 px/day in 24h, 190 px/day in 7d).
- The row must be populated in both horizons. Nothing here runs per animation frame —
  `renderTimeline()` only runs on mount/resize/horizon change, so the 5H scrub budget is untouched.

## 2. Remove the redundant bottom text row

- Delete `#wind-strip` (element, `.deck-wind` CSS, `role=status` markup) and the `ui.windStrip()`
  helper + its write in `updateScrubUi()` (the wave colour bar lives in the map card; the top header
  and compass badge already carry the active needle's exact metrics).
- `#deck` stays **68 px** so the map keeps its height; the freed row becomes tape space (§1).

## 3. Calm-water opacity balance

- `OVERLAY_OPACITY` **0.85 → 0.68**. Keep the saturated blue:
  `HS_STOPS[0] = #0369a1`, `CALM_RGBA = [3, 105, 161, 255]` (PNG opaque; the layer supplies the 0.68).
  Update the comment: composite ≈ `rgb(67, 138, 176)` over the desaturated basemap — still clearly
  blue, with bay/reef/island labels legible through it. Land stays exactly transparent.

## 4. Keep the wave legend card (bottom-left)

- `#legend-card` stays inside `#map`, `pointer-events:none`, six `ui.HS_STOPS` stops.
  Reid asked for `left:10px; bottom:78px` — **measured conflict**: at 78 px the card's top edge
  (78→111 px band) intersects the OSM attribution band (74–91 px from the map's bottom, x 156–390)
  in the x-range 156–176 (the card is 166 px wide from x=10). Implement
  **`left:10px; bottom:98px`** (clears the attribution by ~7 px) and leave a code comment recording
  the 78 → 98 measurement, so the deviation is auditable.
- `#card` (tap readout) moves to **`bottom:140px`** so it stacks above the legend (legend top =
  131 px) and the two never overlap.

## Files allowed to touch

`index.html`, `src/ui.js`, `src/render.js`, `tests/ui.test.js`, `tests/render.test.js`,
`tools/qa/stage5_check.py`, `tools/qa/live_smoke.py`. Nothing else — no physics, no `public/**`,
no new dependency, no `docs/**`.

## Gate contract updates (authorised, and the ONLY ones allowed)

- `[18] timeline labels`: keep the 5L assertions (one head, pinned, sticky-window, sticky-block,
  head-x shift, no-repeat, 9 ticks, boundary `12`, all labels inside) and **add**:
  per block `.day-wind` count == 8 in 24h **and** in 7d; every wind label matches `/^\d+$/`;
  for each three-hourly tick, `|wind.center − tick.center| <= 1.5 px`; the boundary tick has no wind
  sibling. Report the worst per-hour delta.
- `[15] deck geometry`: `deckH <= 72` still; assert `#wind-strip` is **absent**, the tape row
  (`#track`/`#timeline`) is 68 px, and the play button still sits inside the track.
- `[7b] touch ergonomics`: the second-row drag no longer exists — the "non-interactive deck press"
  probe must now hit the deck's **bottom band** (deck centre-x, ~6 px above the deck's bottom edge,
  i.e. the new wind row) and still be non-interactive with the scrub advance preserved.
- `tools/qa/live_smoke.py`: drop the `#wind-strip` check; assert the first day block carries 8
  numeric `.day-wind` labels instead.
- Node suites: pin `OVERLAY_OPACITY = 0.68`; delete the `windStrip` test block (helper gone); add
  `tickWinds` cases (rounding, skipped missing frames, 8 entries for a full day, order by hour);
  keep the `CALM_RGBA` / gradient-low-stop / `paintRaster` (alpha 255) pins; update the deck id list.

**Never weaken a gate to make it pass.** Report anything that legitimately fails verbatim.

## Done-when (command output is the proof)

1. `node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js` → all exit 0.
2. `git diff main -- src/wind.js src/wave-math.js src/tables.js public/` → 0 lines.
3. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py` → all groups ok except the tolerated pre-existing `[14] live seam` (report verbatim if it appears).
4. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/live_smoke.py --url http://127.0.0.1:8791/index.html` → all ok (server already on 8791 — do not kill it).
5. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/scrub_bench.py --url http://127.0.0.1:8791/index.html` → modal step latency still ~16 ms, verdict PASS; quote the numbers.
6. Evidence in your summary: (a) the `[18]` line verbatim plus the worst tick-vs-wind alignment
   delta in 24h and 7d; (b) the 24h wind list (8 ints) and a 7d block's wind list; (c) `deckH`,
   the absence of `#wind-strip`, and the tape row height; (d) the legend card + `#card` rects with
   the overlap verdict and their distances from the map's bottom; (e) `[17]` line verbatim.

## Procedure

- Ponytail ruleset. Work on the current branch (`stage5m`); commit in logical steps with `stage5m:`
  prefixes; do NOT merge, tag, or push — the orchestrator handles the preview push.
- Re-run the harness after the edits; keep the tree clean.
