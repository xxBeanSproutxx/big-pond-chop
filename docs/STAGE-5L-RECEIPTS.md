# STAGE 5L — RECEIPTS (saturated calm blue, legend card bottom-left, wind strip back, sticky day header)

Branch `stage5l` (off `stage5k` @ c4057ae). **Not merged, not tagged, not pushed.** `main` is still 5I.

Reid's brief (2026-09-12, after reviewing the 5K screenshots): the 0.0 ft calm colour read as dead
concrete → make it a saturated glassy deep lake blue at ~0.85 effective opacity; move the wave ledger
to the map's **bottom-left** and restore the dynamic wind strip flush at the deck base (synced with
the cursor during scrub *and* playback); make the single 24h day header **sticky** at the window edge
so "Saturday 12" stays visible past noon.

Spec `docs/BUILD-SPEC-STAGE5L.md`. Worker: OpenCode (reusing the 5J legend/strip code from git
history). Gates + calm-state visual verification re-run by the orchestrator on the final tree.

## What changed

1. **Calm water: saturated deep lake blue at 0.85 effective.**
   `HS_STOPS[0]` → **`#0369a1`**, `CALM_RGBA` → **`[3, 105, 161, 255]`**,
   **`OVERLAY_OPACITY` 0.72 → 0.85** — the layer opacity had to rise because a Leaflet overlay can
   never paint darker than its own opacity, so 0.85 effective was unreachable at 0.72.
   **Measured (forced-calm run, phone viewport):** lake median **`rgb(34, 121, 168)`** —
   b−r **134**, g−r **87**, b−g **47** — versus the predicted composite `rgb(33, 120, 168)`.
   The slate look is gone; land stays exactly transparent (`[0,0,0,0]`).
2. **Legend card → map bottom-left.** `#legend-card` (bar + six labels, `pointer-events:none`)
   measured rect `[10, 733, 176, 766]` in a map spanning `[0, 72, 390, 776]` — 10 px from the left
   and bottom edges, left of the map's centreline, no map child covers the eastern bays.
   The tap readout panel (`#card`) moved to `bottom: 54px` so the two stack: card rect
   `[10, 589, 240.6, 722]`, legend top 733 → **overlap = false** (asserted with both visible).
3. **Wind strip restored in the deck.** `.deck-ramp` is gone from the deck; `#wind-strip`
   (`role=status aria-live=off`, 20 px) is the second row and is **flush at the deck base**
   (bottom gap **0.0 px**, deck **68 px**). Text comes from the restored `ui.windStrip()` and is
   written **inside `updateScrubUi()`** — the single path both the drag (every rAF) and playback
   (`showFrame`) use. Measured during a real drag: 4 distinct strip values
   (`21 mph · NW 301°` → `23 · NW 295°` → `22 · NW 300°` → `19 · NW 302°`) and the settled frame
   matches the published `windMph` (`18.8` → `19 mph`).
4. **Sticky 24h day header.** The wide block's single `.day-head` is clamped in `writeTape()` to
   `max(6px, windowLeft + STICKY_INSET − blockLeft)` with **`STICKY_INSET = 56`** (clears the 48 px
   play button + 8 px). Measured: header on screen at idx 0/24/48/72/95, x **201 → 64** (137 px of
   travel, clamped 56 px past the window's left edge), inside its block, one header only (no repeats),
   ticks `12,03,06,09,12,03,06,09,12`, nothing clipped. 7d unchanged (centred, non-sticky).
5. **5H scrub path untouched** — the only added work on the UI path is one conditional `style.left`
   write for the sticky header (skipped when unchanged).

## Gate receipts (orchestrator re-run on the final tree)

- Node suites: `parity / wind / render / ui` → **4 × exit 0**.
- `git diff main -- src/wind.js src/wave-math.js src/tables.js public/` → **0 lines**.
- `tools/qa/stage5_check.py` → **`SUMMARY: 24 ok, 0 FAIL`** (even the long-standing `[14] live seam`
  passed this run: `dSpeed=0.40 dDir=3.00 PASS`). Key lines:
  - `[7a] ramp location ok ramp in-deck=False in-map=True legend-card-present=True stops=['0'…'6+'] gradient-six=True`
  - `[15] deck geometry ok deckH=68.0 wind-strip-bottom=844.0 deck-bottom=844.0`
  - `[16] tape architecture ok 24h tape=550.0/window=374.0 runway=176.0 | 7d blocks=7 subs=[8×7]`
  - `[17] scrub decoupling ok moves=31 tx>=moves=True swaps=11<=12=True long-max=0<=50=True idx=42 expected=42=True`
  - `[18] timeline labels (5L) ok one-head=True pinned=True no-repeat=True sticky-window=True sticky-block=True head-x0=201 head-x95=64 shift=137>50=True ticks=9=True all-inside=True`
  - `[10.1] land bleed ok land_alpha=[0,0,0,0] mid_lake_alpha=[255,255]`
- `tools/qa/live_smoke.py --url http://127.0.0.1:8791/index.html` → **10 ok / 0 FAIL**.
- `tools/qa/scrub_bench.py --url http://127.0.0.1:8791/index.html` → **VERDICT 24/24 PASS**,
  modal step latency **16.76 / 16.79 / 17.96 ms** (390×844 mouse / 360×800 mouse / 360×800 touch);
  the 390×844 and touch cases report `longtasks=[]`, the 360×800 mouse case one 50 ms task (at the
  gate's `<=50` edge, same class of pre-existing drag-start/release build — 5H.1).
- Independent orchestrator verifier (forced-calm data injected at the network layer, phone viewport,
  real browser): **14 ok / 0 FAIL**.

## Visual receipts

`tmp/5l-shots/5l-{calm,calm-card,24h-start,24h-afternoon,24h-evening,7d}.png` (gitignored; delivered in chat).

## Honest notes

- **Opacity is now global:** `OVERLAY_OPACITY` 0.85 applies to every frame, so wave colours are also
  ~13 % more opaque than before. That is what makes the calm water land at 0.85; per-frame opacity
  would need a second overlay layer.
- **Trade-off accepted:** at 0.85 the basemap under the water is largely hidden — OSM names under the
  lake are dim now (the vision read of the calm shot: "no meaningful map detail visible through the
  water"). Reid asked for saturation over see-through; if he wants both, the middle ground is
  `OVERLAY_OPACITY ≈ 0.65` with the same blue (names read, water still clearly blue).
- **7d is not sticky** — only the wide 24h block clamps, per the brief.
- `#1d4ed8` (the more electric blue Reid also named) is a one-line swap in `HS_STOPS[0]` + `CALM_RGBA`.
- Still waiting on Reid's Windy timeline reference photo for a deck/strip styling pass (label
  placement, tick density, band treatment).

## Status

- Branch `stage5l` (3 commits: spec, product+suites, gates). `main` still at 5I; nothing deployed.
- Awaiting Reid's screenshot review (and the Windy reference) before any merge / Pages push.
