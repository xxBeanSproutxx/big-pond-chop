# Stage 5 receipts — big-pond-chop

Committed receipt for **stage 5E (QA harness migration + deploy prep)**. Every number
below is the verbatim stdout of `tools/qa/stage5_check.py`, the four Node suites, the
frame bench, and `tools/qa/seam_check.js` — not a hand-written snapshot. Re-run any time with:

```sh
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py
```

The harness is a full migration of `tools/qa/stage4_check.py` (now deleted): it serves
the repo with `python -m http.server`, drives Chromium at 390x844 (DPR 2) and 360x800,
compares against a read-only worktree of tag `pre-stage4` (the stage-1-3 baseline), runs
the Node suites, and shells out to `tools/qa/seam_check.js` for the live +48 h seam. It
exits 0 even when a check fails: failures are findings, not harness crashes.

## What changed since stage 4

- **Migration.** Same structure, helpers (`record`/`safe`/`free_port`/`serve`/`wait_http`/
  `new_page`/`main`), the same 17 pre-existing groups, the same exit-0 contract, and
  `ROOT = Path(__file__).resolve().parents[2]`. Module header is now `STAGE 5 RECEIPTS`
  and screenshots are `bpc-s5-*.png`. Check 11 still pins `PRE_TAG = "pre-stage4"`.
- **Authorised assertion changes** (the point of this stage):
  1. `[2]` keeps the 24 h baseline (`aria-valuemax == "95"`). New `[2b] horizon ceiling`
     clicks `#h-7d`, waits for `671`, clicks `#h-24h`, waits for `95`, prints both
     ceilings plus both `aria-pressed` states — and asserts the `#boot` skeleton is hidden
     again after each transition (the 5D.2 regression pin, added by the orchestrator).
  2. `[7b] touch ergonomics` gained a **second drift** that presses inside the
     `.deck-main` row (deck-centre x, `deck.y + 24`) — asserted non-interactive — wanders
     ±80 px and lands at ~70 % of the rail. The existing track-row drift, pill-visible /
     pill-hidden, play-click and ≥44 px assertions are unchanged.
  3. `[7a]` carries the ramp-docking assertion unchanged: ramp in `#deck`, not in `#map`.
  4. `[7b]`'s focused clamp check now proves **both ends**: far-right → `n−1` and far-left
     → `0`, with the pill rect fully inside the track rect at each; both raw pill/track
     rects are printed.
- **New `[13] lazy 7d compute`.** Widening to 7 d builds one frame, not a sweep:
  `precomputeMs first < 500` and, after 2500 ms idle, `idle_delta <= 10`.
- **New `[14] live seam`.** `tools/qa/seam_check.js` runs `wind.ingest({ horizon: '7d' })`
  live and asserts the first frame of local day 3 is continuous with its predecessor:
  `Δspeed <= 2.0 mph` and shortest-arc `Δbearing <= 6.0°`.
- **5D.1 gate fix noted.** The stage-5 browser history includes the 5D.1 fix (now-tick /
  playhead re-placed on resize; first day label un-clipped). The migrated harness still
  exercises that geometry through `[7b]`'s rail/pill rect checks.
- **5D.2 gate fix (orchestrator, found by this migration).** The widen/refresh path shows
  the boot skeleton (`boot()` in `src/render.js`) but `showFrame` only hid it while
  `bootHidden` was false — and that flag was set once at first paint. Net effect: after
  any widen the `#boot` overlay stayed visible and intercepted map clicks, so a horizon
  gate running before `[7] tap card` deadlocked it (observed in the first
  `stage5_check.py` runs as a `[7] tap card` timeout; confirmed with a standalone
  Playwright probe: `boot.hidden=False`, `elementFromPoint(centre)=#boot` after widen,
  narrow and refresh). App code was out of scope for the migration, so the defect was
  recorded, not patched. It was then fixed as **5D.2** — one line resetting
  `bootHidden = false` inside `boot()` — `[2b]` was restored to its spec position (right
  after `[2]`), and the later map-tap group now regression-tests the fix.

