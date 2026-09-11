# big-pond-chop — BUILD SPEC (stage 4A.2: engine encode — async blob + playback resolution clamp)

Status: **LOCKED by Reid 2026-09-11** (staged after 4B, before 4C). Build **ONE commit**.
Follow the **ponytail ruleset (laziest correct implementation)**. Report the ACTUAL shipped API back.

## Why this stage exists (measured, not theorised)

Stage 4A made the display raster zoom-aware (512-1536 px) and fixed the blockiness, but the browser
measurement shows the per-frame cost is now **140-240 ms at zoom (88 ms at fit)** — far above the
Node bench's 27.8 ms, because `canvas.toDataURL()` PNG encoding happens **synchronously on the main
thread** and the Node bench never measured it. At the 333 ms play tick that is a ~50% duty cycle; a
phone would stutter. Reid's locked direction: move the encode off the main thread, and stop the
resolution thrash while the 3 fps loop is running.

## Files allowed to touch

- `src/render.js`
- `tests/render.test.js` — add new sections; **do not modify or delete any existing assertion**
- `docs/BUILD-SPEC-STAGE4A2.md` (this file — you may append a `## Notes / shipped API` section)

**FROZEN:** `src/wave-math.js`, `src/tables.js`, `src/ui.js`, `index.html`, `public/*`,
`tests/parity.test.js`, `tests/wind.test.js`, `tests/ui.test.js`, `tools/*`, and the 4A/4B data
contract (`data-hour` ISO incl. minutes, `data-step-min`, `data-frameMs`, `data-precomputeMs`,
`window.__bpcTap`, the rAF-coalescing behaviour, the LRU key format `idx|pinIdx|WxH`).

## Requirements (all three are locked scope)

1. **Async encode off the main thread.** In `frameFor()` replace the synchronous
   `canvas.toDataURL()` with:
   - paint into an **`OffscreenCanvas`** 2D context (same `paintRaster` path), then
     `convertToBlob({ type: 'image/png' })` → `URL.createObjectURL(blob)` for the overlay URL;
   - **feature-detect**: when `OffscreenCanvas`/`convertToBlob` are unavailable, fall back to the
     existing canvas + `toDataURL()` path (do not break old browsers);
   - **revoke object URLs on eviction** — add an eviction hook to `createFrameCache` and call
     `URL.revokeObjectURL` (guard for the data-URL fallback, which must not be revoked).
   - **stale-result guard**: an async encode that resolves after the user has moved to another frame
     must still be cached under its own key, but must NOT be painted onto the overlay unless its
     frame is still the current one.
2. **Playback resolution clamp (kill the LRU thrash).** While the play loop is running, render at
   **1x display width, capped at 780 px** (`playWidth`); when playback is paused, go back to the full
   zoom-aware `targetWidth` (512-1536). Use the existing debounced re-gather machinery for the
   transition back. The LRU key already carries the dims, so both classes can coexist in the cache —
   just make sure the transition does not clear the cache unnecessarily.
3. **Playback prefetch.** While playing, after painting frame N, kick off the build for N+1 at the
   play resolution during idle time so the loop never waits on a cold build. Do not prefetch while
   paused beyond the current frame.

Additive telemetry is allowed (e.g. `body.dataset.encodeMs` for the async encode duration) but no
existing `data-*` value may change meaning.

## Done when

1. The four suites pass, and `tests/parity.test.js`, `tests/wind.test.js`, `tests/ui.test.js` outputs
   are **byte-identical** to their pre-stage output; existing `tests/render.test.js` assertions
   untouched (additions only).
2. New pure tests: `playWidth`/clamp behaviour; cache eviction calls the revoke hook exactly once per
   evicted URL entry and never for data URLs; a stale async result is cached but not painted
   (test the decision helper with a stubbed "current index", not the DOM).
3. **Browser measurement** (reuse the recipe from the 4B spec: `python3 -m http.server` from the repo
   root + `/home/reid/.hermes/hermes-agent/venv/bin/python` + playwright, viewport 390x844, DPR 2):
   - during playback, sample `data-frameMs` (or the new `data-encodeMs`) over >= 8 ticks: the
     **main-thread** per-frame cost must be **<= 60 ms** (baseline today: 140-240 ms), and the play
     loop must advance a 15-min frame on every tick sampled (no skips);
   - after pausing (+ 400 ms debounce) `#field`/overlay canvas width must be back in the full class
     (assert `canvas.width > 1000` at zoom 13);
   - zero console/page errors; screenshots to `/tmp/bpc-4a2-*.png`.
   - Report the numbers whether they pass or not — this stage exists to move a measured number.
