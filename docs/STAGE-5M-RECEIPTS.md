# STAGE 5M — RECEIPTS (three-tier tape: day / hours / wind · strip removed · opacity 0.68)

Branch `stage5m` (off `stage5l` @ a65347c), pushed as the preview branch `origin/stage5m`.
`main` = `383126e` (5I) untouched — no merge, no tag. Net vs `stage5l`: **8 files, +319/−87**.

## 1. Three-tier scrolling tape (`#track-tape`)

Rows now: `.day-head` (top 6 px) / `.day-sub` hour ticks (top 28 px) / **`.day-wind` mph (top 48 px)**,
inside a 68 px tape row — all children of the day block, so they translate with the hours.

- Values come from the new **pure** helper `tickWinds(entries, start, end)` (`src/render.js`): the frame
  whose local time is exactly `hh:00`, `Math.round(speedMph)`; missing/non-finite frames are skipped.
  Built in `renderTimeline()` (mount/resize/horizon change) — **nothing added to the per-frame path**.
- **24h**: winds `['14','20','23','18','23','22','21','20']` under ticks `['12','03','06','09','12','03','06','09']`
  → worst tick-vs-wind centre delta **0.00 px** (of the 8; 9th tick is the boundary `12`).
- **7d**: every block carries 8 numeric values (counts `[8,8,8,8,8,8,8]`), worst delta **0.00 px**,
  first block identical list.
- Boundary `12` tick deliberately carries **no** wind value (there is no 24:00 frame in the block).

## 2. Bottom text row removed

`#wind-strip` (element + `.deck-wind` CSS + `ui.windStrip()` + its write) deleted. Measured:
`deckH=68.0 trackH=68.0 timelineH=68.0 strip-absent=True` → map height unchanged; the freed 20 px
became tape space for the third row.

## 3. Calm-water opacity balance

`OVERLAY_OPACITY 0.85 → 0.68`; calm stays `#0369a1` at alpha 255 (`CALM_RGBA=[3,105,161,255]`).
Measured composite over forced-calm data: **`rgb(68, 138, 176)`** (b−r = 108, g−r = 70) — saturated
blue, not slate. Legibility, measured on the bare-map vs tinted pair over **109,635 water pixels**:

- label pixels n=66, glyph-vs-water contrast **40.3 % (bare map) → 21.9 % (with the 0.68 tint)**
- label fidelity **r = 0.998** (the tint is an exact affine transform where the detail lives)
- open-water Pearson r is *degenerate* (σ ≈ 4.9 luminance levels of texture) and is reported as
  information only — it is not a gate.
- Vision check on the rendered frame: “Mille Lacs Lake” and “Mille Lacs Reservation” legible through
  the water; water reads as saturated medium-to-deep blue.

## 4. Wave legend card kept (bottom-left)

`#legend-card` stays in `#map`, `pointer-events:none`, six stops. Reid asked for `bottom:78px`;
**the 78–111 px band intersects the OSM attribution band (74–91 px, x 156–390) over x 156–176**, so the
card is docked at **`left:10px; bottom:98px`** (clears it by 7 px; the reason is a code comment in
`index.html`). `#card` (tap readout) moved to `bottom:140px` → stacks above the legend.
Measured: legend `[10,645,176,678]` bottom-offset 98 px, **overlap=false**; card `[10,503,241,636]`
with the legend, **overlap=false**.

## Gates (all on the 5M tree, run by the orchestrator)

| gate | result |
| --- | --- |
| node suites `parity/wind/render/ui` | 4/4, exit 0 |
| `tools/qa/stage5_check.py` | **24 ok / 0 FAIL** |
| `tools/qa/live_smoke.py` | **10 ok / 0** |
| `tools/qa/scrub_bench.py` | 3/3 — medians **16.6 / 16.84 / 18.03 ms**, **0 long tasks in all three**, 10 swaps / 10 paints |
| physics diff vs `main` | **0 lines** |
| `verify5m.py` (independent) | **13 ok / 0 FAIL** |

Gate lines worth quoting: `[15] deckH=68.0 strip-absent=True trackH=68.0 timelineH=68.0 pill-centred=True`;
`[18] one-head=True sticky-window=True head-x0=201 head-x95=64 | 5m wind 24h counts=[8] worst=0.00px nums=True
boundary-no-wind=True list=['14','20','23','18','23','22','21','20'] | 7d counts=[8×7] worst=0.00px`;
`[17] moves=31 swaps=10<=12 long-max=0<=50 idx=42 expected=42`.

## Preview

- Branch pushed: `origin/stage5m` (public repo). Live Pages site **remains 5I on `main`** — Pages is a
  legacy main-only build, so GitHub provides no per-branch preview URL.
- LAN preview (branch tree, bound `0.0.0.0`): `http://192.168.0.61:8796/index.html`.

## Honest notes

1. Wind values are plain integers with no unit suffix (per the brief, e.g. `14 15 18`); the calm row
   therefore shows a single digit per hour (`2`).
2. The boundary `12` tick has no wind value by design (no 24:00 forecast frame inside the block).
3. Reid's `bottom:78px` legend offset was changed to `98px` on measurement (see §4) — one line to revert
   if he'd rather move the attribution instead.
4. Falsy-zero sweep after the verifier incident: every numeric `||` fallback in `src/` is either an
   intentional default (`(h % 12) || 12` → midnight) or one whose fallback equals the legitimate zero.
   No product-side instances of the failure class.

Changed files: `index.html`, `src/render.js`, `src/ui.js`, `tests/render.test.js`, `tests/ui.test.js`,
`tools/qa/stage5_check.py`, `tools/qa/live_smoke.py`, `docs/BUILD-SPEC-STAGE5M.md`
(+ evidence in `tmp/5m-shots/`).