### Resolved conflict (5D.2)

The stage-5D widen/refresh flow re-shows the boot skeleton, but `showFrame` only hid it
once ever; the overlay then covered the map and swallowed taps. Recorded by the migration
run (see above), fixed in 5D.2 (commit `b604f9b`), ordering restored in 5E.1 (commit
`20a65eb`). Probe after the fix, same script: `boot.hidden=True`, `elementFromPoint=#map`
after widen, narrow **and** refresh. All groups pass with the new ordering — see the
verbatim run below.

## Verbatim run

```text
STAGE 5 RECEIPTS — big-pond-chop
generated: 2026-09-12 01:30:26 UTC
HEAD: 20a65eb Stage 5E.1: restore the [2b] horizon gate to its spec position + pin boot-hide after transitions (5D.2 regression)
harness: 390x844 DPR2 + 360x800, http://127.0.0.1:55809
------------------------------------------------------------------------------
[1] boot                   ok   visible_before=True hidden_after=True overlay_src=blob:http://... naturalWidth=780x796
[2] frame base             ok   track.aria-valuemax=95 data-step-min=15 ticks=10 distinct=True minutes%15=True
        series: ['2026-09-11T20:45', '2026-09-11T21:00', '2026-09-11T21:15', '2026-09-11T21:30', '2026-09-11T21:45', '2026-09-11T22:00', '2026-09-11T22:15', '2026-09-11T22:30', '2026-09-11T22:45', '2026-09-11T23:00']
[2b] horizon ceiling        ok   7d max=671 pressed 7d/24h=true/false boot-hidden=True | 24h max=95 pressed 24h/7d=true/false boot-hidden=True
[3] header layout          ok   390: 72/72 | 360: 72/72 | worst='Peak: 3.9 ft · Upper and Lower Twin Island' natural=251px scrollWidth=314 clientWidth=314 over=0 widest_natural=251px overflow=none
[4] tier chip              ok   max=2.802 roller=4.679 H/L=0.045 => tier-red 'Dangerous · Stay Home' | chip='tier-red' text='Dangerous · Stay Home'
[5] clock                  ok   hour-label='8:30 PM CDT' zoneinfo='8:30 PM CDT' data-hour=2026-09-11T20:30 regex=True
[6] compass badge          ok   text='S 173°' arrow=173.00° expected=173.00° delta=0.00 (into-wind) top-right=True clear-zoom=True aria='Wind from S at 173 degrees'
[7a] ramp location          ok   ramp in-deck=True in-map=False legend-present=False stops=['0', '1', '2', '3.5', '4.5', '6+'] gradient-six=True
[8] tap card               ok   fields=['Open water - N Basin', '46.2398, -93.6429', '37.5 ft', '2.3 ft', '3.9 ft', '0.047'] opened=True dismissed-pin=0=True land-flash='land — no wave data here' revert='tap the lake for a local readout' land-hit=DIV|leaflet-container leaflet-touch leaflet-retina leaflet-fade-anim leaflet-grab leaflet-touch-drag leaflet-touch-zoom
        drift: start=19 landed=66 expected=67 (+/-1) during-pill=True text='4:30 PM CDT' after-pill-hidden=True
        play-click: before=66 after=66 unchanged=True play=71x48
        pill right: idx=95/95 pill=[314.0,378.0] track=[8.0,382.0] inside=True
        pill left:  idx=0/0 pill=[12.0,76.0] track=[8.0,382.0] inside=True
        deck-main drift: press=(195.0,733.0) target=DIV.deck-row deck-main interactive=False landed=66 expected=67 (+/-1) pill-during=True hidden-after=True
[7b] touch ergonomics       ok   wander±80 landed=66/67 pill-during=True hidden-after=True play-unchanged=True play=71x48 right=95/95 inside=True left=0/0 inside=True deck-press=DIV.deck-row deck-main noninteractive=True deck-landed=66/67
[9] playback perf          ok   canvas_during=780 ticks=10 frameMs avg=42.6 max=55.3 encodeMs=6.8 canvas_paused=1536 created=68 revoked=60
        frameMs: [41.7, 41, 43.4, 40.7, 55.3, 40.7, 40.6, 41.9, 40.3, 40.6]
        hours:   ['2026-09-11T16:45', '2026-09-11T17:00', '2026-09-11T17:15', '2026-09-11T17:30', '2026-09-11T17:45', '2026-09-11T18:00', '2026-09-11T18:15', '2026-09-11T18:30', '2026-09-11T18:45', '2026-09-11T19:00']
[10] radar smoothing        ok   upscale fit=0.456 z13=1.408 z14=2.817 (gate <=3.0, 1536px ceiling accepted)
[10.1] land bleed             ok   land_alpha=[0, 0, 0, 0] mid_lake_alpha=[255, 255] (land must be 0, mid >0)
        level   pre-stage4 (stages 1-3)   stage-4 (now)
        fit     0.927                    0.456
        13      5.633                    1.408
        14      11.268                   2.817
[11] before/after           ok   fit 0.927->0.456  z13 5.633->1.408  z14 11.268->2.817
[13] lazy 7d compute        ok   precomputeMs first=40.8 idle=40.8 idle_delta=0.0 (gate <=10, first<500)
page errors: 0 []
[12] suite parity           ok   exit=0 tail: ALL TESTS PASSED
[12] suite wind             ok   exit=0 tail: ALL TESTS PASSED
[12] suite render           ok   exit=0 tail: ALL TESTS PASSED
[12] suite ui               ok   exit=0 tail: ALL TESTS PASSED
        seam:   prev 2026-09-12T23:45  speed=16.5  dir=342
        seam:   seam 2026-09-13T00:00  speed=16.5  dir=339
        seam:   dSpeed=0.00 mph (gate <= 2)  dDir=3.00 deg (gate <= 6)
        seam:   seam anchor blended speed=16.5 dir=339 | raw hourly speed=16.5 dir=339
        seam: SEAM 2026-09-13 frame=288 dSpeed=0.00 dDir=3.00 PASS
[14] live seam              ok   exit=0 dSpeed=0.00 dDir=3.00 | SEAM 2026-09-13 frame=288 dSpeed=0.00 dDir=3.00 PASS
------------------------------------------------------------------------------
SUMMARY: 20 ok, 0 FAIL
screenshots: bpc-s5-360.png, bpc-s5-390.png, bpc-s5-card.png, bpc-s5-now-fit.png, bpc-s5-now-z13.png, bpc-s5-now-z14.png, bpc-s5-play.png, bpc-s5-pre4-fit.png, bpc-s5-pre4-z13.png, bpc-s5-pre4-z14.png
```