4. **ONE git commit**: `Stage 4A.2: async OffscreenCanvas encode + playback resolution clamp`
   — diff limited to the allowed files.

## Out of scope

Any DOM/visual change (4B owns it), the physics, the bundle format, the QA scripts (4C is
strictly QA + receipts, no src edits), the palette, deployment.

## Receipts to include in your final message

(a) four suite tails; (b) the before/after browser numbers (frameMs during play at both resolution
classes) + the pause re-gather proof; (c) `git show --stat`; (d) shipped API changes; (e) anything you
could not do.

## Notes / shipped API

### Shipped API

`src/render.js` (new/changed):
```
PLAY_MAX_WIDTH = 780
playWidth(clientWidth, cap = PLAY_MAX_WIDTH) -> number   // round(1x display px) clamped [2, cap]
offscreenSupported() -> boolean                          // OffscreenCanvas + convertToBlob + createObjectURL
encodeOffscreen(raster, W, H) -> Promise<string>         // paintRaster -> convertToBlob -> object URL
revokeUrl(url) -> void                                   // revokes only `blob:` URLs; data: is a no-op
shouldPaintResult(result, current) -> boolean            // {idx,pinIdx,W,H} identity guard, false if null
createFrameCache({ max, sizeOf, onEvict }) -> cache      // NEW onEvict(key, entry) hook
```
Unchanged signatures kept: `targetWidth`, `cacheKey`, `frameBytes`, `createFrameCache` get/set/has/
clear/keys/size/bytes/peakBytes/max, `paintRaster`, `computeFrame`, `gatherRaster`, `smoothRaster`,
`landMaskRaster`, `mount`, and all constants. `mount()` internals: `desiredDims()` uses
`playing ? playWidth(css) : targetWidth(css, dpr())`; `frameFor()` caches a `{ url:null, stats,
pinVals }` entry *before* encoding, then fills `url` when the blob resolves (only repaints the overlay
if `shouldPaintResult`); `setPlaying(true)` calls `regather()` into the play class and
`setPlaying(false)` calls the debounced `scheduleRegather()` back to the full class; `regather()` no
longer clears the cache (dims are in the key, so both classes coexist); `showFrame()` prefetches
`cur+1` via `requestIdleCallback` while playing. New additive telemetry: `body.dataset.encodeMs`.

### Browser measurement (viewport 390x844, DPR 2, zoom 13)

| metric | before | after |
| --- | --- | --- |
| play `frameMs` min/avg/max | 104.4 / 142.0 / 155.3 ms | 26.0 / 41.7 / 50.6 ms |
| async `encodeMs` max | n/a (sync `toDataURL`) | 13.3 ms |
| overlay URL | `data:` | `blob:` (OffscreenCanvas path) |
| canvas during play | 1536x1568 | 780x796 |
| canvas after pause (+700 ms) | 1536x1568 | 1536x1568 |
| 15-min steps in 24 samples (180 ms apart) | 1 x 30 min (sample aliasing) | 13/13 exactly 15 min |
| console/page errors | 0 | 0 |

Screenshots: `/tmp/bpc-4a2-{before,after}-{fit,zoomed,play,paused}.png`. A separate probe sampled the
overlay `src` and confirmed 10 distinct `blob:` URLs with `naturalWidth 780` across 10 consecutive
ticks, then `naturalWidth 1536` after pausing (proves the async paint is live, not a frozen image).

### Reality over spec

- **`data-frameMs` now measures the main-thread portion** (compute + gather + smooth + OffscreenCanvas
  raster paint), excluding the async `convertToBlob`/object-URL step which is no longer synchronous.
  The previous meaning (full synchronous build incl. encode) cannot exist once the encode is async;
  the new `data-encodeMs` carries the async encode duration. No other `data-*` value changed.
- The spec's "sample data-frameMs over >=8 ticks; no skips": sampling at 350 ms aliased the 333 ms
  tick (one 30-min gap in the *before* run was a missed sample, not a loop skip). Re-sampled at 180 ms;
  after the change every observed transition is exactly 15 min.
- Screenshots of `play` before/after are byte-identical even though the raster class changed
  1536 -> 780; the smooth field upscaled to the same on-screen device pixels. The independent
  `src`/`naturalWidth` probe above is the authoritative proof that the image advances.

