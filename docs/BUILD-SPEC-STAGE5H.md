# BUILD SPEC — Stage 5H: Touch Decoupling & Scrub Performance

> **If any number in this spec conflicts with observed reality, trust reality and proceed; record the conflict in your report.**
> Follow the ponytail ruleset: laziest correct implementation. No new dependencies, no new build steps, no re-architecture.

## Goal

On a phone, dragging the tape is janky: the lake overlay is rebuilt and re-encoded for
almost every scrubbed frame, and the 24 h tape has **zero runway** (its width equals the
viewing window, so the thumb hits a clamp immediately). Stage 5H:

1. **Decouples the tape UI from the map render** — tape transform + amber pill update run on
   *every* animation frame (zero drag latency); the Leaflet overlay repaints at a throttled
   **12-15 fps**, skipping when a previous paint is still pending, and snapping to the exact
   final frame on `pointerup`.
2. **Kills blob/overlay thrash during drag** — no full `OffscreenCanvas` encode + `setUrl`
   per scrubbed frame; in-flight results for indices the user has already scrubbed past are
   dropped.
3. **Expands the 24 h tape runway** — 24 h density goes from `190 px/day` (which the window
   floor silently turns into `max(190, window)` = **374 px at a 374 px window → 0 runway**)
   to **~550 px/day (≈22.9 px/hour, ≈5.73 px/frame, ~176 px of runway)**; 7 d stays 190 px/day.
4. **Produces a mobile drag benchmark** (`tools/qa/scrub_bench.py`) whose before/after numbers
   are printed in the receipts.

### Measured baseline — pre-stage5h @ 390×844, dsf=2 (orchestrator probe, this box)

```
24h: window 374 px, tape 374 px, runway   0 px, pxf 3.8958
7d : window 374 px, tape 1330 px, runway 956 px
30-step / 240 px drag: step latency median 16.62 ms, p90 16.88 ms, MAX 159.52 ms
                       overlay src swaps 28, blob creations 4, long tasks [73, 69] ms
                       live frame build 45.5 ms, encode 20.5 ms
```

Two facts drive the design: (a) **28 overlay `src` swaps for one drag** — most of them
`showFrame` re-setting a URL the overlay already had (cache hit → same `blob:` URL re-applied),
and (b) the 159 ms main-thread stall = a full raster build (45.5 ms) + encode landing inside a
drag frame. Both are fixed in §B/§C.

## A. Tape density — `src/render.js`

```js
// 7 d unchanged at 190 px/day; a single 24 h day is now a 550 px/day tape (~23 px/h)
// and still fills at least the viewing window (desktop/tablet: window-fill, as in 5G).
function pxPerDay(horizon, windowW) {
  return horizon === '7d' ? 190 : Math.max(550, Math.round(Number(windowW) || 0));
}
```

- `pxPerFrame = pxPerDay / 96` is unchanged as a rule (24 h → 5.7292 px/frame at 374 px window;
  7 d → 1.9792).
- Nothing else changes: `renderTimeline()`, `placeNowTick()`, `writeTape()` and `idxFromDrag()`
  all read density through `pxPerFrame()` and pick the new value up automatically. Do **not**
  hard-code 550 anywhere except `pxPerDay()`. Do not add CSS or DOM for this.
- Consequence to state in your report: at a ≥550 px-wide viewing window the 24 h tape is
  window-fill (runway 0) exactly as in 5G — 550 px/day is the phone case.

## B. Decoupled drag path — `src/render.js`

During an active drag the UI must never wait on raster work. Split the current single path
(`pointermove → requestFrame(idx) → rAF → showFrame(idx)`, where `showFrame` = full build +
DOM stats) into two:

1. **Every drag frame (60 fps, zero latency):** the `pointermove` rAF flush resolves the index
   from the *delivered* `clientX` and calls a new **UI-only** step:

   ```js
   // UI-only: reticle-side of the drag. Cheap by construction — text + one transform.
   function scrubUiTo(idx) {            // idx already clamped by the caller
     dragIdx = idx;                     // latest target the map owes us
     updateScrubUi(idx);                // amber pill text/aria + writeTape() (unchanged helper)
     scheduleMapPaint(idx);             // throttled, worst-case 1 in-flight build
   }
   ```

   - `updateScrubUi()` is the existing helper; keep it the single writer of pill text + tape
     transform. **Skip a `textContent` write when the string is unchanged** (set only on change).
   - The tape transform must be written for the index under the drag — do not gate it on any
     timestamp, and do not round the tape position coarsely.

