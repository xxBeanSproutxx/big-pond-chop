# Stage 5G — The Scrolling Tape Architecture (render.js + index.html transport rebuild)

Work in THIS worktree only (branch `stage5g`). Do not touch /home/reid/projects/big-pond-chop (main checkout) or the sibling worktrees.

> **If any number in this spec conflicts with observed reality, trust reality and proceed; record the conflict in your report.**
> Follow the ponytail ruleset (laziest correct implementation). No test deletions; no weakened assertions — the assertion CHANGES listed under "Pre-authorised assertion changes" are this stage's documented contract change, nothing else.
> **Deploy is OUT OF SCOPE: do NOT push, do NOT tag, do NOT touch the remote.** The orchestrator runs the production step after your commit is verified.

## Why

5F made the deck *look* like Windy but the mechanics are still a static-width slider: the thumb travels across a ~326 px track that squishes all 672 frames into it (0.49 px/frame → unusable). Windy is the opposite: a **horizontal tape measure** with a **stationary centred reticle** — the tape scrolls, the needle never moves.

## Goal

Turn the timeline into a scrolling tape.

### 1. Fixed centre playhead reticle

- `#time-pill` is anchored at the **horizontal centre of the viewing window** (`#timeline`): `left: 50%; transform: translateX(-50%)`, plus its downward stem at that same x.
- It **never moves horizontally** — not during drag, not during playback, not on resize. It is not written to in any JS position path; the only thing that changes is its **text** (the active frame's timestamp, `h AM` / `h:mm AM` format as today) and the tape underneath it.
- Keep the 5F look: 68 × 20 amber badge floating just above the deck edge, stem dipping into the bar.

### 2. Wide scrolling filmstrip tape

- New container `<div id="track-tape">` **inside `#timeline`**, `position:absolute; left:0; top:0; height:100%`, holding the day blocks, the 3-hour sub-labels **and** the NOW hairline. `#now-tick` moves inside it and is positioned at the exact pixel of the current local time (`nowIdx * pxPerFrame`), so it scrolls in and out of view naturally.
- `#timeline` becomes the **viewing window**: `overflow: hidden`, full width of the track row (the play button no longer reserves layout space, see §4).
- **Density — export a helper** `pxPerDay(horizon, windowW)`:
  - `horizon === '7d'` → **190 px per day** (672 frames → tape **1,330 px**, inside the 1,100–1,400 px target);
  - `horizon === '24h'` → `Math.max(190, Math.round(windowW))` (a single day always at least fills the window, so the tape can actually scroll);
  - `pxPerFrame = pxPerDay / 96` (≈1.98 px in 7 d, ≈3.4–3.9 px in 24 h at phone widths). Do NOT derive it from `frames.length / 96` — day blocks are date-string derived (5D contract); size each block from its own frame run: `width = frameCount * pxPerFrame`.
- Day blocks keep the 5F visual language (alternating `#262930` / `#1e2025`, 1 px `#3a3f4a` midnight divider, bold centred day header, sub-row) but now at real width: at 190 px/day the 3-hour spacing is ~23.8 px, so **every day shows the full `12 03 06 09 12 03 06 09` sub-row in both horizons** — the 5F thinning / `.narrow` / `.solo` degradation paths become dead code and must be deleted, not kept.
- The tape is not a slider trough: no rounded rail, no progress fill.

### 3. Tape transform math (single source of truth)

One function writes the tape position, and only one:

```js
trackTape.style.transform =
  'translateX(' + (viewportCenterPx - activeFrameIdx * pxPerFrame) + 'px)';
```

where `viewportCenterPx = window.innerWidth`-independent **window width / 2** (`#timeline.getBoundingClientRect().width / 2`). Export the pure helpers so the Node suite can test them:

- `pxPerDay(horizon, windowW)` → px
- `pxPerFrame(horizon, windowW)` → `pxPerDay / 96`
- `tapeTranslate(idx, pxPerFrame, viewportCenterPx)` → number
- `idxFromDrag(dxPx, startIdx, pxPerFrame, n)` → `clamp(round(startIdx - dxPx / pxPerFrame), 0, n - 1)`

The frame under the reticle **is** the active frame: `cur` (the frame the map, verdict and readout already render). No parallel index.

### 4. Pointer drag, playback, transport

- Keep full-deck pointer capture on `#deck` (`setPointerCapture`), the `e.target.closest('button, [role=button], a, input')` guard, rAF coalescing for pointermove, and the "never auto-resume after capture" rule.
- `pointerdown`: record `startX = e.clientX`, `startIdx = cur`; `pointermove`: `requestFrame(idxFromDrag(e.clientX - startX, startIdx, pxPerFrame, n))` — **dragging LEFT advances forward in time** (future frames scroll under the reticle), **dragging RIGHT rewinds**.
- Playback: keep the existing interval cadence (`playStep(horizon)` frames per tick) and the tape translates left underneath. While playing, give the tape a short linear `transform` transition (~min(320 ms, cadence)) so it glides; while dragging, set transition to `none`; disabled entirely under `body.reduced-motion`.
- `#play` is **pinned to the far-left edge, stationary, `z-index: 10`**, overlaying the tape window (it no longer takes flex space): borderless icon-only ▶/⏸, 48×48 hit area, same `aria-pressed` + `data-state` contract, and the existing "clicks on the play button must not scrub" behaviour. If the white glyph is hard to read over passing tape text, add a subtle dark scrim behind it — nothing more.
- Keep everything else that works today: keyboard seek (`ArrowLeft` −1, `ArrowRight` +1, `PageUp` +4, `PageDown` −4, `Home` 0, `End` n−1), `#track` `role="slider"` + `aria-valuemin/max/now/valuetext`, the `?hour=` / `?frame=` boot overrides, prefetch, `playStep`/`nextPlayIdx` wrap, resize re-placement.

## Files allowed to touch

`index.html`, `src/render.js`, `tests/render.test.js`, `tools/qa/stage5_check.py`, `docs/STAGE-5G-RECEIPTS.md` (new).

## Out of scope

`src/wave-math.js`, `src/wind.js`, `src/tables.js`, `public/*`, the physics engine, the LRU cache, the vector-blending pipeline, the tap card, the header, the OG image, deploy/push/tag, and `src/ui.js` unless a formatter string must change (say so in the report if it does).

Do not change: `ui.rampGradient()`'s six stops, `#ramp-ticks`, the `#boot` overlay contract, tier logic, verdict text, `dayPartitions()`, or any engine test.

## Pre-authorised assertion changes (the ONLY permitted test edits)

1. **`tests/render.test.js` id list**: add `track-tape`; keep `play, track, timeline, track-days, track-ticks, track-label, now-tick, time-pill, h-24h, h-7d, ramp-bar, ramp-ticks`; keep the absence asserts.
2. **`tests/render.test.js` helper tests**: delete the `clampPillX` test (that helper is gone — the pill is fixed) and the position→index `idxFromX` test; replace with tests for the new pure helpers: `pxPerDay('7d', 374) === 190`; `pxPerDay('24h', 374) === 374`; `pxPerFrame('7d', 374) === 190/96`; `idxFromDrag` monotonic + clamped at both ends + `dx = -pxPerFrame × k` moves +k frames; and the reticle identity — for any `idx`, `tapeTranslate(idx, pxPerFrame, center) + idx * pxPerFrame === center`.
3. **`tools/qa/stage5_check.py` `[7b]` becomes the tape test** (keep the group number and name `touch ergonomics`):
   - press inside `#timeline`, drag **left** by ≈ −120 px: index advances by ≈ `120 / pxPerFrame` (±1); the **pill's centre x is unchanged within 0.5 px**; the tape's own left edge moved by ≈ −120 px (within 3 px, allowing for the clamp);
   - drag **right** by ≈ +60 px: index rewinds by ≈ `60 / pxPerFrame` (±1);
   - clamp: drag far left (to the window's left edge minus 2×width) → index `n−1`; drag far right → index `0`, with the pill still centred;
   - the play-button click still does not scrub; a drag starting inside the `.deck-ramp` row still scrubs (deck-wide capture);
   - keep pressing/releasing through real `page.mouse.down/move/up`.
4. **`tools/qa/stage5_check.py` NEW group `[16] tape architecture (5G)`** — assert on the 390×844 page:
   - `#time-pill` centre x within **1 px** of `#timeline` centre x (and again after a scrub and after the 7-day widen);
   - `#track-tape` exists, is a child of `#timeline`, and `#now-tick` is a child of `#track-tape`;
   - 24 h: tape width ≥ `#timeline` width − 2 px; 7 d: tape width in **1,100–1,400 px**;
   - the active frame's centre (tape left + `cur * pxPerFrame`) is within **1 px** of the reticle centre;
   - `#play` rect is stationary over the window's left edge (inside the track's first 56 px) and has `z-index ≥ 10`;
   - day blocks: ≥ 1 in 24 h, 7 in 7 d, alternating background colours, and every block in the 7-day view contains 8 sub-labels.
   Print the measured numbers (tape width, px/frame, pill centre, frame centre, transform) in the detail line.
5. **`tools/qa/stage5_check.py` screenshots**: keep `24h.png`, `7d.png`, `scrub.png`, `24h-360.png`; add **`tape-7d.png`** captured after a mid-tape scrub in 7-day mode (so the sheet shows the tape scrolled with the reticle centred).
6. `[15] deck geometry (5F)` keeps its checks, but its pill assertions become: pill **centred** in `#timeline` and visible, instead of "pill inside the timeline rect".

## Done when

1. `tools/qa/stage5_check.py` prints **`SUMMARY: N ok, 0 FAIL` with N ≥ 22** (20 previous groups + `[15]` + `[16]`), verbatim into `docs/STAGE-5G-RECEIPTS.md`.
2. All four Node suites pass (`parity`, `wind`, `render`, `ui`) — no test deleted, nothing weakened outside the six items above.
3. Screenshots written to `tmp/s5g-shots/`: `24h.png`, `7d.png`, `scrub.png`, `24h-360.png`, `tape-7d.png`.
4. `docs/STAGE-5G-RECEIPTS.md`: verbatim harness output, four suite tails, the tape numbers (pxPerDay, pxPerFrame, tape width per horizon, pill centre vs window centre, transform values before/after drags), a table of every test/assertion changed with a one-line justification, screenshot paths, and any spec-vs-reality conflicts.
5. One commit on `stage5g`, message `Stage 5G: scrolling tape transport (fixed centre reticle, px/day tape, drag = scroll)`.
   Report: files changed, `git diff --stat`, the harness summary line, the tape numbers, and any conflict between this spec and observed reality.
