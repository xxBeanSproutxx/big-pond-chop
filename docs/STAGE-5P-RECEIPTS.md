# STAGE 5P — RECEIPTS (wind numbers embedded in a 20 px heat ribbon · 3-tier 62 px deck)

Branch `stage5p` (off `stage5o` @ `d167026`), commit `c38727c`, pushed as the preview branch.
`main` = `383126e` (5I) untouched — no merge, no tag. Net vs `stage5o`: **4 files, +144/−46**
(`index.html`, `src/render.js`, `tools/qa/stage5_check.py`, spec doc — no test-file changes were needed).

## 1. One unified bar

- The separate wind row is gone: `.day-wind` now sits **inside the ribbon's vertical band**
  (`top: 40px; height: 20px; line-height: 20px`) and `.day-heat` is appended **before** the numbers in
  the DOM, so the ribbon paints behind the text (`src/render.js` append order: head → ticks → **heat** →
  winds → boundary).
- Ribbon: **20 px** tall (was 6), `left/right: 3px`, `bottom: 2px`, radius 3 px, gradient unchanged
  (24 hourly stops, tier palette).
- **Containment verified per block**: every one of the 8 numbers in all 7 blocks (and the 24h block)
  is vertically inside its ribbon rect — band `[822, 842]` CSS, numbers `[822, 842]`.
- Numbers keep the `tickWinds()` data + anchor rules: 8 per block, tick-vs-wind centre alignment
  **0.01 px**, none under the boundary `12`.

## 2. Text contrast

- White `#ffffff`, `font-weight: 700`, 12 px, `text-shadow: 0 1px 2px rgba(0,0,0,.65)` — computed
  style on the rendered element: `12px | 700 | rgb(255, 255, 255) | rgba(0,0,0,0.65) 0px 1px 2px | line-height 20px`.
  (The `font:` shorthand resets `line-height` — the worker caught that during the build and overrode
  it afterwards; that is why the centring holds.)
- **Measured contrast (WCAG, white vs each tier, and the shadow ring's contribution):**

| tier | white : background | dark shadow : background |
| --- | --- | --- |
| cyan `<10` (#0891b2) | 3.68 : 1 | 5.10 : 1 |
| green `10-14` (#10b981) | 2.54 : 1 | 7.40 : 1 |
| amber `15-19` (#f59e0b) | **2.15 : 1** | 8.74 : 1 |
| orange `20-24` (#f97316) | 2.80 : 1 | 6.70 : 1 |
| crimson `25+` (#ef4444) | 3.76 : 1 | 4.99 : 1 |

  Rendered-pixel check on the actual frame (glyph columns only): green 2.54:1, amber 2.15:1,
  orange 2.80:1 for the white fill, with the **glyph-vs-shadow** edge at **4.79–5.94 : 1** — the dark
  ring is what defines the letterforms, which is why the numbers read on every tier.
- **Honest call-out:** white-on-amber at 2.15:1 is the weakest combination. It is legible in practice
  because of the 8.7:1 dark outline, but if "never wash out" is meant literally, the fix is the
  **dynamic contrast** option Reid listed: dark `#10263a` on the light tiers (green/amber → ≈6.5-8.6:1)
  and white on cyan/orange/crimson. One small helper + gate change — his call.

## 3. Deck height / 3-tier layout

- `--deck-h` **68 → 62 px**; `#track`/`#timeline` **62 px**; measured `deckH=62.0 trackH=62.0 timelineH=62.0`.
- Tiers: header `top: 3px` (600 12 px) · ticks `top: 20px` (11 px `#94a3b8`) · ribbon `40-60 px`.
- Play button (48 px) still fits inside the 62 px row (`play-inside=True`); the pill is unchanged and
  still centred (`cx=195.0 == timeline-cx`).
- Side effect checked: the legend card (map-space `bottom: 98px`) and the attribution lift
  (`calc(var(--deck-h) + 6px)`) both follow the shorter deck — no new overlaps (the attribution band
  moves *down* 6 px, so clearance improves).

## 4. Preserved features (all re-verified)

- Alternating tones exactly `rgb(35,39,46)` / `rgb(27,29,34)`; divider `1px rgb(74,85,104)` = `#4a5568`
  on every block boundary (block 0 has no leading divider, as designed).
- Sticky 24h header: x **201 → 64** at idx 95; 7d headers stay inside their own blocks (mid-week idx 300
  checked).
- Calm floor `#0891b2` @ 0.68: forced-calm composite **`rgb(77, 170, 192)`**, label contrast 39.8 % →
  19.1 %, fidelity r = 0.999.
- 5H decoupled scrub path: **0** changed lines referencing `scrubUiTo` / `scheduleMapPaint` /
  `endScrub` / `shouldPaintMap`.

## Gates (orchestrator runs)

| gate | result |
| --- | --- |
| node suites | 4/4 exit 0 (heat helpers unchanged, so no test edits) |
| `stage5_check.py` | **24 ok / 0 FAIL** — `5p ribbon: count=True h=True stops=True colours=True inside=True shadow=True fonts=True scroll=True | ink-gap 24h=39.0px 7d=11.5px` |
| `live_smoke.py` | **10 ok / 0** |
| `scrub_bench.py` | 24/24 PASS — medians **16.72 / 16.71 / 18.01 ms**, **0 long tasks**, swaps 10, `idx 42 == expected 42` |
| physics diff vs `main` | **0 lines** |
| `verify5p.py` (independent) | **16 ok / 0 FAIL** |

Other lines: `[15] deckH=62.0 … trackH=62.0 timelineH=62.0`; `[16] 7d tape=2310.0 blocks=7 tones-ok=True`;
`[17] swaps=10<=12 long-max=0<=50 idx=42 expected=42`; `[18] … 5p ribbon heat-count=True h=True inside=True
shadow=True colours=True fonts=True scroll=True`.

## Honest notes

1. **My verifier's first pass failed twice, both test-side:** I read the midnight divider on block 0
   (which correctly has none — the divider is `.day-block + .day-block`) and I ran the sticky-header
   check on the 7d tape (the clamp is intentionally 24h-only). Fixed; both now pass with real numbers.
2. The **`font:` shorthand / `line-height` trap** was caught and fixed during the build — worth
   remembering for any future absolute-positioned label that relies on line-height centring.
3. Ink gaps tightened slightly (`7d` 11.5 px min, floor 6 px) because the numbers are now the same
   12 px bold as before but sit over a busier background; no overlap anywhere.
4. **Amber contrast** is the one open judgement call (see §2) — data provided, decision Reid's.

Changed files: `index.html`, `src/render.js`, `tools/qa/stage5_check.py`, `docs/BUILD-SPEC-STAGE5P.md`
(+ evidence in `tmp/5p-shots/`).
