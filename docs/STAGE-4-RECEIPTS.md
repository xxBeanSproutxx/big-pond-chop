# Stage 4 receipts — big-pond-chop

Committed receipt for **stage 4C (final QA)**. Every number below is the verbatim
stdout of `tools/qa/stage4_check.py` on HEAD `613bdff` (2026-09-12), not a
hand-written snapshot. Re-run it any time with:

```sh
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage4_check.py
```

The harness serves the repo with `python -m http.server`, drives Chromium at
390x844 (DPR 2) and 360x800, measures the live app against the locked Stage-4
contract, compares against a read-only worktree of tag `pre-stage4`, and prints
the four Node suite tails. It exits 0 even when a check fails: failures are
findings, not harness crashes.

## Verbatim run

```text
STAGE 4C RECEIPTS — big-pond-chop
generated: 2026-09-12 00:14:39 UTC
HEAD: 613bdff Stage 4B.1: compass badge top-right + row-2 no-truncate header layout
harness: 390x844 DPR2 + 360x800, http://127.0.0.1:51483
------------------------------------------------------------------------------
[1] boot                   ok   visible_before=True hidden_after=True overlay_src=blob:http://... naturalWidth=780x796
[2] frame base             ok   scrub.max=95 data-step-min=15 ticks=10 distinct=True minutes%15=True
        series: ['2026-09-11T19:15', '2026-09-11T19:30', '2026-09-11T19:45', '2026-09-11T20:00', '2026-09-11T20:15', '2026-09-11T20:30', '2026-09-11T20:45', '2026-09-11T21:00', '2026-09-11T21:15', '2026-09-11T21:30']
[3] header layout          ok   390: 72/72 | 360: 72/72 | worst='Peak: 3.9 ft · Upper and Lower Twin Island' natural=251px scrollWidth=314 clientWidth=314 over=0 widest_natural=251px overflow=none
[4] tier chip              ok   max=2.093 roller=3.495 H/L=0.043 => tier-amber 'Heavy Rollers' | chip='tier-amber' text='Heavy Rollers'
[5] clock                  ok   hour-label='9:30 PM CDT' zoneinfo='9:30 PM CDT' data-hour=2026-09-11T21:30 regex=True
[6] compass badge          ok   text='SW 246°' arrow=246.00° expected=246.00° delta=0.00 (into-wind) top-right=True clear-zoom=True aria='Wind from SW at 246 degrees'
[7] touch ergonomics       ok   refresh=48x48 play=71x48 card-close=48x48 scrub-h=48 controls.touch-action=none
[8] tap card               ok   fields=['Open water - N Basin', '46.2397, -93.6429', '37.5 ft', '1.7 ft', '2.9 ft', '0.045'] opened=True dismissed-pin=0=True land-flash='land — no wave data here' revert='tap the lake for a local readout' land-hit=DIV|leaflet-container leaflet-touch leaflet-retina leaflet-fade-anim leaflet-grab leaflet-touch-drag leaflet-touch-zoom
[9] playback perf          ok   canvas_during=780 ticks=10 frameMs avg=35.9 max=40.4 encodeMs=7.5 canvas_paused=1536 created=30 revoked=22
        frameMs: [40, 37.4, 35, 25.5, 36.8, 35.8, 34.6, 36.2, 37.4, 40.4]
        hours:   ['2026-09-11T21:45', '2026-09-11T22:00', '2026-09-11T22:15', '2026-09-11T22:30', '2026-09-11T22:45', '2026-09-11T23:00', '2026-09-11T23:15', '2026-09-11T23:30', '2026-09-11T23:45', '2026-09-11T00:00']
[10] radar smoothing        FAIL upscale fit=0.456 z13=1.408 z14=2.817 (gate <=1.15)
[10.1] land bleed             ok   land_alpha=[0, 0, 0, 0] mid_lake_alpha=[255, 255] (land must be 0, mid >0)
        level   pre-stage4 (stages 1-3)   stage-4 (now)
        fit     0.927                    0.456
        13      5.633                    1.408
        14      11.268                   2.817
[11] before/after           ok   fit 0.927->0.456  z13 5.633->1.408  z14 11.268->2.817
page errors: 0 []
[12] suite parity           ok   exit=0 tail: ALL TESTS PASSED
[12] suite wind             ok   exit=0 tail: ALL TESTS PASSED
[12] suite render           ok   exit=0 tail: ALL TESTS PASSED
[12] suite ui               ok   exit=0 tail: ALL TESTS PASSED
------------------------------------------------------------------------------
SUMMARY: 15 ok, 1 FAIL
  FAIL [10] radar smoothing
screenshots: bpc-s4-360.png, bpc-s4-390.png, bpc-s4-card.png, bpc-s4-now-fit.png, bpc-s4-now-z13.png, bpc-s4-now-z14.png, bpc-s4-play.png, bpc-s4-pre4-fit.png, bpc-s4-pre4-z13.png, bpc-s4-pre4-z14.png
```

## Finding — radar overlay upscale at zoom 13/14 (check 10)

`#scrub`, the frame time base, the header, tier chip, clock, compass badge,
touch targets, tap card, playback performance, land-bleed, and all four suites
pass. One check group fails:

- The overlay `img` upscale factor (`getBoundingClientRect().width / naturalWidth`)
  is **0.456 at fit**, but **1.408 at zoom 13** and **2.817 at zoom 14**, against
  a gate of **<= 1.15**.
- This is a real, measured display property, not a harness artifact: the raster
  is gathered at the zoom-aware width and clamped to `targetWidth(.., hi=1536)`.
  At zoom 13/14 the lake bbox projects to ~2163 / ~4327 CSS px, so a 1536 px
  raster is stretched 1.4x / 2.8x on screen.
- It is a large improvement over stages 1-3 (see the before/after table: 5.633
  -> 1.408 at z13, 11.268 -> 2.817 at z14), but the 4C gate is not met at the
  two high zoom levels.

Land-bleed passed: all four `wgs84_corners` land samples read alpha 0 on the fit
raster, and both mid-lake samples read alpha 255 — the raster is painted on
water and clean at the corners.

## Screenshots

Saved to `/tmp/bpc-s4-*.png` by the same run:

- `bpc-s4-360.png`, `bpc-s4-390.png` — header/layout pass at both widths
- `bpc-s4-now-fit.png`, `bpc-s4-now-z13.png`, `bpc-s4-now-z14.png` — current app
- `bpc-s4-pre4-fit.png`, `bpc-s4-pre4-z13.png`, `bpc-s4-pre4-z14.png` — pre-stage4
- `bpc-s4-play.png` — mid-play
- `bpc-s4-card.png` — tap cards

## Notes

- Check 2 and check 9 sample `data-hour` ticks only after the play-width
  regather settles, so the one re-render at play/pause is not miscounted as a
  duplicate tick.
- Check 3 measures the intrinsic label width with a DOM `Range` (a block-level
  element's `scrollWidth` equals its client width even when the text fits).
- Check 6 verifies the arrow's `matrix()` rotation against
  `data-bearing-grid + gamma` (the true bearing) so the INTO-the-wind convention
  is checked independently of the badge text.
