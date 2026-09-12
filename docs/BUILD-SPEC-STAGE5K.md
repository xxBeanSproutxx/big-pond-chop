# BUILD SPEC — Stage 5K: UI revision (Reid rejected 5J's visual direction)

Repo: /home/reid/projects/big-pond-chop (branch `stage5k`, off `stage5j` @ 6fb260d)

## Context — what Reid rejected (his words, 2026-09-12)

> "Revert the Floating Legend Card & Bottom Text Strip … Restore the wave height color scale ribbon
> docked flush to the base of #deck. Do NOT float it inside the map canvas where it covers bays and
> collides with attribution. Remove the bottom text row … Fix Calm Lake Transparency: do NOT render
> calm water as an opaque dark block … Fix the 24h Day Header Stutter: remove the 6-hour repeating
> day label hack … Keep the 16.4ms decoupled scrub performance from 5H intact."

5J is NOT merged. This stage nets the tree back toward 5G visuals where Reid wants them, keeps the
parts of 5J he did not reject, and changes the calm-water treatment to translucent.

## Goal — four edits, nothing else

### 1. Deck ribbon back; floating legend card and wind strip deleted

- `index.html`: restore the 5G ramp row in `#deck` (`.deck-row.deck-ramp` containing
  `#ramp-bar` + `#ramp-ticks` with the six labels `0 1 2 3.5 4.5 6+`), exactly as `git show main:index.html`
  has it (11 px bar with the `#33506b` border, tick row 8 px `#9fc3dd`, flush at the deck base).
  `#deck` stays **68 px** (48 track + 20 ribbon) and the ribbon's bottom must equal the deck's bottom.
- Delete the `#wind-strip` row (element, `.deck-wind` CSS, the `role=status`/`aria-live` markup) and
  the `#legend-card` / `#legend-card-bar` / `#legend-card-ticks` card (element + its CSS). Note
  `.deck-ramp`'s 20 px row is what the ribbon occupies — the deleted text row must not leave a gap.
- `src/render.js`: the ramp painter already exists — point it back at `#ramp-bar` (keep it in
  render.js as the single writer; do NOT re-add the old `index.html` inline snippet) and delete the
  `#legend-card-bar` lookup, the `windStripEl` const and the strip write inside `updateScrubUi()`.
- `src/ui.js`: delete `windStrip()` and its export (now dead). Keep the header `·` delimiter fix and
  the `.leaflet-bottom` lift from 5J — Reid did not reject those.

### 2. Calm water goes translucent — the basemap must read through it

- `src/ui.js`: `HS_STOPS[0]` `#0f2744` → **`#2a5885`** (tranquil water blue); `CALM_RGBA`
  `[15, 39, 68, 255]` → **`[42, 88, 133, 115]`** (alpha 115/255 = 0.45). Keep the exported
  `CALM_RGBA` and the single-source-of-truth invariant (its rgb must equal `HS_STOPS[0]`'s rgb).
  Add a comment stating the composite: the Leaflet overlay applies `OVERLAY_OPACITY 0.72`, so the
  on-screen calm layer reads ≈0.32 alpha over the desaturated basemap — intentional, so lake-bed
  detail, depth cues and island/bay names stay legible through calm water.
- `src/render.js`: keep 5J's land/calm separation exactly (`raster[k] > 0` → ramp;
  `else landFrac[k] < 0.5 ? CALM_RGBA : [0,0,0,0]`) — land must stay **exactly** transparent.
  Only the constant changes, so `paintRaster`/`encodeOffscreen` keep their signatures.
- Do NOT make `colorForHs()` translucent — the ramp above 0 ft stays opaque; only the 0.0 ft floor
  is translucent.

### 3. 24h day header: one per block, pinned at the start of the day

- `src/render.js` `renderTimeline()`: delete the 6-hour repeat loop (the `w > 275` branch). Render
  **exactly one** `.day-head` per day block, left-aligned at the block's start
  (`left: 6px; transform: none`), i.e. pinned at the day boundary; 24h has one block and therefore
  exactly one `"Saturday 12"` on the tape — no repeated date text.
- 7d keeps its current single **centred** header per 190 px block (unchanged — do not touch it).
- Keep the tick work from 5J: h=0 left-anchored `"12"` with `.edge`, the 3-hourly `03/06/09/…` set,
  and the **last block's** right-anchored `"12"` boundary marker over the date seam. 24h therefore
  still renders 9 ticks (`12,03,06,09,12,03,06,09,12`), 7d still 8 per block, nothing clipped.

