# BUILD SPEC — Stage 5L: saturated calm blue, legend card bottom-left, wind strip back, sticky day header

Repo: /home/reid/projects/big-pond-chop (branch `stage5l`, off `stage5k` @ c4057ae)

Reid's brief (2026-09-12, after reviewing the 5K screenshots):

> 1. Fix Calm Water Saturation (Eliminate Slate Gray) — the current calm colour looks like dead
>    concrete. Set the 0.0 ft floor to a saturated, glassy deep lake blue (#1d4ed8 or #0369a1) at
>    high effective opacity (~0.85). Calm water must register as clean, deep blue lake water.
> 2. Move Wave Ledger & Restore Dynamic Wind Strip — relocate the floating wave-height legend card
>    to the bottom-left corner (avoids the attribution text, keeps eastern bays clear). Restore the
>    dynamic Wind Status strip flush along the bottom of #deck under the timeline tape; it must
>    update synchronously with the active cursor during both scrub and playback.
> 3. Sticky Day Header on 24h tape — window-edge clamping for the single `.day-head` so
>    "Saturday 12" stays visible at the left edge while scrubbing past noon into the late evening.

**Note for the worker:** 5J built the legend card + wind strip and 5K deleted them. The 5J code is in
git history — `git show stage5j:index.html`, `git show stage5j:src/render.js`,
`git show stage5j:src/ui.js` — reuse it rather than re-inventing, then apply the 5L differences
(card position, saturated calm colour, sticky header). Keep everything else 5K shipped.

## Goal

### 1. Calm water: saturated deep lake blue at ~0.85 effective

- `src/ui.js`: `HS_STOPS[0]` → **`#0369a1`** (deep lake blue; `#1d4ed8` is the alternate Reid named —
  use `#0369a1`, it reads as water rather than electric blue) and `CALM_RGBA` →
  **`[3, 105, 161, 255]`**. Keep the single-source-of-truth invariant (CALM_RGBA rgb == HS_STOPS[0] rgb).
- `src/ui.js`: `OVERLAY_OPACITY` **0.72 → 0.85**. This is required to reach the ask: the Leaflet
  overlay multiplies the PNG's alpha, so a baked 0.45/1.0 can never exceed 0.72 on screen. At 255
  alpha with the layer at 0.85 the calm water lands at **0.85 effective** — composite over the
  desaturated basemap ≈ `rgb(33, 120, 168)`. Write that math into the comment block.
- `src/render.js`: keep the 5K land/calm separation exactly (`raster[k] > 0` → ramp; else
  `landFrac[k] < 0.5 ? CALM_RGBA : [0,0,0,0]`); land stays **exactly** transparent. The ramp above
  0 ft is already opaque, so the calm floor is now visually consistent with it.

### 2. Legend card → bottom-LEFT of the map; wind strip → back in the deck

- **Legend card (wave ledger)**: re-add `#legend-card` inside `#map` (bar `#legend-card-bar`,
  labels `#legend-card-ticks` with `0 1 2 3.5 4.5 6+`), non-interactive (`pointer-events:none`),
  docked **bottom-left**: `left:10px; bottom:10px; z-index:500`, same card chrome as 5J
  (`rgba(16,38,58,.85)`, 8 px radius, 6px/8px padding), 150 px bar, 11 px gradients from
  `ui.HS_STOPS`, 8 px tick row. render.js paints the bar (single writer).
- **No collision with the tap readout:** `#card` currently sits at `left:10px; bottom:10px`. Move it
  to `bottom: 54px` (legend height ≈ 34 px + 10 px bottom + 10 px gap) so the legend and the readout
  panel never overlap. Keep `#card`'s z-index below nothing / unchanged otherwise.
- **Wind strip**: re-add the deck's second row as `#wind-strip`
  (`<div class="deck-row deck-wind" id="wind-strip" role="status" aria-live="off">Wind: —</div>`,
  20 px tall, font 11 px `#cfe3f2`, tabular-nums, nowrap + ellipsis) and **delete** the ribbon row
  from the deck (`.deck-ramp`, `#ramp-bar` in the deck, `#ramp-ticks`) — the ramp now lives only in
  the map card. Deck total stays **68 px** (48 track + 20 strip), strip flush at the deck base.
- **Text + sync**: restore `ui.windStrip(speedMph, gustMph, bearingDeg)` from 5J
  (`Wind: 15 mph · Gusts 16 mph · From NW 315°`; calm/non-finite speed → `Wind: calm`; no finite
  bearing → no `From` clause) and write it **inside `updateScrubUi(idx)`** — that is the one path
  both the drag (every rAF) and playback (`showFrame`) use, so the strip tracks the cursor
  synchronously. Skip the write when the string is unchanged.

### 3. Sticky day header on the 24h tape (window-edge clamping)

- `src/render.js` `renderTimeline()`: keep exactly one `.day-head` per block (5K behaviour — no 6-h
  repeats). For the **wide (24h) block** store a module-scope reference
  `stickyHead = { el: head, blockLeft: left }`; the 7d centred headers are not sticky.
  Reset `stickyHead = null` at the top of `renderTimeline()`.
- Clamp it in `writeTape(idx)` (the single transform writer, already called every UI frame):
  with `tx = tapeTranslate(idx, pxf, center)` the window's left edge is tape-x `-tx`, so
  ```
  const want = Math.max(6, (-tx) + STICKY_INSET - stickyHead.blockLeft);
  if (stickyHead.el.style.left !== want + 'px') stickyHead.el.style.left = want + 'px';
  ```
  **`STICKY_INSET = 56`** — the `#play` button (48 px, `z-index:10`) overlays the window's left edge
  with a scrim, so the label must ride just right of it. Effect: at the start of the day the label
  sits at the day seam; as soon as that seam scrolls behind the play button the label clamps and
  stays at the window's left edge for the rest of the day. The label must never leave its own block
  (`want + headWidth <= blockWidth` holds for the 550 px 24h block; assert it).
- Cost: one extra `style.left` write per UI frame, skipped when unchanged — the 5H decoupled scrub
  budget must not regress (see Done-when).

## Files allowed to touch

`index.html`, `src/ui.js`, `src/render.js`, `tests/ui.test.js`, `tests/render.test.js`,
`tools/qa/stage5_check.py`, `tools/qa/live_smoke.py`. Nothing else — no physics, no `public/**`,
no new dependency, no `docs/**` (the orchestrator writes receipts).

## Gate contract updates (authorised, and the ONLY ones allowed)

- `[7a] ramp location`: the six-stop ramp is **inside `#map`** again (not in `#deck`), gradient must
  contain the new low stop `rgb(3, 105, 161)` plus the other five; keep the `#legend-card` absent/present check.
- `[15] deck geometry`: measure `#wind-strip` (not `.deck-ramp`) for the flush-to-deck-bottom
  assertion; keep `deckH <= 72`.
- `[7b] touch ergonomics`: the second-row drag must start in `.deck-wind` / `#wind-strip` again and
  must still be non-interactive.
- `[18] timeline labels`: keep everything from 5K (one head per block, pinned at the day start,
  no-repeat, 9 ticks, boundary `12`, all labels inside) and **add the sticky assertions**:
  at idx 0/24/48/72/95 the head must still be inside `#timeline`'s rect **and** its left edge must be
  `>= timeline.left + 52` (clear of the play button); the head's x at idx 95 must differ from idx 0
  by more than 50 px (proves clamping engages); the head must stay inside its own block.
- Node suites: pin `HS_STOPS[0]` = `rgb(3, 105, 161)`, `CALM_RGBA` = `[3,105,161,255]`,
  `OVERLAY_OPACITY` = 0.85, `paintRaster` calm water alpha 255 with land `[0,0,0,0]`, the deck's id
  list (`wind-strip` back; `ramp-bar`/`ramp-ticks` now inside the map card — adjust the
  deck-vs-page assertions accordingly), `windStrip` output cases (restore the 5J block), and the
  ramp-gradient low stop colour.

**Never weaken a gate to make it pass.** Report anything that legitimately fails verbatim.

## Done-when (command output is the proof)

1. `node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js` → all exit 0.
2. `git diff main -- src/wind.js src/wave-math.js src/tables.js public/` → 0 lines.
3. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py` → every group ok except the tolerated pre-existing `[14] live seam` (report verbatim if it appears).
4. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/live_smoke.py --url http://127.0.0.1:8791/index.html` → all ok (server already running on 8791 — do not kill it).
5. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/scrub_bench.py --url http://127.0.0.1:8791/index.html` → modal step latency still ~16 ms, `longtasks=[]`, verdict PASS; quote the numbers (the sticky header must not cost the 5H budget).
6. Evidence in your summary: (a) `[18]` line and the head x at idx 0 vs 95 (must differ, both on screen);
   (b) deck height + strip rect flush + the strip text for a windy frame; (c) the legend card's rect
   (bottom-left, inside the map, no overlap with `#card` — measure both rects with the card open);
   (d) calm paint unit assertion (alpha 255, `[3,105,161]`); (e) `[17]` line verbatim.

## Procedure

- Ponytail ruleset (laziest correct implementation; the 5J code in history is the reference).
- Work on the current branch (`stage5l`); commit in logical steps with `stage5l:` prefixes; do NOT
  merge, tag, or push.
- Re-run the harness after the edits; keep the tree clean.