2. **Throttled map paint:**

   ```js
   const MAP_PAINT_MIN_MS = 72;         // ~13.9 fps — inside the 12-15 fps band
   ```

   - `scheduleMapPaint(idx)`: if a paint is already armed with the same target index, drop it;
     otherwise arm ONE timer/rAF-gated paint that runs only when
     `now - lastMapPaintMs >= MAP_PAINT_MIN_MS`. If the gate is not open yet, leave the newest
     index stashed and paint it when the gate opens (**the newest index always wins** — never a
     queue of stale indices).
   - **Skip when busy:** while a previous paint's `convertToBlob`/encode is still in flight
     (see §C) do not start another build — keep the newest index stashed and paint it when the
     in-flight one settles or the gate opens.
   - The paint is the existing `showFrame(idx)` (build + `setUrl` + stats DOM). Reuse it; do not
     fork a second renderer.

3. **Snap on release:** in `endScrub()` cancel the pending throttle, then call
   `showFrame(dragIdx)` (final clamped index) **immediately, bypassing the throttle and the
   busy skip** — after `pointerup` the resting state must be the exact final frame, always.
   `dragIdx` is the index the tape UI is already showing at that moment, so the pill never
   moves on release.

4. **Do not regress:** play/programmatic/keyboard paths keep `requestFrame()`/`showFrame()`
   exactly as they are (rAF-coalesced, `[7b]` tape test unchanged); `#play` stays pinned at the
   window's left edge; the `.32 s` glide transition, drag-vs-play transition toggling, deck-wide
   `setPointerCapture`, the `closest('button, [role=button], a, input')` guard, the
   never-auto-resume rule, and `prefers-reduced-motion` all stay.

5. **Touch is not a special case.** The drag path is pointer-type agnostic — no `pointerType`
   branch, no touch-only code path, no passive-listener changes. (The 159 ms stall fixed here
   is the same one a mouse drag reproduces; that is why the bench can drive it with a mouse.)

## C. Blob/overlay thrash — `src/render.js`

1. **Dedupe the overlay URL.** Track the last URL applied to the image overlay and skip
   `overlay.setUrl(url)` when it is identical (cache hits re-apply the same `blob:` URL today —
   24 of the 28 baseline swaps). Apply the same rule to the async result path; the URL-dedupe
   state must reset whenever the overlay's raster dims change (`regather()` path) — the same URL
   for a different `W×H` is a different image.
2. **One in-flight build, newest wins.** Increment a generation token on every
   `scheduleMapPaint()` target change; a build/encode result may only be applied when its
   generation is still current **and** `shouldPaintResult(meta, currentMeta())` (the existing
   stale guard — keep it). Dropped results must not be applied and must not be re-queued; a
   dropped result that is still in the frame cache stays cached (its URL is revoked by LRU
   eviction as today — do not add a second revocation path).
3. **Nothing else about the cache changes:** `createFrameCache`, `cacheKey`, `FRAME_CACHE_MAX`,
   `revokeUrl`, the play-width vs zoom-aware width classes, and the prefetch behaviour stay.
   Do not change raster width, smoothing, colouring or the fallback `toDataURL()` path.
4. **In-flight cancellation is "drop", not "abort":** `convertToBlob()` has no cancellation;
   do not attempt to abort a promise. Dropping = not applying a stale result (§C2), and never
   starting builds for indices the user has already scrubbed past (§B2).

## D. Bench — `tools/qa/scrub_bench.py` (NEW)

Playwright, run with `/home/reid/.hermes/hermes-agent/venv/bin/python`, Chromium, `--url`,
`--label`, `--out` (default `tmp/scrub-bench`). Serve-agnostic (the harness will be pointed at
a locally served tree AND at the deployed site). Exit 0 always; print a machine-readable JSON
block + a human table; read PASS/FAIL lines for the verdict.

Requirements:

- Viewports: **390×844 dsf=2** and **360×800 dsf=2** (the two phone cases the project already
  tests at), plus one **CDP touch drag** (`Input.dispatchTouchEvent` via
  `context.new_cdp_session(page)`, `touchStart`/N× `touchMove`/`touchEnd`) at 360×800 so the
  touch path is exercised end-to-end. If the CDP touch path cannot be driven in this
  environment, print the verbatim error and mark that row `unavailable` — never fake it.
- Instrument from outside the page (`add_init_script`, script **body** string — a function
  expression installs nothing): count `URL.createObjectURL` calls, count blob-`src` writes on
  `HTMLImageElement.prototype`, count writes to `#track-tape`'s inline `transform`
  (wrap `CSSStyleDeclaration.prototype.setProperty`/the `style.transform` setter — whichever
  actually catches `el.style.transform = …` in Chromium), and record long tasks via
  `PerformanceObserver({entryTypes:['longtask']})`. **Assert each instrument exists** (truthy)
  before reporting a number from it.