## Node suite + bench tails

```text
$ node tests/parity.test.js
  ok   dispersionFast vs exact cg within 0.5% across field envelope

== [PERF] per-hour field over all 83,220 cells ==
  cells/hour        : 83220
  water cells w/ Hs : 50656
  ms/hour           : 1.172 (budget 2-6)

ALL TESTS PASSED

$ node tests/wind.test.js
  ok   all 96 frames produced a finite, non-negative lake-max Hs
  ok   Hs_max cap: roller uses post-Ks pre-0.6d value

== [5] per-frame field benchmark (blending enabled) ==
  ms/frame (blended, incl. lake-max scan): 1.691 (budget <= 6)
  ok   budget <= 6 ms/frame

ALL TESTS PASSED

$ node tests/render.test.js
       2026-09-11@0 2026-09-12@96 2026-09-13@192 2026-09-14@288 2026-09-15@384 2026-09-16@480 2026-09-17@576
  ok   standard 672-frame shape -> 7 partitions at 0..576
  ok   uneven day lengths 5/4/6 -> indices [0,5,9] (string-derived, not /96)
  ok   single 96-frame day -> one partition
  ok   playStep + nextPlayIdx wrap cleanly at the 7-day boundary
  ok   #scrub shim is gone; timeline containers present

ALL TESTS PASSED

$ node tests/ui.test.js
  ok   ramp gradient contains the six Hs stops in order

== [11] stage-5d dayLabel ==
       Fri 11 / Friday 11
  ok   short + long weekday from calendar math (no TZ-parse)
  ok   bad input -> empty string

ALL TESTS PASSED

$ node tools/bench_frames.js

Stage 4A frame pipeline (96 frames, ms)
  stage                       width   ms/frame   96-frame
  (a) math only                 384       1.51      144.8
  (b) + gather                  384       3.12      299.1
  (c) + gather                  780       7.94      762.6
  (d) + smooth                  780      18.86     1810.6
  (e) + colorize                780      27.50     2639.8

  LRU peak bytes @780        : 2798368 (2.67 MB, url 174866 chars, max 8)

PASS
```

