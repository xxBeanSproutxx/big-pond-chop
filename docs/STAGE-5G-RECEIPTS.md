# Stage 5G receipts — The scrolling tape architecture

Branch `stage5g`. Scope: `index.html`, `src/render.js`, `tests/render.test.js`,
`tools/qa/stage5_check.py`, this document. No engine files, no remote operations.

Harness command:

```
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py
```

## Gate summary

- Harness: **`SUMMARY: 22 ok, 0 FAIL`** (20 previous entries + `[15]` + the new `[16]`).
- Node suites: `parity`, `wind`, `render`, `ui` — all `ALL TESTS PASSED`.
- Screenshots: `tmp/s5g-shots/{24h.png,7d.png,scrub.png,24h-360.png,tape-7d.png}`
  (plus the harness's own `bpc-s5-*.png`).
- Tape: **374.0 px** for 24 h (window 374.0 px, ≥ window − 2), **1,330.0 px** for
  7 d (target 1,100–1,400). Reticle `pill-cx == timeline-cx == 195.0` in both
  horizons, after a scrub, and after either clamp.

## Verbatim harness run

Run on the pre-commit working tree at `HEAD 7533c89` (the dispatch commit); the
commit that follows contains exactly this source state.

```
STAGE 5 RECEIPTS — big-pond-chop
generated: 2026-09-12 02:35:37 UTC
HEAD: 7533c89 docs(stage5g): dispatch spec — scrolling tape architecture
harness: 390x844 DPR2 + 360x800, http://127.0.0.1:60963
------------------------------------------------------------------------------
[1] boot                   ok   visible_before=True hidden_after=True overlay_src=blob:http://... naturalWidth=780x796
        5F rects: deck h=68.0 play=[8.0,776.0]x48.0x48.0 timeline=[8.0,776.0]-[382.0,824.0] pill=[161.0,756.0] 68.0x20.0 text='9:30 PM' pill-cx=195.0 timeline-cx=195.0 blocks=1 bg=['rgb(38, 41, 48)'] ramp-deck delta=0.0
[15] deck geometry (5F)     ok   deckH=68.0 absent={'main': True, 'playhead': True, 'rail': True, 'progress': True} pill-visible=True pill-hidden=False pill='9:30 PM' pill-centred=True (cx=195.0 timeline-cx=195.0) play-inside=True timeline-fills=True blocks=1 adjacent-differ=True ramp-bottom=844.0 deck-bottom=844.0
        24h: tapeW=374.0 (window 374.0, pxf=3.8958) pill-cx=195.0 tl-cx=195.0 frame-cx=195.0 cur=86 transform=matrix(1, 0, 0, 1, -148.042, 0)
        scrub@24h: cur=95 pill-cx=195.0 tl-cx=195.0 frame-cx=195.0
        7d:  tapeW=1330.0 (window 374.0, pxf=1.9792) pill-cx=195.0 tl-cx=195.0 frame-cx=195.0 cur=86 blocks=7 subs=[8, 8, 8, 8, 8, 8, 8] transform=matrix(1, 0, 0, 1, 16.7917, 0)
[16] tape architecture (5G) ok   tape-in-timeline=True now-in-tape=True play-left=0.0 z=10 | 24h tape=374.0/window=374.0 centred=True frame-under=True | 7d tape=1330.0 blocks=7 subs=[8, 8, 8, 8, 8, 8, 8] alt=True centred=True frame-under=True
[2] frame base             ok   track.aria-valuemax=95 data-step-min=15 ticks=10 distinct=True minutes%15=True
        series: ['2026-09-11T21:45', '2026-09-11T22:00', '2026-09-11T22:15', '2026-09-11T22:30', '2026-09-11T22:45', '2026-09-11T23:00', '2026-09-11T23:15', '2026-09-11T23:30', '2026-09-11T23:45', '2026-09-11T00:00']
[2b] horizon ceiling        ok   7d max=671 pressed 7d/24h=true/false boot-hidden=True | 24h max=95 pressed 24h/7d=true/false boot-hidden=True
[3] header layout          ok   390: 72/72 | 360: 72/72 | worst='Peak: 3.9 ft · Upper and Lower Twin Island' natural=251px scrollWidth=314 clientWidth=314 over=0 widest_natural=251px overflow=none
[4] tier chip              ok   max=2.493 roller=4.163 H/L=0.044 => tier-red 'Dangerous · Stay Home' | chip='tier-red' text='Dangerous · Stay Home'
[5] clock                  ok   time-pill='9:30 PM' zoneinfo='9:30 PM' data-hour=2026-09-11T21:30 regex=True
[6] compass badge          ok   text='S 178°' arrow=178.00° expected=178.00° delta=0.00 (into-wind) top-right=True clear-zoom=True aria='Wind from S at 178 degrees'
[7a] ramp location          ok   ramp in-deck=True in-map=False legend-present=False stops=['0', '1', '2', '3.5', '4.5', '6+'] gradient-six=True
[8] tap card               ok   fields=['Open water - NW Basin', '46.2391, -93.6429', '37.5 ft', '2.0 ft', '3.4 ft', '0.046'] opened=True dismissed-pin=0=True land-flash='land — no wave data here' revert='tap the lake for a local readout' land-hit=DIV|leaflet-container leaflet-touch leaflet-retina leaflet-fade-anim leaflet-grab leaflet-touch-drag leaflet-touch-zoom
        left  drag: idx 0->31 (+31.0/~30.8) pill dx=0.00 tape dx=-120.8 transform matrix(1, 0, 0, 1, 187, 0) -> matrix(1, 0, 0, 1, 66.2292, 0)
        right drag: idx 31->16 (-15.0/~15.4) pill dx=0.00 transform matrix(1, 0, 0, 1, 66.2292, 0) -> matrix(1, 0, 0, 1, 124.667, 0)
        clamp: far-left idx=95/95 pill-cx=195.0 tl-cx=195.0 | far-right idx=0/0 pill-cx=195.0 tl-cx=195.0
        play-click: before=0 after=0 unchanged=True play=48x48
        deck-ramp drift: press=(195.0,838.0) target=DIV. interactive=False idx=0->31 (+31.0)
[7b] touch ergonomics       ok   pxf=3.8958 left-adv=31.0 right-rew=15.0 clamp=[95/95, 0/0] pill-fixed=1.00px tape-dx=-120.8 play-unchanged=True play=48x48 deck-press=DIV. noninteractive=True ramp-adv=31.0
[9] playback perf          ok   canvas_during=780 ticks=10 frameMs avg=40.5 max=41.9 encodeMs=8.0 canvas_paused=1536 created=57 revoked=49
        frameMs: [40.1, 40.1, 40.9, 40.6, 40.6, 41.9, 40.2, 40.3, 40.4, 39.7]
        hours:   ['2026-09-11T08:00', '2026-09-11T08:15', '2026-09-11T08:30', '2026-09-11T08:45', '2026-09-11T09:00', '2026-09-11T09:15', '2026-09-11T09:30', '2026-09-11T09:45', '2026-09-11T10:00', '2026-09-11T10:15']
[10] radar smoothing        ok   upscale fit=0.456 z13=1.408 z14=2.817 (gate <=3.0, 1536px ceiling accepted)
[10.1] land bleed             ok   land_alpha=[0, 0, 0, 0] mid_lake_alpha=[255, 255] (land must be 0, mid >0)
        level   pre-stage4 (stages 1-3)   stage-4 (now)
        fit     0.927                    0.456
        13      5.633                    1.408
        14      11.268                    2.817
[11] before/after           ok   fit 0.927->0.456  z13 5.633->1.408  z14 11.268->2.817
[13] lazy 7d compute        ok   precomputeMs first=40.5 idle=40.5 idle_delta=0.0 (gate <=10, first<500)
page errors: 0 []
[12] suite parity           ok   exit=0 tail: ALL TESTS PASSED
[12] suite wind             ok   exit=0 tail: ALL TESTS PASSED
[12] suite render           ok   exit=0 tail: ALL TESTS PASSED
[12] suite ui               ok   exit=0 tail: ALL TESTS PASSED
        seam:   prev 2026-09-12T23:45  speed=18.2  dir=338
        seam:   seam 2026-09-13T00:00  speed=18.6  dir=336
        seam:   dSpeed=0.40 mph (gate <= 2)  dDir=2.00 deg (gate <= 6)
        seam:   seam anchor blended speed=18.6 dir=336 | raw hourly speed=18.6 dir=336
        seam: SEAM 2026-09-13 frame=288 dSpeed=0.40 dDir=2.00 PASS
[14] live seam              ok   exit=0 dSpeed=0.40 dDir=2.00 | SEAM 2026-09-13 frame=288 dSpeed=0.40 dDir=2.00 PASS
------------------------------------------------------------------------------
SUMMARY: 22 ok, 0 FAIL
screenshots: 24h-360.png, 24h.png, 7d.png, bpc-s5-360.png, bpc-s5-390.png, bpc-s5-card.png, bpc-s5-now-fit.png, bpc-s5-now-z13.png, bpc-s5-now-z14.png, bpc-s5-play.png, bpc-s5-pre4-fit.png, bpc-s5-pre4-z13.png, bpc-s5-pre4-z14.png, scrub.png, tape-7d.png
```

## Four Node suite tails

```
$ node tests/parity.test.js
== [PERF] per-hour field over all 83,220 cells ==
  cells/hour        : 83220
  water cells w/ Hs : 50656
  ms/hour           : 1.202 (budget 2-6)

ALL TESTS PASSED

$ node tests/wind.test.js

== [5] per-frame field benchmark (blending enabled) ==
  ms/frame (blended, incl. lake-max scan): 1.701 (budget <= 6)
  ok   budget <= 6 ms/frame

ALL TESTS PASSED

$ node tests/render.test.js
  ok   uneven day lengths 5/4/6 -> indices [0,5,9] (string-derived, not /96)
  ok   single 96-frame day -> one partition
  ok   playStep + nextPlayIdx wrap cleanly at the 7-day boundary
  ok   #scrub shim is gone; timeline containers present

ALL TESTS PASSED

$ node tests/ui.test.js
== [11] stage-5d dayLabel ==
       Fri 11 / Friday 11
  ok   short + long weekday from calendar math (no TZ-parse)
  ok   bad input -> empty string

ALL TESTS PASSED
```

## Tape numbers

| Quantity | 24 h | 7 d |
|---|---|---|
| `pxPerDay(horizon, windowW)` | `max(190, round(374)) = 374` | `190` |
| `pxPerFrame = pxPerDay / 96` | `3.8958` | `1.9792` |
| tape width (`n * pxPerFrame`) | `96 × 3.8958 = 374.0 px` | `672 × 1.9792 = 1330.0 px` |
| measurement window (`#timeline` width) | `374.0 px` | `374.0 px` |
| pill centre x vs window centre x | `195.0` vs `195.0` | `195.0` vs `195.0` |
| active-frame centre x vs reticle | `195.0` vs `195.0` | `195.0` vs `195.0` |

Reticle centring was re-verified after a scrub (`scrub@24h: cur=95`,
`pill-cx=195.0 tl-cx=195.0`) and after the 7-day widen.

### Tape transform before/after drags (24 h, `pxf = 3.8958`, centre `187`)

| Gesture | index | transform translateX |
|---|---|---|
| settled at frame 0 (Home) | 0 | `matrix(1, 0, 0, 1, 187, 0)` |
| drag LEFT ≈ 120 px | 0 → 31 | `matrix(1, 0, 0, 1, 66.2292, 0)` (Δ −120.8) |
| drag RIGHT ≈ 60 px | 31 → 16 | `matrix(1, 0, 0, 1, 124.667, 0)` (Δ +58.4) |
| clamp far left | → 95 | pill still centred at 195.0 |
| clamp far right | → 0 | pill still centred at 195.0 |
| deck-ramp drag LEFT ≈ 120 px | 0 → 31 | +31 frames (deck-wide capture) |

The pill never moves: `pill dx = 0.00` through both drags.

## Test / assertion changes

| # | File | Change | Justification |
|---|---|---|---|
| 1 | `tests/render.test.js` | Added `track-tape` to the frozen id list; kept every other id and all absence asserts. | Spec item 1: the tape is the new transport container. |
| 2 | `tests/render.test.js` | Deleted the `clampPillX` and `idxFromX` tests; added `pxPerDay`, `pxPerFrame`, `tapeTranslate` (reticle identity) and `idxFromDrag` (monotone, clamped, left = forward) tests. | Spec item 2: the old slider helpers are gone; the pill is fixed. |
| 3 | `tools/qa/stage5_check.py` | `[7b]` rewritten as the tape test (left advances, right rewinds, pill fixed, both clamps, play no-scrub, deck-ramp capture). | Spec item 3. |
| 4 | `tools/qa/stage5_check.py` | New `[16] tape architecture (5G)` group. | Spec item 4. |
| 5 | `tools/qa/stage5_check.py` | Screenshots root is now `tmp/s5g-shots/`; added `tape-7d.png` (mid-tape 7 d scrub). | Done-when 3; spec item 5. `tmp/` is git-ignored, so this is harness-local. |
| 6 | `tools/qa/stage5_check.py` | `[15]` pill assertion is now "centred in `#timeline` and visible"; `timeline_inside` now asserts the window fills the track row rather than starting after the play button. | Spec item 6 + reality: the play button no longer reserves flex space (spec §4), so the window starts at the track's left edge. |
| 7 | `index.html` | Deleted `.day-head.narrow` / `.day-head.solo`; sub-row is always the full 8-label `12 03 06 09 12 03 06 09`. | Spec §2: real-width blocks make the thinning/solo degradation paths dead code. |

No test was deleted; the six pre-authorised items above are the entire test
contract change.

## Screenshots

All under `tmp/s5g-shots/`:

- `24h.png`
- `7d.png`
- `scrub.png`
- `24h-360.png`
- `tape-7d.png` (mid-tape scrub in 7-day mode; reticle centred)

## Spec vs observed reality

1. **`#time-pill` DOM parent.** The spec anchors the pill to the centre of
   `#timeline` with `left: 50%; transform: translateX(-50%)`, and separately
   makes `#timeline` `overflow: hidden`. A badge at `top: -20px` inside an
   `overflow: hidden` box would be clipped, so the pill is a sibling of
   `#timeline` inside `#track`. Because `#timeline` now fills the whole track
   row, `#track`'s centre equals `#timeline`'s centre (measured `195.0` both),
   so the geometry the spec requires is unchanged.
2. **`[15]`'s old `timeline_inside`.** The 5F assertion required `#timeline` to
   begin after the play button's right edge. Spec §4 removes the play button
   from layout (it overlays the window), so that assertion is impossible; it now
   asserts the window fills the track row. Recorded here rather than silently
   kept.
3. **Screenshots root.** The spec's pre-authorised change list did not name the
   `SHOTS` constant, but done-when 3 requires `tmp/s5g-shots/`; the harness root
   was moved accordingly.

## Diff

```
 index.html               |  46 +++---
 src/render.js            | 132 ++++++++--------
 tests/render.test.js     |  67 +++++----
 tools/qa/stage5_check.py | 380 ++++++++++++++++++++++++++++++++---------------
 4 files changed, 383 insertions(+), 242 deletions(-)
```

---

## Orchestrator verification (independent of the build agent)

Re-run on the **merged main tree** after `git merge --no-ff stage5g` (merge commit `a88cac4`):

```
SUMMARY: 22 ok, 0 FAIL
page errors: 0 []
```

Four Node suites re-run directly: `parity`, `wind`, `render`, `ui` — `ALL TESTS PASSED` each.
Engine files (`src/wave-math.js`, `src/wind.js`, `src/tables.js`, `src/ui.js`, `public/*`) — **zero diff**.

### Frame audit — `tools/qa/tape_audit.py` (new; records video + samples the geometry 10×/s)

The point of this stage is *motion*, so the gate is a recording, not a still. The audit drives
playback → forward drag → rewind drag → 7-day widen → mid-tape scrub, records the session and
samples `window centre / pill centre / tape left` throughout.

Run against the **deployed site** (`https://xxbeansproutxx.github.io/big-pond-chop/`):

```
video: tmp/live-audit-5g/tape.webm (1.1 MB)
mp4:   tmp/live-audit-5g/tape.mp4 (0.3 MB)
frames: 21 PNGs at 2 fps
reticle fixed              ok     pill minus window centre spread=0.00 px over 52 samples
tape moves on play         ok     tape left moved -132.5 px, idx 86 -> 94 during playback
drag left advances         ok     idx 31 -> 70 on -150 px drag
drag right rewinds         ok     idx 70 -> 44 on +100 px drag
7d tape wide               ok     tape width 1330 px at 7 day
SUMMARY: 5 ok, 0 FAIL
```

`0.00 px` over 52 samples is the whole claim: **the reticle does not move; the tape does.**
Drag arithmetic checks out exactly — 150 px ÷ 3.8958 px/frame = 38.5 frames (31 → 70),
100 px ÷ 3.8958 = 25.7 frames (70 → 44).

Frame-by-frame read of the recording (vision audit of extracted frames): the pill sits centred in
the bar in both horizons; at 7 day the tape scrolls `Friday 11 | Saturday 12 …` past the reticle
with the full `12 03 06 09` sub-row on every day; the NOW hairline is visible inside the tape; the
play glyph stays pinned on the left edge (pause bars during playback, with a dark scrim behind it)
while the day header passes underneath. No clipped or overlapping labels.

## Production deployment (stage 5G)

- **Push.** `git push origin main`: `809d84d..6d6f13e` (spec → 5G → merge → audit tool),
  2026-09-12 02:5x UTC. Rollback tag `pre-stage5g` (`809d84d`, last 5F.1 deploy) pushed to origin.
- **GitHub Pages build.** `pages/builds/latest`: `status=built`, commit `6d6f13e`,
  `duration=37592 ms`, `error.message = null`; 10/10 spot-checked assets HTTP 200.
- **Live smoke — `tools/qa/live_smoke.py` (updated to the 5G contract), 10 ok / 0 FAIL:**

```text
deck two-row             ok     deckH=68.0 blocks=1 absent=True
pill permanent           ok     text='9:30 PM' hidden=False above-bar=True
reticle centred          ok     pill centre == timeline centre (<=1px)
play pinned              ok     play overlays the window's left edge, z-index>=10
tape wired               ok     tape=374 px inside #timeline=True
ribbon flush             ok     ramp/deck delta ok=True
day header               ok     block0 header='Friday 11' subs=['12', '03', '06', '09', '12', '03', '06', '09']
7 day live               ok     blocks=7 alt=True boot-hidden=True tape=1330 sub-labels=[8, 8, 8, 8, 8, 8, 8]
back to 24 h             ok     aria-valuemax=95
no page errors           ok     errors=0 []
SUMMARY: 10 ok, 0 FAIL  (https://xxbeansproutxx.github.io/big-pond-chop/)
```

### Notes for the next session

- `live_smoke.py`'s old "play embedded" assertion (`#timeline` starts after the play button) is
  **invalid from 5G on**: the play button overlays the window. It now asserts the overlay geometry
  (`0 ≤ playX − trackX ≤ 56`, `z-index ≥ 10`).
- The 24 h tape ends at the "now" frame. Any audit that wants a forward drag must rewind first,
  or it starts clamped at the last frame (this bit the first run of `tape_audit.py`).