- Drag: 30 steps over 240 px across `#timeline`'s centre, dragging LEFT (= forward in time).
  For each step record the delivered `clientX` (capture-phase listener) and the driver
  round-trip ms. Report: **tape transform writes ≥ moves delivered** (the UI path is
  unthrottled), **overlay src swaps and blob creations during the drag**, **long-task list and
  max**, **map paints during the drag** (expect 8-12 for a ~700 ms drag at 12-15 fps), and the
  **post-`pointerup` index exactness** — recompute `idxFromDrag(finalDx, startIdx, pxf, n)`
  from the delivered coordinates and require `aria-valuenow` to equal it (snap = exact).
- Also print, for both horizons: window width, tape width, **runway = tape − window**, px/day,
  px/hour — the 24 h runway number is a headline receipt.
- The bench must run unchanged against the **pre-stage5h** tree (no dependency on anything 5H
  adds) so the before/after pair is one command either side.

## E. Pre-authorised gate deltas (numbered — anything else you change in a test/harness is a red flag)

1. `tests/render.test.js` — `pxPerDay`: `24h` → `550` at window 374, `550` at window 120;
   `pxPerFrame('24h', 374) === 550/96`. Add a `runway` assertion:
   `pxPerDay('24h', 374) - 374 >= 150` and `pxPerDay('7d', 374) === 190`.
2. `tools/qa/stage5_check.py` — the two `pxf`/`pxf_for` density formulas
   (`190.0 if horizon == "7d" else max(190.0, round(tlW))`) → `550.0` floor for 24 h. Scan the
   whole file for any other drag dx→index expectation derived from the old 3.8958 pxf and update
   it the same way (list them in your report).
3. `tools/qa/stage5_check.py` — 24 h tape assertion `tapeW >= tlW - 2` stays, and gains the
   runway check: `tapeW >= tlW + 100` at 390×844 (measured 550 vs 374 → 176). 7 d assertion
   (`1100 <= tapeW <= 1400`) unchanged.
4. `tools/qa/stage5_check.py` — **new group `[17] scrub decoupling`**: a scripted 30-step drag
   at 390×844 in 24 h mode asserting (a) overlay src swaps ≤ 12 during the drag, (b) tape
   transform writes ≥ delivered moves, (c) no long task > 50 ms attributable to the drag,
   (d) after `pointerup` `aria-valuenow` equals the expected final index, (e) the amber pill's
   text equals the frame at that index. Keep the existing `[16]` tape-architecture assertions
   (pill dx 0.00 px, drag deltas exact, both clamps) green — they are the 5G contract.
5. New node-testable pure helper: expose the throttle decision as a pure function
   (e.g. `shouldPaintMap(nowMs, lastPaintMs, busy, minIntervalMs)`) and unit-test it in
   `tests/render.test.js` (gate closed → false; open + not busy → true; open + busy → false).

## F. Out of scope (do NOT touch)

- `src/wave-math.js`, `src/tables.js`, `src/wind.js`, `src/ui.js` — **zero diff** (physics,
  data, labels, formatting are frozen).
- `public/*`, `tools/export_tables.py`, the Open-Meteo fetch path, deployment/GitHub Pages.
- `index.html` — only if a CSS/DOM change is strictly unavoidable; if you touch it, justify
  each line in your report.
- `docs/BUILD-SPEC-STAGE5H.md` — read-only reference, it is this file.

## G. Done-when (all must be true, print the evidence)

1. Four node suites green: `parity`, `render`, `ui`, `wind` (`node tests/<name>.test.js`) —
   parity must be byte-identical to pre-stage apart from timing lines.
2. `tools/qa/stage5_check.py` green on the merged tree, with `[16]` and the new `[17]` group
   listed in the summary (report the ok/FAIL counts verbatim).
3. `tools/qa/scrub_bench.py` runs on both trees and prints the before/after table — 24 h runway
   0 → ≥150 px, overlay src swaps during the drag 28 → ≤12, drag-attributable long tasks
   eliminated (max step-latency not more than ~2× median).
4. Your own two-run determinism check on any one gate (same command twice, same verdicts).
5. A `docs/STAGE-5H-RECEIPTS.md` draft: what changed per file, the numbered gate deltas with a
   per-change justification, the bench table, the exact commands, and any spec/reality conflict.

Report back: files changed, `git diff --stat`, the harness summary line, the bench numbers
before and after, and anything in this spec that reality contradicted.