## Live seam (`node tools/qa/seam_check.js`)

```text
  prev 2026-09-12T23:45  speed=16.5  dir=342
  seam 2026-09-13T00:00  speed=16.5  dir=339
  dSpeed=0.00 mph (gate <= 2)  dDir=3.00 deg (gate <= 6)
  seam anchor blended speed=16.5 dir=339 | raw hourly speed=16.5 dir=339
SEAM 2026-09-13 frame=288 dSpeed=0.00 dDir=3.00 PASS
```

## What each check pins

| # | check | what it guarantees |
| --- | --- | --- |
| 1 | boot | skeleton shows then hides; the overlay paints from a `blob:` URL (async encode path) |
| 2 | frame base | 24 h: 96 frames, 15-minute steps, no skipped or repeated tick |
| 2b | horizon ceiling | widening tracks the ceiling (24 h = 95, 7 d = 671), `aria-pressed` follows, and the boot skeleton hides again after each transition (5D.2) |
| 3 | header layout | 72 px at 360 + 390, no clipping, no location label truncates |
| 4 | tier chip | chip class equals an independent re-derivation from the frame's own numbers |
| 5 | clock | 12-hour America/Chicago label == a `zoneinfo` re-derivation |
| 6 | compass badge | arrow rotation == true bearing (INTO the wind), top-right, clear of zoom |
| 7a | ramp location | Hs ramp lives inside `#deck`, NOT inside `#map`; six gradient stops |
| 7 | tap card | 6 fields, ✕ dismisses and stays dismissed, land/nodata dismisses + flashes |
| 7b | touch ergonomics | deck-wide pointer capture (track row + deck-main row), pill linger/hide, play not swallowed, pill clamped inside the track at BOTH ends |
| 9 | playback perf | main-thread frame <= 60 ms, play-width clamp, pause restores width, no URL leak |
| 10 | radar smoothing | upscale within the accepted <= 3.0x ceiling |
| 10.1 | land bleed | alpha 0 on land samples, > 0 mid-lake |
| 11 | before/after | same upscale measurement against a `pre-stage4` worktree |
| 13 | lazy 7d compute | widening builds one frame; idle `precomputeMs` does not grow (LRU/on-demand) |
| 12 | suites | all four Node suites green |
| 14 | live seam | +48 h native→blended handoff continuous (`Δspeed <= 2 mph`, `Δbearing <= 6°`) |

## Production deployment

_Filled by the orchestrator after the push; no numbers here until then._

## Notes

- Browser-group order: `[1]`, `[2]`, `[2b]` (spec position), `[3]`–`[11]`, `[13]` (after
  the pre-existing interaction groups), then `[12]` suites and `[14]` live seam. `[2b]`
  running before `[7]` is deliberate: the map-tap group regression-tests the 5D.2 boot fix.
- Check 2 and check 9 sample `data-hour` ticks only after the play-width regather settles,
  so the one re-render at play/pause is not miscounted as a duplicate tick.
- Check 3 measures intrinsic label width with a DOM `Range`; check 6 verifies the arrow
  `matrix()` rotation against `data-bearing-grid + gamma` independently of the text.
