# Stage 4 receipts — big-pond-chop

Committed receipt for **stage 4C (final QA)**. Every number below is the verbatim
stdout of `tools/qa/stage4_check.py`, not a hand-written snapshot. Re-run it any time with:

```sh
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage4_check.py
```

The harness serves the repo with `python -m http.server`, drives Chromium at
390x844 (DPR 2) and 360x800, measures the live app against the locked Stage-4
contract, compares against a read-only worktree of tag `pre-stage4`, and prints
the four Node suite tails. It exits 0 even when a check fails: failures are
findings, not harness crashes.

## Gate override — check 10, accepted by Reid 2026-09-12

Check 10 originally asserted an overlay upscale factor `<= 1.15` at fit/z13/z14. On the shipped
build it measures **0.456 / 1.408 / 2.817**, because the raster is gathered at the zoom-aware width
and clamped by `targetWidth(.., hi=1536)` while the lake bbox projects to ~2163 px (z13) and
~4327 px (z14).

**Decision:** keep the 1536 px ceiling. A soft weather gradient at deep zoom is physically
appropriate for a 5-hour forecast, and a larger canvas risks memory pressure/crashes on mobile
Safari. The gate now pins the *improvement* (`<= 3.0x`) rather than perfection — pre-stage4 measured
**5.633x / 11.268x**. The hard-block artifact is gone: the field-domain, water-masked smoothing is what
removed it, and land bleed is separately proven clean (check 10.1).

## Verbatim run (post-override)

```text
generated: 2026-09-12 00:20:01 UTC
HEAD: 284139a Stage 4C: re-runnable QA harness + Stage-4 receipts
      (+ stage 4C.1 gate override in tools/qa/stage4_check.py)
harness: 390x844 DPR2 + 360x800
------------------------------------------------------------------------------
[1] boot                   ok   visible_before=True hidden_after=True overlay_src=blob:http://... naturalWidth=780x796
[2] frame base             ok   scrub.max=95 data-step-min=15 ticks=10 distinct=True minutes%15=True
[3] header layout          ok   390: 72/72 | 360: 72/72 | worst='Peak: 3.9 ft · Upper and Lower Twin Island' natural=251px scrollWidth=314 clientWidth=314 over=0 widest_natural=251px overflow=none
[4] tier chip              ok   max=2.849 roller=4.758 H/L=0.046 => tier-red 'Dangerous · Stay Home' | chip='tier-red' text='Dangerous · Stay Home'
[5] clock                  ok   hour-label='9:45 PM CDT' zoneinfo='9:45 PM CDT' data-hour=2026-09-11T21:45 regex=True
[6] compass badge          ok   text='W 283°' arrow=283.00° expected=283.00° delta=0.00 (into-wind) top-right=True clear-zoom=True aria='Wind from W at 283 degrees'
[7] touch ergonomics       ok   refresh=48x48 play=71x48 card-close=48x48 scrub-h=48 controls.touch-action=none
[8] tap card               ok   fields=['Open water - N Basin', '46.2397, -93.6429', '37.5 ft', '2.4 ft', '4.0 ft', '0.048'] opened=True dismissed-pin=0=True land-flash='land — no wave data here' revert='tap the lake for a local readout'
[9] playback perf          ok   canvas_during=780 ticks=10 frameMs avg=36.6 max=40.7 encodeMs=7.8 canvas_paused=1536 created=30 revoked=22
[10] radar smoothing        ok   upscale fit=0.456 z13=1.408 z14=2.817 (gate <=3.0, 1536px ceiling accepted)
[10.1] land bleed           ok   land_alpha=[0, 0, 0, 0] mid_lake_alpha=[255, 255] (land must be 0, mid >0)
[11] before/after           ok   fit 0.927->0.456  z13 5.633->1.408  z14 11.268->2.817
[12] suite parity           ok   exit=0 tail: ALL TESTS PASSED
[12] suite wind             ok   exit=0 tail: ALL TESTS PASSED
[12] suite render           ok   exit=0 tail: ALL TESTS PASSED
[12] suite ui               ok   exit=0 tail: ALL TESTS PASSED
------------------------------------------------------------------------------
SUMMARY: 16 ok, 0 FAIL
screenshots: bpc-s4-360.png, bpc-s4-390.png, bpc-s4-card.png, bpc-s4-now-fit.png, bpc-s4-now-z13.png, bpc-s4-now-z14.png, bpc-s4-play.png, bpc-s4-pre4-fit.png, bpc-s4-pre4-z13.png, bpc-s4-pre4-z14.png
```

## What each check pins

| # | check | what it guarantees |
| --- | --- | --- |
| 1 | boot | skeleton shows then hides; the overlay paints from a `blob:` URL (async encode path) |
| 2 | frame base | 96 frames, 15-minute steps, no skipped or repeated tick |
| 3 | header layout | 72 px at 360 + 390, no clipping, **no location label truncates** (23 labels swept) |
| 4 | tier chip | chip class equals an independent re-derivation from the frame's own numbers |
| 5 | clock | 12-hour America/Chicago label == a `zoneinfo` re-derivation |
| 6 | compass badge | arrow rotation == true bearing (INTO the wind), top-right, clear of zoom controls |
| 7 | touch ergonomics | every control >= 48 px, drawer `touch-action: none` |
| 8 | tap card | 6 fields, ✕ dismisses and stays dismissed, land/nodata dismisses + flashes the hint |
| 9 | playback perf | main-thread frame <= 60 ms during play, play-width clamp, pause restores full width, no object-URL leak |
| 10 | radar smoothing | upscale within the accepted ceiling; 4x better than stages 1-3 |
| 10.1 | land bleed | alpha 0 on land samples, > 0 mid-lake (no color bleeding onto land) |
| 11 | before/after | the same measurement against a `pre-stage4` worktree |
| 12 | suites | all four Node suites green |

## Notes

- Check 2 and check 9 sample `data-hour` ticks only after the play-width regather settles, so the one
  re-render at play/pause is not miscounted as a duplicate tick.
- Check 3 measures the intrinsic label width with a DOM `Range` (a block-level element's `scrollWidth`
  equals its client width even when the text fits).
- Check 6 verifies the arrow's `matrix()` rotation against `data-bearing-grid + gamma` (the true
  bearing) so the INTO-the-wind convention is checked independently of the badge text.
