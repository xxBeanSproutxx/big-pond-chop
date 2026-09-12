# BUILD SPEC — Stage 5O: wind heatmap ribbon, day-block/typography polish, calm floor #0891b2

Repo: /home/reid/projects/big-pond-chop (branch `stage5o`, off `stage5n` @ e278fa4)

Reid's brief (2026-09-12) — "full Windy-grade visual polish":

> 1. Color-Coded Wind Heatmap Ribbon: add a 6-8px colored strip flush along the bottom of
> `#track-tape` directly beneath the wind speed numbers. For each day block, generate a continuous
> linear-gradient derived from that day's hourly wind speeds: <10 mph Saturated Cyan (#0891b2),
> 10-14 Bright Green (#10b981), 15-19 Amber (#f59e0b), 20-24 Orange (#f97316), 25+ Crimson/Magenta
> (#ef4444 / #db2777). The strip must scroll with the tape — an instant heat map of wind spikes
> across the 7-day horizon.
> 2. Day Block & Typography Polish: subtle alternating dark backgrounds (#23272e vs #1b1d22) with a
> crisp 1px vertical divider at midnight; standardize the 3-hour columns — Row 1 Day Header
> (centered/sticky, 12px semi-bold), Row 2 Hour Ticks (11px, muted #94a3b8), Row 3 Wind Speed mph
> (12px bold #f8fafc), Row 4 Wind Heatmap Strip (6px height, rounded ends per day block).
> 3. Calm Water Floor (#0891b2): switch the 0.0 ft stop in render.js to #0891b2 — keeps the bright
> turquoise feel while preserving the gradient between 0.0 ft calm and 1.0 ft chop.

## 1. Wind heatmap ribbon

**New pure helpers in `src/ui.js`** (node-testable, exported):

```js
// Tier scale, ascending: [maxMph, r, g, b]
const WIND_HEAT = [
  [10, 0x08, 0x91, 0xb2], // < 10 mph  saturated cyan   (#0891b2)
  [15, 0x10, 0xb9, 0x81], // 10-14      bright green    (#10b981)
  [20, 0xf5, 0x9e, 0x0b], // 15-19      amber           (#f59e0b)
  [25, 0xf9, 0x73, 0x16], // 20-24      orange          (#f97316)
  [Infinity, 0xef, 0x44, 0x44], // 25+   crimson       (#ef4444)
];
function windHeatColor(mph)            // -> [r,g,b]; non-finite or <0 -> the <10 colour
function windHeatGradient(speeds)      // -> "linear-gradient(90deg, rgb(…) 0%, …, rgb(…) 100%)"
```

- `windHeatGradient` puts **one stop per hourly sample** at `i / (n-1) * 100 %` (n = `speeds.length`),
  so the ribbon interpolates continuously between hours. `n < 2` → a flat two-stop gradient of that
  single colour. Non-finite samples fall back to the <10 mph colour (never emit `NaN`).
- **Rendering** (`renderTimeline()`): each day block gets one child
  `<div class="day-heat" aria-hidden="true">` whose `backgroundImage` is
  `ui.windHeatGradient(hourly)` where `hourly` = that block's frames sampled at every `hh:00`
  (24 samples; the 15-min frames are 4 per hour). Build it in the same loop that emits the ticks —
  no per-frame work.
- **CSS**: `.day-heat { position: absolute; left: 3px; right: 3px; bottom: 3px; height: 6px;
  border-radius: 3px; }`. Inside the block, so it translates with the tape under the reticle.
- 25+ uses **crimson `#ef4444`** (Reid's first listed value); `#db2777` is a one-line alternate.

## 2. Day blocks & typography

- `.day-block` background **`#23272e`**, `.day-block.alt` **`#1b1d22`** (they must stay adjacent-
  alternating — the existing `[16]` alternation gate still applies).
- Divider: `.day-block + .day-block { border-left: 1px solid #4a5568; }` (crisp against both tones).
- Rows (all inside the 68 px tape; keep the total under 68 px):
  | row | element | spec |
  | --- | --- | --- |
  | 1 | `.day-head` | `top: 3px`, `font: 600 12px/1`, colour `#e8f0f7`, centered (sticky behaviour unchanged) |
  | 2 | `.day-sub` | `top: 19px`, `font: 11px/1`, colour **`#94a3b8`**; keep `.edge` brighter (`#e8f0f7`) |
  | 3 | `.day-wind` | `top: 33px`, `font: 700 12px/1`, colour **`#f8fafc`** |
  | 4 | `.day-heat` | `bottom: 3px`, height 6 px, radius 3 px |
- **Alignment**: both `.day-sub` and `.day-wind` switch from `width: 1.5em` to a **shared
  `width: 20px`** box so their centres stay identical despite the different font sizes (the h=0
  labels are left-anchored at 3 px, so a shared box width is what keeps the 0.00 px alignment).
- Bigger type must not re-introduce collisions: the `[18]` ink-gap gate (min ≥ 6 px, no overlap)
  must still pass at 330 px/day and 550 px/day — quote the new numbers.

## 3. Calm floor → `#0891b2`

- `HS_STOPS[0]` → **`[0.0, 0x08, 0x91, 0xb2]`**, `CALM_RGBA` → **`[0x08, 0x91, 0xb2, 255]`**.
  `OVERLAY_OPACITY` stays **0.68**. The 1.0 ft stop stays `#06b6d4`, so the **0–1 ft gradient is
  restored** (that was the reason for this change). Predicted composite
  `0.68 × rgb(8,145,178) + 0.32 × rgb(205,207,207)` ≈ **`rgb(71, 165, 187)`** — bright
  turquoise/teal. Replace the 5N "flat band" comment with a note recording this.
- Update every pinned expectation: `tests/ui.test.js` (`HS_STOPS[0]`, `CALM_RGBA` literal +
  equality, the ramp-gradient `0%` entry → `rgb(8, 145, 178)`), `tests/render.test.js`
  (`paintRaster` calm RGBA), `tools/qa/stage5_check.py` `[7a]` colour list.

## Gate contract updates (authorised; these are the ONLY ones)

- `[7a]`: first expected gradient colour `rgb(3/6 …)` → **`rgb(8, 145, 178)`**; the six expected
  colours are now all distinct again — drop the deliberate-duplicate comment.
- `[16]`: in addition to the existing `adjacent_ok`, assert the **exact tones** — the computed
  `backgroundColor` set must be `{rgb(35, 39, 46), rgb(27, 29, 34)}` exactly, alternating.
- `[18]`, new sub-block "5o rows" (all must gate the `[18]` verdict, not just print):
  - every 7d block has **exactly one** `.day-heat`; height **6 px** (±0.5); width == block width
    − 6 px (±1); `border-radius` ≥ 2 px; its `backgroundImage` contains **≥ 2 distinct** tier
    colours from the 5-tier scale;
  - computed fonts: `.day-head` 12 px / 600, `.day-sub` 11 px with colour `rgb(148, 163, 184)`,
    `.day-wind` 12 px / 700 with colour `rgb(248, 250, 252)`;
  - the ribbon **scrolls with the tape**: after one scrub step, the `.day-heat` rect's x delta must
    match the parent block's x delta within 1 px;
  - quote the ink-gap numbers (24h + 7d) with the new type sizes.
- Node suite additions (`tests/ui.test.js`): `windHeatColor` at the boundaries (9.9 → cyan, 10 →
  green, 14.9 → green, 15 → amber, 19.9 → amber, 20 → orange, 24.9 → orange, 25 → crimson, 40 →
  crimson, `NaN` → cyan) and `windHeatGradient` shape (stops == speeds length, ends at 0 %/100 %,
  contains the expected `rgb()` strings, single sample → flat gradient, empty → no throw).

**Never weaken a gate to make it pass.** If a gate legitimately fails, report it verbatim.

## Files allowed to touch

`index.html`, `src/ui.js`, `src/render.js`, `tests/ui.test.js`, `tests/render.test.js`,
`tools/qa/stage5_check.py`. (`tools/qa/live_smoke.py` only if a pinned value there breaks — and say
so explicitly in your summary.)

## Done-when (output is the proof)

1. `node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js` → all exit 0.
2. `git diff main -- src/wind.js src/wave-math.js src/tables.js public/` → **0 lines**.
3. `stage5_check.py` → all groups ok except the tolerated pre-existing `[14] live seam` (quote verbatim if it appears).
4. `live_smoke.py --url http://127.0.0.1:8791/index.html` → all ok (server already on 8791 — don't kill it).
5. `scrub_bench.py --url http://127.0.0.1:8791/index.html` → PASS; quote the three medians + long-task maxima.
6. Evidence in the summary: (a) `[16]` line verbatim incl. the block tones; (b) the new `[18]`
   "5o rows" line verbatim incl. the ink-gap numbers; (c) block 0's `backgroundImage` string (first
   120 chars); (d) `[7a]` line verbatim; (e) the 7d wind list + tick list; (f) `[17]` verbatim.

## Procedure

- Ponytail ruleset. Current branch (`stage5o`); commits prefixed `stage5o:`; **do NOT merge, tag, or
  push** — the orchestrator handles the preview push, screenshots and the brain update.
- Do not touch the 5H decoupled scrub path (`scrubUiTo` / `scheduleMapPaint` / `endScrub`).
- Re-run the harness after editing; leave the tree clean.