### 4. Do not touch the 5H scrub path

`scrubUiTo()`, `scheduleMapPaint()`, `shouldPaintMap()`, `endScrub()`, the rAF coalescing and the
`paintGen`/`inFlightEncode` guards stay byte-identical. Removing the strip write from
`updateScrubUi()` is the only edit on that path (it makes the drag **cheaper**, not slower). The
harness `[17] scrub decoupling` gate and `tools/qa/scrub_bench.py` must both still pass.

## Files allowed to touch

- `index.html`
- `src/ui.js`, `src/render.js`
- `tests/ui.test.js`, `tests/render.test.js`
- `tools/qa/stage5_check.py`, `tools/qa/live_smoke.py`

Nothing else. Out of scope: `src/wind.js`, `src/wave-math.js`, `src/tables.js`, `public/**`,
`docs/**` (receipts are the orchestrator's), any new dependency, any physics change.

## Gate contract updates (authorised, and the ONLY ones allowed)

- `[7a] ramp location`: back to "ramp is INSIDE `#deck` and NOT inside `#map`"; six stops; gradient
  must contain the new low stop `rgb(42, 88, 133)` plus the other five. Update the comment to record
  the 5K revert (5B → 5J floated it → 5K docks it again).
- `[15] deck geometry`: measure `.deck-ramp` again (not `#wind-strip`); keep `deckH <= 72` and the
  "ribbon bottom == deck bottom (±2 px)" assertion. Restore the original detail wording.
- `[7b] touch ergonomics`: the second-row drag must start in `.deck-ramp` again; keep the extra
  assertion that it is non-interactive (that tightening was good) and drop the wind-strip-specific one.
- `[18] timeline labels (5J→5K)`: in 24h assert **exactly one** `.day-head` in total and that its
  left edge sits within 12 px of its block's left edge (pinned at the day start); assert the 9-tick
  list, the left-anchored `12`, the last-block right-anchored boundary `12`, all labels inside their
  blocks, and no repeated date text (no two heads share the same text within the same block).
  In 7d keep the existing per-block assertions (8 ticks each, min `12`-gap ≥ 20 px).
- `tools/qa/live_smoke.py`: `.deck-ramp` again (revert the 5J `#wind-strip` edit).
- Node suites: update the pins that changed — the 0 ft stop colour (`rgb(42, 88, 133)`),
  `CALM_RGBA === [42,88,133,115]` and its agreement with `HS_STOPS[0]`, `paintRaster` calm-water
  alpha **115** (not 255) with land still `[0,0,0,0]`, the deck's frozen-id list
  (`ramp-bar`/`ramp-ticks` back in, `wind-strip`/`legend-card-*` out), and delete the `windStrip`
  test block (the helper is gone). The calm-tier tests stay.

**Never weaken a gate to make it pass.** If something legitimately fails, fix the product or report it
verbatim in your summary.

## Done-when (command output is the proof)

1. `node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js` → all exit 0.
2. `git diff main -- src/wind.js src/wave-math.js src/tables.js public/` → 0 lines.
3. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py` → every group ok except the tolerated pre-existing `[14] live seam` (and the marginal `[17]` headroom if it trips) — report either verbatim.
4. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/live_smoke.py --url http://127.0.0.1:8791/index.html` → all ok (a server is already running on 8791; do not kill it).
5. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/scrub_bench.py` (add `--url http://127.0.0.1:8791/index.html` if it supports it) → modal step latency still ~16 ms and no in-drag long tasks; quote the numbers.
6. Measurement evidence in your summary: (a) ribbon rect flush at the deck base + `deckH=68`;
   (b) a `paintRaster` unit assertion showing calm water `[42,88,133,115]` and land `[0,0,0,0]`;
   (c) 24h `.day-head` count (must be 1) and its left offset, plus the tick list;
   (d) `[17]` line verbatim.

## Procedure

- Follow the ponytail ruleset (laziest correct implementation — this stage is mostly deletion).
- Work on the current branch (`stage5k`). Commit in logical steps with `stage5k:` prefixes; do NOT
  merge, tag, or push.
- Re-run the harness after the edits; keep the tree clean of stray files.
