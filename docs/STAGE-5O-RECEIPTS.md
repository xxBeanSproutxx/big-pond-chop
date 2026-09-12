# STAGE 5O — RECEIPTS (wind heat ribbon · day-block & type polish · calm floor #0891b2)

Branch `stage5o` (off `stage5n` @ e278fa4), commit `89a84e5`, pushed as the preview branch.
`main` = `383126e` (5I) untouched — no merge, no tag. Net vs `stage5n`: **7 files, +345/−38**.

## 1. Wind heat ribbon

- Two new **pure** helpers in `src/ui.js`:
  - `WIND_HEAT` tier scale + `windHeatColor(mph)` — `<10` `#0891b2` · `10–14` `#10b981` ·
    `15–19` `#f59e0b` · `20–24` `#f97316` · `25+` `#ef4444` (crimson; `#db2777` is the one-line
    alternate). Non-finite/negative falls back to the `<10` colour.
  - `windHeatGradient(speeds)` — one stop per sample at `i/(n−1)·100 %`; `n < 2` → flat two-stop;
    empty never throws and never emits `NaN`.
- **Per day block**: exactly one `.day-heat` child (inside the block → it translates with the tape),
  **6 px** tall, `blockWidth − 6` wide (3 px inset each side), radius **3 px**, **24 hourly stops**
  (the 15-min frames sampled at `hh:00`). Built in `renderTimeline()` — no per-frame work.
- **Scroll proof**: after one scrub step the block moved −13.8 px and the ribbon −13.8 px →
  **delta 0.00 px**.
- **Palette verified across the tape**: all five tiers present — `rgb(16,185,129)`, `rgb(245,158,11)`,
  `rgb(249,115,22)`, `rgb(239,68,68)`, `rgb(8,145,178)`. Blocks 4–6 are single-colour because those
  days are genuinely calm (<10 mph all day) — correct data, not a rendering gap.
- Block 0 gradient head: `linear-gradient(90deg, rgb(16, 185, 129) 0%, rgb(16, 185, 129) 4.34783%,
  rgb(245, 158, 11) 8.69565%, …)`.

## 2. Day blocks & typography

- Tones measured exactly: **`rgb(35,39,46)` = `#23272e`** and **`rgb(27,29,34)` = `#1b1d22`**,
  adjacent-alternating (`[16] tones-ok=True`); crisp 1 px divider `#4a5568` at each midnight.
- Rows: header **600 12 px** (top 3 px) · ticks **11 px `#94a3b8`** (top 19 px) · winds
  **700 12 px `#f8fafc`** (top 33 px) · heat strip 6 px at bottom 3 px. Midnight/edge ticks stay
  brighter `#e8f0f7` by design.
- Both label rows now use a **shared 20 px centred box** (was `1.5em`) so the mixed font sizes keep
  identical centres → worst tick-vs-wind delta **0.01 px**.
- **Bigger type did not re-introduce collisions**: ink gaps **24h 39.0 px / 7d 11.5 px**, zero
  overlap, per-block minimum 11.5–19.9 px (gate floor is 6 px).

## 3. Calm floor → `#0891b2`

- `HS_STOPS[0]` = `CALM_RGBA` = **`#0891b2`** `[8,145,178,255]`; `OVERLAY_OPACITY` stays **0.68**.
  The 1.0 ft stop remains `#06b6d4`, so the **0–1 ft gradient is restored** (5N's flat band is gone).
  Legend head: `rgb(8, 145, 178) 0%, rgb(6, 182, 212) 16.7%, …`.
- Measured forced-calm composite: **`rgb(77, 170, 192)`** (lum 152; predicted ≈`rgb(71,165,187)`) —
  bright turquoise/teal.
- Label legibility: 184 lake-label pixels — contrast **39.4 % (bare) → 19.1 % (tinted)**,
  fidelity **r = 0.999**.

## Gates (orchestrator runs on the final tree)

| gate | result |
| --- | --- |
| node suites `parity/wind/render/ui` | 4/4 exit 0 (incl. the new `windHeatColor` tier-boundary and `windHeatGradient` shape tests) |
| `tools/qa/stage5_check.py` | **24 ok / 0 FAIL** |
| `tools/qa/live_smoke.py` | **10 ok / 0** (7d tape=2310, blocks=7, all 7 headers read) |
| `tools/qa/scrub_bench.py` | 24/24 checks PASS — medians **16.62 / 16.68 / 17.77 ms**, **0 long tasks**, swaps 10, `idx 42 == expected 42` |
| physics diff vs `main` | **0 lines** |
| `verify5o.py` (independent) | **16 ok / 0 FAIL** |

Key gate lines: `[16] … 7d tape=2310.0 blocks=7 subs=[8×7] alt=True tones=['rgb(27, 29, 34)',
'rgb(35, 39, 46)'] tones-ok=True`; `[18] … 5n gaps 24h=39.0>=6=True 7d=11.5>=6=True
overlap=False/False | 5o rows heat-count=True size=True stops=True colours=True fonts=True scroll=True`;
`[17] moves=31 swaps=10<=12 long-max=0<=50 idx=42 expected=42`.

## Honest notes

1. **One gate clause was adapted (disclosed by the worker, verified here).** The spec's "≥ 2 distinct
   tier colours per block" is unsatisfiable on a genuinely calm day (blocks 4–6 sample uniformly
   <10 mph). Rather than lower a numeric threshold it now asserts a **stricter** per-block
   `stops == 24`, with tier variety asserted **tape-wide** — all five tiers present. I re-derived the
   per-block tier sets independently and confirm the single-colour blocks are the calm days.
2. My verifier's `A5` first read the **edge** tick's colour (`#e8f0f7`) instead of a regular tick
   (`#94a3b8`) — my probe grabbed `.day-sub[0]`, which is the midnight tick by design. Test-side,
   fixed; both tick treatments are now asserted.
3. The worker's first `[17]` harness run showed `swaps=23, long-max=51` under machine contention; my
   quiet-machine re-run gives `swaps=10, long-max=0` (gates ≤12 / ≤50), consistent with every prior
   stage. No regression.
4. `src/render.js`'s 5H decoupled scrub path has **zero** changed lines referencing
   `scrubUiTo` / `scheduleMapPaint` / `endScrub` / `shouldPaintMap`.
5. `tools/qa/live_smoke.py` was not touched (no pinned value broke).

Changed files: `index.html`, `src/ui.js`, `src/render.js`, `tests/ui.test.js`, `tests/render.test.js`,
`tools/qa/stage5_check.py`, `docs/BUILD-SPEC-STAGE5O.md` (+ evidence in `tmp/5o-shots/`).
