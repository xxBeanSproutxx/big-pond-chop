# STAGE 5N — RECEIPTS (7-day tape 190 → 330 px/day · cyan calm floor · ink-gap gate)

Branch `stage5n` (off `stage5m` @ 672a233), commit `547c911`, pushed as the preview branch.
`main` = `383126e` (5I) untouched — no merge, no tag. Net vs `stage5m`: **7 files, +176/−29**.

## 0. The 5M miss, measured before the fix

Reid reported 7d hour/wind values colliding (“14” + “20” merging). **Confirmed** using text-run *ink*
boxes (`Range.getClientRects()`, not span boxes) on the pre-change tree:

| | min tick gap | min wind gap | overlap |
| --- | --- | --- | --- |
| 7d @ 190 px/day | **0.5 px** | **−0.7 px** | **yes** (first pair) |
| 24h @ 550 px/day | 45.5 px | 44.3 px | no |

The 5M verifier missed it because it compared label *centres* (0.00 px) while each span is a fixed
1.5 em box — the boxes hide ink collisions. Hence both the density change and a new permanent gate.

## 1. 7-day density 190 → 330 px/day

- `pxPerDay('7d') = 330` → **2,310 px** tape, **41.25 px per 3-hour interval**; `24h` untouched at
  `max(550, window)`.
- Measured after: 7d block **330 px**, min tick gap **18.0 px**, min wind gap **16.8 px**, **zero
  overlap** across all 7 blocks (per-block wind gaps `[16.8, 20.3, 16.8, 16.8, 23.8, 23.8, 23.8]`),
  worst tick-vs-wind centre delta **0.01 px**, 8 + 8 labels per block, interior blocks re-measured at
  mid-week (same 16.8 px floor).
- **New permanent gate** in `[18]`: both rows are measured as ink runs at both horizons — no pair may
  overlap and the minimum gap must be **≥ 6 px**; the harness prints `5n gaps 24h=44.3px 7d=16.8px`.
  (Wired into the `[18]` verdict, not just printed.)
- Constant sites updated consistently: `src/render.js` `pxPerDay`; `stage5_check.py` `pxf` ×3 and the
  `[16]` band → `2280 ≤ tapeW ≤ 2340`; `tests/render.test.js` → 330 and 330/96; and
  `tools/qa/live_smoke.py` (same constant, same ±30 band — the worker flagged it as outside the spec's
  file list; it is a sync, not a loosening).

## 2. Cyan calm floor

- `HS_STOPS[0]` = `CALM_RGBA` = **`#06b6d4`** `[6, 182, 212, 255]`; `OVERLAY_OPACITY` unchanged **0.68**.
- Measured forced-calm composite: **`rgb(84, 203, 224)`** (luminance 179, b−r 140, g−r 119) — bright
  saturated turquoise; predicted ≈`rgb(70, 190, 210)` from the nominal basemap grey.
- Legibility: 223 lake-label pixels — glyph-vs-water contrast **44.1 % (bare map) → 20.0 % (tinted)**,
  label fidelity **r = 0.999**. Vision check: water reads as bright turquoise and “Mille Lacs Lake” /
  “Mille Lacs Reservation” remain readable through it.
- Legend gradient (six stops kept): `rgb(6,182,212) 0%, rgb(6,182,212) 16.7%, rgb(245,158,11) 33.3%,
  rgb(234,88,12) 50%, …`.
- **Consequence to report:** the 1.0 ft stop was already `#06b6d4`, so the **0–1 ft band is one flat
  cyan** and the legend's first two entries are identical (asserted deliberately in `[7a]` and
  `tests/ui.test.js` so nobody mistakes it for a bug). The alternative — floor `#0891b2` — keeps a
  gradient inside 0–1 ft and is a one-line change.

## Gates (all run by the orchestrator on the final tree)

| gate | result |
| --- | --- |
| node suites `parity/wind/render/ui` | 4/4, exit 0 (`7d->330`, `pxPerFrame 3.4375`) |
| `tools/qa/stage5_check.py` | **24 ok / 0 FAIL** |
| `tools/qa/live_smoke.py` | **10 ok / 0** |
| `tools/qa/scrub_bench.py` | 3/3 PASS — medians **16.65 / 16.68 / 18.57 ms**, **0 long tasks**, swaps 10, `idx 42 == expected 42`, page reports `px_per_day_7d=330.0` |
| physics diff vs `main` | **0 lines** |
| `verify5n.py` (independent) | **12 ok / 0 FAIL** |

Gate lines: `[16] 7d tape=2310.0 blocks=7 subs=[8×7] alt=True centred=True frame-under=True`;
`[18] … min-12-gap=154.5>=20=True | 5n gaps 24h=44.3>=6=True 7d=16.8>=6=True overlap=False/False`;
`[17] moves=31 swaps=11<=12 long-max=0<=50 idx=42 expected=42`; `[14] live seam ok (dSpeed=0.60 dDir=3.00)`.

## Honest notes

1. My verifier's first pass failed `B2` — my assertion wrongly required 8 ticks in the 24h block,
   which legitimately has 9 (8 three-hourly + the boundary `12`). Test-side bug, fixed; the product
   was correct.
2. A 7d day block is now 330 px wide against a 374 px window, so roughly one day fills the view and a
   full 7-day sweep needs ~1,936 px of drag (more swipes than before) — that is the cost of the
   padding Reid asked for.
3. `src/render.js`'s diff is a comment plus one constant — the 5H decoupled scrub path is untouched,
   and the bench confirms the 16–18 ms budget is intact.

Changed files: `src/render.js`, `src/ui.js`, `tests/render.test.js`, `tests/ui.test.js`,
`tools/qa/stage5_check.py`, `tools/qa/live_smoke.py`, `docs/BUILD-SPEC-STAGE5N.md`
(+ evidence in `tmp/5n-shots/`).
