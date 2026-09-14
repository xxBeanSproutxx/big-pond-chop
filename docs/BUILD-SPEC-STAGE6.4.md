# BUILD SPEC — Stage 6.4 smoothness (executable)

Input/authority: `docs/SPEC-stage-6.4-smoothness.md` **APPROVED** with all recommended defaults
(D1.1 `inertia:false` · D1.2 viscosity 0.75 · D1.3 native recoil · D1.4 skip refits mid-gesture ·
D2.1 suspend paints while scrubbing · D2.2 valve 1.2 s · D2.3 drag raster 512 · D3.1 keep the blob
overlay · D3.2 extend prefetch to scrubs · D3.3 canvas layer = backlog).

Baseline `8be5ae6`, git tree clean. **FILES ALLOWED TO TOUCH (closed list):** `src/render.js`,
`tools/qa/stage5_check.py`, `tests/render.test.js` (only if an assertion genuinely breaks). Nothing
else — not `index.html`, not `public/*`, not other `src/*`, not `docs/*`.

## 1. `src/render.js` — item 1 (D1.1, D1.4)

1. In `setupMap()`'s `L.map('map', {...})` options add `inertia: false` with comment
   `// 6.4 D1.1: no momentum — the release tail collapses to one fixed-duration recoil (SPEC §1.4)`.
   Keep `maxBoundsViscosity: 0.75` (D1.2) and all other options exactly as they are.
2. In `scheduleRefit` (the debounced `fitLake` re-arm, ~line 652): if a drag is in progress when the
   debounce fires (`map && map.dragging && map.dragging.moving()`), **re-arm the timer** instead of
   running `fitLake()`, so the refit still lands after the gesture (do not silently drop it). Cap the
   re-arm so it cannot loop forever.

## 2. `src/render.js` — item 2 (D2.1, D2.2, D2.3) — strict scrub suspension

3. **Delete** the velocity-EMA machinery: constants `V_HI`, `V_LO`, `V_EMA_ALPHA` (lines 26-28) and
   the state/writes that exist only to feed them: `vEma`, `lastX`, `lastT`, the `suspended` flag, the
   `120 ms` decay branch inside the paint rAF, and the velocity computation in the deck `pointermove`
   handler. Keep the `dragRaster` switch in that handler and keep `scrubUiToMinutes(...)` exactly as
   it is (the tape/pill path must not change).
4. **Keep** `SUSPEND_MAX_MS = 1200` (D2.2), `suspendStartMs` (re-purposed as the valve clock),
   `MAP_PAINT_MIN_MS` + `shouldPaintMap()` (still used by the post-settle catch-up path — see 6),
   `DRAG_RASTER_W = 512` (D2.3) and the pointerup settle (`endScrub` → `cancelMapPaint` +
   `showFrame(dragIdx)`).
5. Rewrite the `scheduleMapPaint` rAF body to be strictly suspension-based, keeping the existing
   stash/newest-wins/`target === cur` skip/`busy` semantics:
   * `scrubbing === true` → **no paint**, except one anti-freeze paint when
     `now - suspendStartMs >= SUSPEND_MAX_MS` (then reset the clock). Otherwise re-arm with the newest
     target and return.
   * `scrubbing === false` (reachable from the in-flight-encode settle callback) → paint when
     `!busy`; keep the `shouldPaintMap(...)` guard so a re-arm burst cannot double-paint. If busy,
     re-arm with the newest target.
   * `busy` still means "an encode is in flight" (`inFlightEncode > 0`) — unchanged.
6. `endScrub`: reset the valve clock (`suspendStartMs = 0`) instead of the deleted `suspended` flag.
7. Update every stale comment that references the velocity gate thresholds.

## 3. `src/render.js` — item 3 (D3.2) — neighbour prefetch for scrubs

