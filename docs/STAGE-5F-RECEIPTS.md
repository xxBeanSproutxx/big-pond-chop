# Stage 5F receipts — Windy-paradigm deck refactor

Branch `stage5f`. Scope: `index.html`, `src/render.js`, `src/ui.js`,
`tests/render.test.js`, `tools/qa/stage5_check.py`, this document. No engine
files, no remote operations.

Harness command:

```
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py
```

## Gate summary

- Harness: **`SUMMARY: 21 ok, 0 FAIL`** (20 existing entries + the new `[15]`).
- Node suites: `parity`, `wind`, `render`, `ui` — all `ALL TESTS PASSED`.
- Screenshots: `tmp/s5f-shots/{24h.png,7d.png,scrub.png,24h-360.png}` (plus the
  harness's own `bpc-s5-*.png`).
- Measured deck height **68.0 px** (gate ≤ 72). Ribbon bottom == deck bottom
  (delta 0.0 px). Amber pill **68 × 20 px**, visible with text `9 PM` before any
  interaction.

## Verbatim harness run

Run on the pre-commit working tree at `HEAD 8fecd3b` (the dispatch commit); the
commit that follows contains exactly this source state.

```
STAGE 5 RECEIPTS — big-pond-chop
generated: 2026-09-12 02:01:36 UTC
HEAD: 8fecd3b docs(stage5f): dispatch spec — Windy-paradigm deck rebuild
harness: 390x844 DPR2 + 360x800, http://127.0.0.1:56597
------------------------------------------------------------------------------
[1] boot                   ok   visible_before=True hidden_after=True overlay_src=blob:http://... naturalWidth=780x796
        5F rects: deck h=68.0 play=[8.0,776.0]x48.0x48.0 timeline=[56.0,776.0]-[382.0,824.0] pill=[310.0,776.0] 68.0x20.0 text='9 PM' blocks=1 bg=['rgb(38, 41, 48)'] ramp-deck delta=0.0
[15] deck geometry (5F)     ok   deckH=68.0 absent={'main': True, 'playhead': True, 'rail': True, 'progress': True} pill-visible=True pill-hidden=False pill='9 PM' play-inside=True timeline-inside=True blocks=1 adjacent-differ=True ramp-bottom=844.0 deck-bottom=844.0
[2] frame base             ok   track.aria-valuemax=95 data-step-min=15 ticks=10 distinct=True minutes%15=True
        series: ['2026-09-11T21:15', '2026-09-11T21:30', '2026-09-11T21:45', '2026-09-11T22:00', '2026-09-11T22:15', '2026-09-11T22:30', '2026-09-11T22:45', '2026-09-11T23:00', '2026-09-11T23:15', '2026-09-11T23:30']
[2b] horizon ceiling        ok   7d max=671 pressed 7d/24h=true/false boot-hidden=True | 24h max=95 pressed 24h/7d=true/false boot-hidden=True
[3] header layout          ok   390: 72/72 | 360: 72/72 | worst='Peak: 3.9 ft · Upper and Lower Twin Island' natural=251px scrollWidth=314 clientWidth=314 over=0 widest_natural=251px overflow=none
[4] tier chip              ok   max=2.489 roller=4.157 H/L=0.044 => tier-red 'Dangerous · Stay Home' | chip='tier-red' text='Dangerous · Stay Home'
[5] clock                  ok   time-pill='9 PM' zoneinfo='9 PM' data-hour=2026-09-11T21:00 regex=True
[6] compass badge          ok   text='S 177°' arrow=177.00° expected=177.00° delta=0.00 (into-wind) top-right=True clear-zoom=True aria='Wind from S at 177 degrees'
[7a] ramp location          ok   ramp in-deck=True in-map=False legend-present=False stops=['0', '1', '2', '3.5', '4.5', '6+'] gradient-six=True
[8] tap card               ok   fields=['Open water - NW Basin', '46.2391, -93.6429', '37.5 ft', '2.0 ft', '3.4 ft', '0.046'] opened=True dismissed-pin=0=True land-flash='land — no wave data here' revert='tap the lake for a local readout' land-hit=DIV|leaflet-container leaflet-touch leaflet-retina leaflet-fade-anim leaflet-grab leaflet-touch-drag leaflet-touch-zoom
        drift: start=19 landed=67 expected=67 (+/-1) during-pill=True text='4:45 PM' after-pill-hidden=False
        play-click: before=67 after=67 unchanged=True play=48x48
        pill right: idx=95/95 pill=[303.5,371.5] timeline=[56.0,382.0] inside=True
        pill left:  idx=0/0 pill=[60.0,128.0] timeline=[56.0,382.0] inside=True
        deck-ramp drift: press=(195.0,838.0) target=DIV. interactive=False landed=67 expected=67 (+/-1) pill-during=True hidden-after=False
[7b] touch ergonomics       ok   wander±80 landed=67/67 pill-during=True pill-after=False play-unchanged=True play=48x48 right=95/95 inside=True left=0/0 inside=True deck-press=DIV. noninteractive=True deck-landed=67/67
[9] playback perf          ok   canvas_during=780 ticks=10 frameMs avg=41.4 max=44.0 encodeMs=12.6 canvas_paused=1536 created=66 revoked=59
        frameMs: [40.9, 41, 41.1, 41.7, 40.1, 42.4, 44, 40.7, 40.5, 41.1]
        hours:   ['2026-09-11T17:00', '2026-09-11T17:15', '2026-09-11T17:30', '2026-09-11T17:45', '2026-09-11T18:00', '2026-09-11T18:15', '2026-09-11T18:30', '2026-09-11T18:45', '2026-09-11T19:00', '2026-09-11T19:15']
[10] radar smoothing        ok   upscale fit=0.456 z13=1.408 z14=2.817 (gate <=3.0, 1536px ceiling accepted)
[10.1] land bleed             ok   land_alpha=[0, 0, 0, 0] mid_lake_alpha=[255, 255] (land must be 0, mid >0)
        level   pre-stage4 (stages 1-3)   stage-4 (now)
        fit     0.927                    0.456
        13      5.633                    1.408
        14      11.268                   2.817
[11] before/after           ok   fit 0.927->0.456  z13 5.633->1.408  z14 11.268->2.817
[13] lazy 7d compute        ok   precomputeMs first=40.7 idle=40.7 idle_delta=0.0 (gate <=10, first<500)
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
SUMMARY: 21 ok, 0 FAIL
screenshots: 24h-360.png, 24h.png, 7d.png, bpc-s5-360.png, bpc-s5-390.png, bpc-s5-card.png, bpc-s5-now-fit.png, bpc-s5-now-z13.png, bpc-s5-now-z14.png, bpc-s5-play.png, bpc-s5-pre4-fit.png, bpc-s5-pre4-z13.png, bpc-s5-pre4-z14.png, scrub.png
```

## Four Node suite tails

```
$ node tests/parity.test.js | tail
  water cells w/ Hs : 50656
  ms/hour           : 1.177 (budget 2-6)

ALL TESTS PASSED

$ node tests/wind.test.js | tail
  ms/frame (blended, incl. lake-max scan): 1.684 (budget <= 6)
  ok   budget <= 6 ms/frame

ALL TESTS PASSED

$ node tests/render.test.js | tail
  ok   playStep + nextPlayIdx wrap cleanly at the 7-day boundary
  ok   #scrub shim is gone; timeline containers present

ALL TESTS PASSED

$ node tests/ui.test.js | tail
  ok   short + long weekday from calendar math (no TZ-parse)
  ok   bad input -> empty string

ALL TESTS PASSED
```

## Measured deck / pill / ribbon numbers

Source: harness `[15]` (390x844, DPR2, default 24 h horizon, immediately after
boot, before any interaction).

| Item | Measured |
| --- | --- |
| `#deck` height (safe-area excluded) | **68.0 px** (gate ≤ 72) |
| `.deck-main` / `#playhead` / `#track-rail` / `#track-progress` | all absent (`True`) |
| `#play` rect | `[8.0, 776.0]` **48.0 × 48.0** |
| `#track` rect | `[8.0, 776.0] – [382.0, 824.0]` |
| `#timeline` rect | `[56.0, 776.0] – [382.0, 824.0]` (**326 px** wide, inside `#track`, starts at play's right edge) |
| `#time-pill` rect | **68.0 × 20.0**, visible, no `hidden` attribute, text `9 PM` |
| Day blocks in `#track-days` | 1 at 24 h (adjacent-colour check vacuous/True); 7 at 7 d |
| Ribbon `.deck-ramp` bottom vs `#deck` bottom | 844.0 vs 844.0 (**delta 0.0 px**) |
| Pill clamp (from `[7b]`) | right frame 95 → pill `[303.5, 371.5]` inside timeline `[56.0, 382.0]`; left frame 0 → pill `[60.0, 128.0]` inside |
| Play / track geometry drift | landed 67/67 expected (wander ±80 px), deck-wide capture from `.deck-ramp`, play not toggled, play target 48×48 |

Screenshots (phone viewport, deck visible at frame bottom):

- `tmp/s5f-shots/24h.png` — 390x844 DPR2, 24 h
- `tmp/s5f-shots/7d.png` — 390x844 DPR2, 7 day
- `tmp/s5f-shots/scrub.png` — 390x844 DPR2, mid-scrub (pill `5 PM`)
- `tmp/s5f-shots/24h-360.png` — 360x800 DPR2, 24 h

At 390 px / 7 days the day header degrades to the day number alone (the widest
abbreviation, `Wed 16` ≈ 46.2 px, does not fit a 46.6 px block with padding) and
the 3 h sub-row thins to a 12 h step (`12 12` per block) — the degradation the
spec calls out, not an overlap/clip failure.

## Test / assertion changes

| # | File / location | Change | Justification |
| --- | --- | --- | --- |
| 1 | `tests/render.test.js` deck-markup id list | Required ids → `play, track, timeline, track-days, track-ticks, track-label, now-tick, time-pill, h-24h, h-7d, ramp-bar, ramp-ticks`; added absence asserts for `playhead, track-rail, track-progress, deck-day, hour-label, play-label, deck-main`; id search widened from `<footer>` to the whole document (horizon ids now live in `#map`) | Pre-authorised item 1; horizon relocated by spec §1 |
| 2 | `tests/render.test.js` `clampPillX` test | Pill width 64 → **68**; expected last-frame left `trackW-72`, mid `66` | Pre-authorised item 2 (new pill width) |
| 3 | `tests/render.test.js` `[10] timeline containers` | Required set: dropped `deck-day`, added `timeline` | Spec deletes `#deck-day`; this second occurrence was not in the pre-authorised list → recorded conflict below |
| 4 | `tools/qa/stage5_check.py` `[7b]` geometry source | Read `#timeline` rect instead of `#track-rail` | Pre-authorised item 3 |
| 5 | `tools/qa/stage5_check.py` `[7b]` pill visibility | Assert `#time-pill` visible + un-hidden **during and after** both drifts (was: visible during, hidden after) | Pre-authorised item 4 (pill is permanent) |
| 6 | `tools/qa/stage5_check.py` `[7b]` second drift | Press inside `.deck-ramp` (was `.deck-main`) | Pre-authorised item 5 (deck-main row deleted) |
| 7 | `tools/qa/stage5_check.py` new group `[15] deck geometry (5F)` | deck height, removed-node absence, permanent pill, play/timeline rect nesting, day blocks + colour alternation, flush ribbon; prints all measured rects | Pre-authorised item 6 |
| 8 | `tools/qa/stage5_check.py` `[5] clock` | Read `#time-pill` (compact `h AM/PM` format) instead of `#hour-label` | Spec deletes `#hour-label`; gate 1 (0 FAIL) cannot hold otherwise — recorded conflict below |
| 9 | `tools/qa/stage5_check.py` screenshots | `SHOTS` dir → `tmp/s5f-shots/`; added `24h.png`, `7d.png`, `scrub.png`, `24h-360.png` captures | Done-when 3 |

No test deleted; no assertion weakened beyond the items above. `src/ui.js` gained
a pure `formatPillTime()` helper (not covered by any altered `ui.test.js`
assertion; verified manually against the spec examples `10 AM`, `12 PM`,
`1:15 AM`).

## Spec vs observed reality — conflicts recorded

1. **`[5] clock` depended on `#hour-label`**, which this spec deletes, but the
   pre-authorised assertion list (items 1–6) does not mention `[5]`. Gate 1
   (`0 FAIL`, `N ≥ 21`) is unachievable without touching it, so `[5]` was
   re-pointed at the permanent `#time-pill` and the new compact format. This is
   a 7th assertion change, forced by the spec's own deletion.
2. **`tests/render.test.js` `[10]` also required `#deck-day`**, also deleted by
   the spec, and again not covered by the pre-authorised list (item 1 names only
   the main id list). Dropped `deck-day`, added `timeline`.
3. **Pre-authorised item 1 puts `h-24h`/`h-7d` in the required-id set**, but
   spec §1 moves them into `#map`; the test's original search was scoped to
   `<footer id="deck">`. The required-id search was widened to the whole
   document so the horizon ids are found; the deck-only assertions stay
   footer-scoped.
4. **Deck height arithmetic**: `--deck-h: 68px` (48 + 20) only measures ≤ 72 px
   if vertical padding is removed; the original deck carried 4 px top/bottom
   padding (would be 76 px). Deck vertical padding set to 0 (horizontal 8 px
   retained), giving a measured 68.0 px.
5. **Pill motion used `transform`, not `left`**, while the spec asks to keep a
   short `left` transition. Pill placement switched to `left` so
   `transition: left .12s linear` applies (disabled under `body.reduced-motion`,
   unchanged).
6. `#track-label` is retained (required id) but visually clipped, as the day
   blocks now carry the day/horizon text.
