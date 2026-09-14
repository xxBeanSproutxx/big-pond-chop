# 6.2 — UI POLISH PASS (de-cluttered header · docked corners · continuous scrub) — RECEIPTS

Scope (Reid's pass spec, 2026-09-14): ship the application with three targeted refinements —
(1) header de-clutter + unit consolidation, (2) map-corner balancing (zoom stack to the
bottom-right), (3) smooth continuous minute scrubbing. Then: run the suites and group [19],
commit, tag as production, push to GitHub Pages.

Repo `/home/reid/projects/big-pond-chop`. Baseline `2d11a8b` (stage-6.1-docked, LIVE).

---

## 1. What shipped

### 1a. Header de-clutter + unit consolidation (`index.html`, `src/render.js`)
- **Deleted**: `#pill-shore`, the `#arrow` SVG, the `#help` micro-badge, and `#help-pop`
  with **every listener** (`setHelpOpen`, the Escape handler, the outside-click handler, the
  popover copy). Row 3 is now two badges; `#refresh` is the only control left in the band.
- **Row 3** = `[17 mph] · [24 mph Gust]`:
  `#three > [#pill-lake(#lake, #mph.unit)] · [#dot] · [#pill-gust(#gust, .unit, #gust-u)]`.
  Both badges carry their own unit, literally as specified.
- The speed badge still inherits the **WIND_HEAT tier tint** (`--tint` / `--tint-bd` from
  `ui.windPills`), and now carries an `aria-label` (`Lake wind 17 mph`) because the visible
  "Lake" word is gone — the badge is number+unit only.
- `#mph` (the lake badge's unit) is **white** (`#f8fafc`): it sits on the .55-alpha tier tint
  where `#cbd5e1` measured 3.58:1 on the amber tier. The gust badge's unit keeps `#cbd5e1`
  (8.64:1 on the neutral fill).
- The shore series is **still ingested** (one batched dual-location request, unchanged) and
  kept in memory — it is simply not displayed. That keeps the 6A data path and its tests intact.

### 1b. Map-corner balancing (`index.html`)
- Zoom stack moved from top-left to **bottom-right**: `.leaflet-top.leaflet-left` is
  re-anchored `top:auto; bottom:20px; left:auto; right:6px`, with Leaflet's inherited
  10 px control margins neutralised (`.leaflet-top.leaflet-left .leaflet-control { margin: 0 }`).
- `#horizon` (24 h | 7 day) now **owns the top-left corner** at `left: 12px`, mirroring
  `#wind-badge`'s `right: 12px` on the opposite corner.

### 1c. Continuous minute scrubbing (`src/ui.js`, `src/render.js`)
- New pure helpers: `pxPerMinute`, `minutesFromDrag` (raw pixel delta → **continuous**
  minutes, clamped), `tapeTranslateMinutes` (continuous translate, same reticle identity as
  `tapeTranslate`) and `idxFromMinutes` (`Math.round(minutes / step)`, clamped to the array).
- **Drag path**: `pointermove` → `scrubUiToMinutes()` → the tape translate and the pill clock
  both run on raw pixel deltas; the canvas still queries the existing **96-frame array** via
  `Math.round(activeMinutes / 15)` — no dummy frames are generated.
- **`#time-pill`** shows true minute-level timestamps (`7:04 AM`, `7:09 AM`, `7:14 AM`) via the
  new `ui.formatPillTimeAt(isoLocal, addMinutes)`, which applies the offset to the resolved
  INSTANT (DST-safe, formatter memoised) and always prints minutes. `tabular-nums` retained.
- **Throttle unchanged**: `MAP_PAINT_MIN_MS = 72` (~13.9 fps) during the drag, newest-index-wins,
  and `endScrub()` still snaps to the exact quantised frame with the .32 s glide restored —
  the tape now *glides* from wherever the finger left it instead of teleporting.
- `updateScrubUi(idx)` (frame-snapped) still owns playback/programmatic updates.

---

## 2. Deviations from the pass spec (with the reason each)

1. **`bottom: calc(var(--deck-h) + 26px)` → `bottom: 20px`.** Leaflet's corner containers are
   children of `#map`, whose bottom edge IS the deck's top, so a `--deck-h` term double-counts
   the deck and would float the stack 88 px up the map. This is the same viewport-vs-map mix-up
   fixed in 6.1 for the attribution (`.leaflet-bottom`). Measured result: zoom sits **20.00 px**
   above the map bottom, **3.41 px** above the 9 px attribution, right edges aligned (0.00 px).
2. **`#horizon` `left: 56px → 12px`.** The 56 px existed only to clear the (now removed)
   top-left zoom control; with the corner freed, 12 px mirrors the wind badge.
3. **`#three` `margin-right: 32px → 0`.** Those 32 px reserved space for the deleted `?`
   micro-badge and its `::after` touch target.
4. **Group [19], `live_smoke.py` and two node suites were updated.** They asserted the 6B
   three-pill markup (`#pill-shore`, `#arrow`, `#help`, `#help-pop`, `#lake-u`, the popover
   plumbing). Keeping the *layout* contracts green (72 px ceiling, ink ≤ available, contrast
   ≥ 4.5:1, no clipping) required re-pointing those assertions at the two-badge row — the
   removed-element assertions are now the inverse (a leftover id FAILS).
5. **The row carries "mph" on BOTH badges** (`17 mph · 24 mph Gust`) because that is what the
   pass spec wrote. If the repetition reads heavy on the phone, dropping the gust badge's unit
   is a one-line change (`#pill-gust .unit`) — flagged, not changed.

---

## 3. Measurements (group [19], 6.2 gates, 360×800 + 390×844 × normal/wide/calm)

| contract | measured |
| --- | --- |
| header ceiling | **72.00 px**, `scrollHeight == clientHeight` in all 6 blocks |
| row fit | `#three` scrollW == clientW (284 @360 / 314 @390); ink **137.64 px** (slack 146.36 / 176.36); widest `wide` state also fits |
| row shape | `['pill-lake','dot','pill-gust']`; lake `['lake','mph']`; gust `['gust','unit','gust-u']`; **dead ids = []** |
| typography | numerals 13px/700/tabular; both units + `#gust-u` 10px/500; lake unit `rgb(248,250,252)`, gust unit `rgb(203,213,225)` |
| contrast (min per state) | **5.11:1** (amber tint, normal) · 6.81:1 (wide) · 7.22:1 (calm) — all ≥ 4.5:1 |
| corner balance | horizon `left=12 top=12`; wind badge `right=12 top=12`; zoom `right-vs-attribution=0.00 px`, `gap-to-attribution=3.41 px`, `above-map-bottom=20.00 px`, bottom half, inside map |
| zoom overlaps | attrib / legend / badge / horizon / pill / card = **none** |
| minute pill | `12:59 PM` ink 68 px = pill width 68 px (fits); `font-variant-numeric: tabular-nums` |
| jitter | max lake-badge Δ **0.00 px**, max gust-badge Δ **0.00 px**, row never crosses `#refresh` (24 frames) |
| continuous scrub | 12 px drag @24 h = 31.4 min → pill `12:08 → 12:16 → 12:24 → 12:31 AM` (**1.4 min off** the 15-min grid); tape follows the raw pixel delta to **0.00 min**; aria idx = `round(min/15)` = 2 = expected |
| settle on release | tape rests exactly on frame 2 (**30.00 min**), pill returns to the compact snapped form `12:30 AM`, 0 new console errors |
| drag perf (group 17) | overlay src swaps **10 ≤ 12**, in-drag long tasks **0 ms ≤ 50 ms**, tape transform writes 31 ≥ 31 delivered moves |
| node suites | parity / wind / render / ui — **4/4 exit 0** |
| playback (group 9) | unchanged: ticks 10, encode ≈ 6.3 ms, canvas 780 during play → 1536 paused |
| smoothing / bleed (10, 10.1) | unchanged (fit 0.456, z13 1.408, z14 2.817; land alpha 0) |
| lazy 7d (13) | unchanged (idle delta 0.0 ms) |

### One pre-existing, data-dependent gate
`[14] live seam` FAILED in this run: `dSpeed=5.00 dDir=13.00` at the +48 h handoff. That gate
runs `node tools/qa/seam_check.js` against the **live API** and reads no app code, so it is
independent of this pass — it is the long-standing "gate vs ramp" item (it passed on 09-13/14
with `dSpeed=0.60`). Not a regression; recorded so the number is not mistaken for one.

### `[17] scrub decoupling` — pre-existing flake, measured against the baseline

`[17]`'s in-drag long-task ceiling is `≤ 50 ms` and it is intermittent on **both** trees. Same
instrument (`tools/qa/scrub_bench.py`), same box, run back-to-back in the same session:

| tree | drag swaps | drag `longMax` (ms) | drag latency median |
| --- | --- | --- | --- |
| baseline `2d11a8b` (pre-6.2), n=4 | 10, 10, 10, 10 | 0, **54**, **54**, 0 | 16.67 / 16.48 / 16.15 / 16.27 |
| 6.2, n=4 | 10, 10, 10, 10 | 0, **51**, 50, 0 | 16.47 / 16.65 / 16.43 / 16.75 |

The ~50-54 ms outlier fires on the unmodified tree as often as on this one, and the median
step latency and the swap count are unchanged (10 in every run). It is the known residual
synchronous raster build at drag-start (`5H.1`, recorded since 5H as "little headroom under
contention"). No part of the drag path this pass touched builds raster data — the continuous
step is one string + one style write per rAF, and it *reuses* one `Intl.DateTimeFormat` where
the snapped path constructed a new one per frame.
**Recorded, not papered over: a contended full-harness run can FAIL `[17]` on either tree.**

### Harness hardening made during this pass (not an app defect)
The new `[19.11]` gate first sampled the tape **mid-glide** after a viewport change: the rAF
that consumes the `Home` keypress can be delayed behind a resize-triggered re-encode. The gate
now waits for `aria-valuenow == '0'` **and** for the transform to rest at the timeline centre
before sampling. Verified in isolation that the app itself is fine at 360 (fresh load and after
a 390→360 resize: `idx=0`, `tx=172.00`).

## 5. Full-harness summary as run

```
SUMMARY: 23 ok, 2 FAIL
  FAIL [17] scrub decoupling (5H)   <- pre-existing intermittent long-task gate (§4)
  FAIL [14] live seam               <- live-API data-dependent gate (§4)
[19] 6.2 polish pass  ok  all gates ok=True   <- both viewports, all six layout blocks
```

`[19]` gates as emitted: 19.1 header 72.00 px · 19.2 row fit + units ≥17 px · 19.3 ink ≤ avail ·
19.4 row shape + zero dead ids · 19.5 typography · 19.6 contrast min 5.11:1 · 19.7 jitter 0.00 px ·
19.8 one dual-location request · 19.9 badge values == API values · 19.10 corners + zoom dock ·
19.11 continuous minute scrub + settle · 19.12 glass/overlay clearance.

## 6. Ship receipt

- Committed on `main`: **`1a86de0`** — "6.2: header de-clutter (two badges), zoom docked
  bottom-right, continuous minute scrubbing"; tag **`stage-6.2-polish`**; `origin/main == 1a86de0`.
- GitHub Pages build for `1a86de0`: **built** (2026-09-14 12:49Z).
- Deployed-byte probe (`curl` of the live `index.html`, 25,790 B): carries `id="pill-lake"`,
  `id="pill-gust"`, `<span class="unit">mph</span>`, the new `.leaflet-top.leaflet-left { top:
  auto; bottom: 20px … }` rule and `left: 12px;` on `#horizon`; carries **zero** `id="pill-shore"`
  / `id="arrow"` / `id="help"` / `id="help-pop"` elements (the only `help-pop` string left in the
  served file is the CSS comment that says it is gone).
- **`live_smoke.py` against production: 16 ok / 0 FAIL** — including `6.2 row live` (dead ids
  none, pill `tabular-nums`), `6.2 row in bytes`, `6.2 zoom docked BR` (right-vs-attribution 0,
  gap 3.41 px, bottom half), `6.2 horizon top-left` (12.00 px), 7-day horizon 7 blocks / 2,310 px,
  and `no page errors`.
- Follow-up: `live_smoke.py`'s deployed-bytes probe now matches `id="help-pop"` / `id="pill-shore"`
  (element ids) instead of the bare strings, so a comment that *names* a deleted id can no longer
  masquerade as a leftover element.
- Rollback: `git revert 1a86de0` or reset to `2d11a8b` (tag `stage-6.1-docked`); `stage-6-live`
  (`f3e415f`) also remains.

---

## 4. Files changed

```
index.html                    row 3 markup + CSS (two badges, .unit, #pill-lake .unit),
                              #help/#help-pop CSS + markup deleted, #horizon left 12px,
                              zoom corner re-anchored, comments updated
src/ui.js                     + formatPillTimeAt (minute-level, DST-safe, memoised formatter)
src/render.js                 + pxPerMinute/minutesFromDrag/tapeTranslateMinutes/idxFromMinutes,
                              applyTapeTransform split, writeTapeMinutes, scrubUiToMinutes,
                              updateScrubUiMinutes, continuous pointermove path, shore/help
                              DOM refs + popover listeners removed, lake badge aria-label
tests/render.test.js          [14] re-pointed at the two-badge contract, [15] new continuous
                              scrub geometry tests
tests/ui.test.js              [9b] new formatPillTimeAt tests (rollover + DST fall-back)
tools/qa/stage5_check.py      group [19] rewritten: two badges, docked corners, continuous
                              scrub, dead-id probe, new contrast pairs
tools/qa/live_smoke.py        deployed-bytes checks re-pointed at the 6.2 chrome
docs/STAGE-6.2-RECEIPTS.md    this file
```

Re-run: `node tests/*.test.js` · `/home/reid/.hermes/hermes-agent/venv/bin/python
tools/qa/stage5_check.py` (group [19] = "6.2 polish pass") ·
`/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/live_smoke.py --url <deployed>`.

Rollback: `git revert -m 1 <merge>` or `git reset --hard <pre-6.2 tag>`; tags
`stage-6-live` (`f3e415f`) and `stage-6.1-docked` (`2d11a8b`) both remain.