8. Add, next to the existing playback `prefetch()` (keep that function untouched):
   ```js
   // 6.4 D3.2: warm the neighbours of the shown index so the next scrub/settle is not a cold build.
   // Never builds while a gesture is live — a 23-41 ms cold build would eat the frame budget the
   // suspension exists to protect; the drag-start trigger therefore queues and runs when idle.
   function prefetchNeighbours() {
     if (!frames.length || scrubbing || playing) return;
     for (let i = cur - 1; i <= cur + 1; i++) {
       if (i >= 0 && i < frames.length && i !== cur) frameFor(i);
     }
   }
   function schedulePrefetchNeighbours() {
     if (typeof requestIdleCallback === 'function') requestIdleCallback(prefetchNeighbours, { timeout: 400 });
     else setTimeout(prefetchNeighbours, 0);
   }
   ```
9. Call `schedulePrefetchNeighbours()` from (a) the deck `pointerdown` handler (the drag-start trigger)
   and (b) `endScrub`, after the settle paint. Nothing else calls it.

## 4. `tools/qa/stage5_check.py` — new gate group `[21]`

Add a `[21] 6.4 smoothness` group registered through the existing `safe(...)` mechanism, printing
PASS/FAIL lines with the measured numbers. Reuse the file's existing instrumentation patterns
(the `[20]` block's attrib script, `S63_*` helpers) and the in-page instrumentation bodies from the
throwaway rigs in `tmp/64-smoothness/*.py` (readable, gitignored). Gates:

* **[21.1] P2/P4 · native recoil:** `map.options.inertia === false`; one synthetic drag that ends at
  the bound produces exactly one `moveend`, ≤ 1 direction reversal, and the pane ends inside the
  pan box (0 px overshoot after settle).
* **[21.2] P1 · excursion law:** on that drag, `|excursion − (1 − 0.75) × over-travel| ≤ 3 px`
  (excursion = peak pane offset beyond the clamped edge; over-travel = the commanded drag distance).
* **[21.3] P3 · recoil duration:** all pane motion ends within 400 ms of pointerup (fixed-duration
  recoil) and no motion is observed after that.
* **[21.4] T2/T3 · suspension:** on a *slow* paced drag (≈0.04-0.15 px/ms, i.e. the regime the old
  velocity gate did NOT suspend): `URL.createObjectURL` during the gesture === 0, `setUrl` === 0, and
  tape-write latency p90 ≤ 1 ms (instrument the `#track-tape` transform setter against the last
  pointermove timestamp).
* **[21.5] T1/T4 · transport:** fast drag: `#track-tape` translateX advances on ≥ 95 % of rAF frames,
  ≤ 1 non-advancing write, frames > 33 ms === 0.
* **[21.6] T5 · settle:** pointerup → the overlay settles on the released index (`aria-valuenow` ===
  expected frame) and a new overlay `src`/`naturalWidth > 0` appears within 70 ms.
* **[21.7] T6/D2.2 · valve:** a 2.0 s continuous fast drag produces ≥ 1 and ≤ 2 overlay swaps, with a
  gap ≥ 1.1 s between them.
* **[21.8] O2 · no long task during a gesture** (`PerformanceObserver('longtask')` > 50 ms === 0 while
  scrubbing). The settle paint's cold-build cost is **informational only** — print it, do not gate it.
* **[21.9] O3 · heap:** after 30 frame updates, retained `JSHeapUsedSize` (CDP, post-`collectGarbage`)
  ≤ +100 KB over the pre state.
* **[21.10] O5 · playback:** 7 d playback ≈ 10 s → 0 long tasks > 50 ms; print the build p50 with an
  informational bar of ≤ 25 ms.

Rules: **never weaken a gate to make it pass.** If a gate fails for a structural reason, leave it
failing and report the raw numbers. Report each gate's measured value next to its verdict.

## 5. Verification the builder must run and report (verbatim output)

1. `node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js`
2. `flutter`-free harness: `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py`
   → report the full PASS/FAIL summary lines, including the `[21]` group and any pre-existing
   failures (known: `[14] live seam` is live-API data-dependent; `[17]` long-task flake — do not
   "fix" either by weakening it).
3. `/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/scrub_bench.py` → report PASS/FAIL lines.
4. `git diff --stat` and `git status --porcelain` (the tree must contain ONLY the allowed files).

Do not commit, tag, push or deploy — the orchestrator owns that.
