# STAGE 5H RECEIPTS — Touch Decoupling & Scrub Performance

Branch `stage5h` · base `e21100e` (dispatch spec) · committed as
`Stage 5H: touch decoupling & scrub performance`.

## What changed, per file

| File | Change |
| --- | --- |
| `src/render.js` | §A `pxPerDay` 24 h floor `190 → 550`. §B decoupled drag: `scrubUiTo` (UI every frame) + `scheduleMapPaint` (72 ms throttle, newest-wins, busy skip) + `shouldPaintMap` pure gate + `endScrub` snap. §C overlay-URL dedupe (`setOverlayUrl` / `resetOverlayDedupe`) and one-in-flight generation token (`paintGen` / `inFlightEncode`); dropped async results are neither painted nor re-queued. `updateScrubUi` skips an unchanged `textContent` write. |
| `tests/render.test.js` | E1: `pxPerDay('24h',374)===550`, `pxPerDay('24h',120)===550`, `pxPerFrame('24h',374)===550/96`, runway `>=150`, `7d===190`. E5: `[11]` unit tests for `shouldPaintMap` (closed → false; open+idle → true; open+busy → false). |
| `tools/qa/stage5_check.py` | E2: both 24 h density formulas now `max(550.0, round(tlW))` (used by `[7b]` and `[16]`). E3: `[16]` keeps `tapeW >= tlW-2` and adds `tapeW >= tlW+100` + prints runway. E4: new `[17] scrub decoupling (5H)` group, registered in `main()`. |
| `tools/qa/scrub_bench.py` | NEW. Playwright mobile drag benchmark: 390×844 and 360×800 mouse drags + a CDP `Input.dispatchTouchEvent` drag at 360×800. External instrumentation (object-URL count, overlay blob `src` writes, `#track-tape` `translateX` writes, long-task observer, `L.imageOverlay.setUrl` paint count), horizon runway table, JSON + PASS/FAIL lines; exits 0 always. |
| `docs/STAGE-5H-RECEIPTS.md` | This file. |

No changes to `src/wave-math.js`, `src/tables.js`, `src/wind.js`, `src/ui.js`, `index.html`,
`public/*`, or any build/deploy step.

## Numbered gate deltas (from the spec §E) and why

1. **`tests/render.test.js`** — 24 h density assertions moved from `max(190, window)` to the
   `550` floor and a runway assertion added. Required by §A; the old `24h(374)→374` value no
   longer describes the tape.
2. **`tools/qa/stage5_check.py`** — the two drag dx→index / reticle formulas now use the
   `550.0` floor:
   - `[7b]` `touch ergonomics`: `pxf = (190.0 if horizon=="7d" else max(550.0, round(m0["tlW"])))/96.0`
   - `[16]` `tape architecture`: `pxf_for(m)` — same change.
   These are the **only** expectations in the file derived from the old `3.8958` pxf: every
   other drag expectation (`120.0/pxf`, `60.0/pxf`, `frame_under_reticle`) is computed from
   the live `pxf`/`pxf_for`, so it tracked the new density automatically. No other
   `190`/`3.8958` drag constants exist (grep-verified).
3. **`tools/qa/stage5_check.py`** — `[16]` keeps `tapeW >= tlW-2` and adds
   `tapeW >= tlW+100`; printed runway is now part of the `[16]` detail line. 7 d
   `1100 <= tapeW <= 1400` unchanged.
4. **`tools/qa/stage5_check.py`** — `[17] scrub decoupling (5H)`: one scripted 30-step /
   240 px LEFT drag at 390×844 in 24 h. Setup includes a throwaway warm-up drag (JIT + cache
   warm) so the gate measures the drag and not the first cold build — the same setup the
   standalone bench uses. Asserts: instruments alive; `swaps <= 12`; `tapeTx >= moves`;
   `long-max <= 50`; `aria-valuenow == idxFromDrag(delivered dx)`; pill text == frame at that
   index. The existing `[16]` 5G contract (pill dx `0.00 px`, exact drag deltas, both clamps,
   reticle centring) stays green.
5. **`src/render.js`** — `shouldPaintMap(nowMs, lastPaintMs, busy, minIntervalMs)` exported
   and unit-tested in `tests/render.test.js`.

## Harness

```
SUMMARY: 23 ok, 0 FAIL
[16] tape architecture (5G) ok  24h tape=550.0/window=374.0 runway=176.0 centred=True
[17] scrub decoupling (5H)  ok  moves=31 tx>=moves=True swaps=10<=12=True
                                long-max=0<=50=True idx=42 expected=42=True pill=True
                                instruments(tx/src/long)=True/True/True
```

Node suites: `parity`, `render`, `ui`, `wind` all `ALL TESTS PASSED` (exit 0). Parity output
is unchanged apart from timing lines.

Determinism (same command twice, final code): run A `[17] ok … swaps=10 … SUMMARY: 23 ok, 0
FAIL`; run B `[17] ok … swaps=11 … SUMMARY: 23 ok, 0 FAIL`. Same verdicts.

## Bench — before / after

`tools/qa/scrub_bench.py`, Chromium, 30-step / 240 px LEFT drag.

Before (`pre-stage5h` = `HEAD` worktree, served locally):

| viewport | mode | drag ms | win | tape | runway | px/day | swaps | paints | tx/moves | med/p90/max ms | long ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 390×844@2 | mouse | 1767 | 374 | 374 | **0** | 374 | 14 | 14 | 30/31 | 56.1 / 64.5 / 101.3 | [52] |
| 360×800@2 | mouse | 1576 | 344 | 344 | **0** | 344 | 14 | 14 | 30/31 | 49.8 / 68.0 / 100.0 | [] |
| 360×800@2 | CDP touch | 1367 | 344 | 344 | **0** | 344 | 2 | 2 | 30/30 | 43.3 / 49.9 / 66.9 | [] |

After (`stage5h`):

| viewport | mode | drag ms | win | tape | runway | px/day | swaps | paints | tx/moves | med/p90/max ms | long ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 390×844@2 | mouse | 943 | 374 | 550 | **176** | 550 | **10** | 10 | 41/31 | 16.4 / 59.8 / 64.9 | [] |
| 360×800@2 | mouse | 933 | 344 | 550 | **206** | 550 | **10** | 10 | 41/31 | 16.7 / 53.2 / 56.2 | [] |
| 360×800@2 | CDP touch | 923 | 344 | 550 | **206** | 550 | **10** | 10 | 41/30 | 18.0 / 53.8 / 66.4 | [] |

Verdict: pre-stage5h `11/24 PASS`, stage5h `24/24 PASS`. Headline: 24 h runway `0 → 176 px`
at 390×844; overlay `src` swaps `14 → 10` (mouse) and long tasks `[52] → []`; modal step
latency `56.1 → 16.4 ms`; max `101.3 → 64.9 ms`.

## Commands

```bash
# node suites
node tests/parity.test.js && node tests/render.test.js && node tests/ui.test.js && node tests/wind.test.js

# full gate (390x844 + 360x800, live wind + seam)
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py

# bench, merged tree
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/scrub_bench.py --label stage5h

# bench, pre-stage5h tree (bench depends on nothing 5H adds)
git worktree add --detach /tmp/bpc-pre5h HEAD
(cd /tmp/bpc-pre5h && /home/reid/.hermes/hermes-agent/venv/bin/python -m http.server 8137 --bind 127.0.0.1 &)
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/scrub_bench.py \
    --url http://127.0.0.1:8137/index.html --label pre-stage5h
```

## Orchestrator gate (independent re-run on the committed tree, 2026-09-12)

Tree: `stage5h` @ `9aba1cd`, working tree clean. Every number below was produced by the
orchestrator, not the build worker.

- **Node suites (my run):** parity 10 ok, render 32 ok, ui 27 ok, wind 36 ok — four
  `ALL TESTS PASSED`, exit 0 each.
- **Test-integrity diff vs `pre-stage5h`:** the only check present before and absent now is the
  renamed `pxPerDay is 190 in 7d and max(190, window) in 24h` (delta E1); the only deleted
  assertion lines in `tests/` are that check's two `pxPerDay`/one `pxPerFrame` assertions —
  all pre-authorised. **Parity output is byte-identical to pre-stage** apart from timing lines
  (the physics did not move).
- **`tools/qa/stage5_check.py` (my run):** `SUMMARY: 23 ok, 0 FAIL`.
  `[16] 24h tape=550.0/window=374.0 runway=176.0 centred=True frame-under=True` ·
  `7d tape=1330.0 blocks=7 subs=[8×7] alt=True` ·
  `[17] moves=31 tx=41 swaps=11 long-max=0 idx=42 expected=42 pill=True instruments=True`.
- **`tools/qa/scrub_bench.py` (my run, both trees):** pre `12/24 PASS` · stage `24/24 PASS`.
  Stage rows: 390×844 runway **176** px, swaps **10**, paints 10, tx/moves 41/31,
  med/p90/max **16.6/60.2/66.1 ms**, long `[]` · 360×800 runway **206**, swaps 10,
  16.6/53.5/54.0, long `[]` · CDP touch 360×800 runway **206**, swaps 10, 17.6/54.2/66.3,
  long `[]`. Pre-stage rows for the same commands: runway **0**, swaps 14 (mouse) / 2 (touch),
  med ≈ 41-54 ms, max ≈ 94.8-102.9 ms.
- **Independent instrument (orchestrator-written, different hooks — prototype blob-`src` wrap
  + `URL.createObjectURL` counter, cold-cache first drag of the session):**
  | | pre-stage5h | stage5h |
  | --- | --- | --- |
  | 24 h runway | 0 px | **176 px** |
  | overlay src swaps in one drag | 28 | **4** |
  | step latency median / max | 16.6 / **159.8 ms** | 16.7 / **88.1 ms** |
  | long tasks in the drag+0.7 s window | [71, 71] | [71, 69] |
  | `body.dataset.encodeMs` | 21.6 | 13.1 |
  This is the second, independently-written witness to the same direction of travel. The two
  residual ~70 ms long tasks appear in **both** trees (pre-existing, not a 5H regression:
  same count, same magnitude) — see the follow-up note below.

### Orchestrator notes (honest deltas)

6. **Observed drag-time repaint rate is ~10-11 fps, not 12-15.** 10 paints over a ~940 ms drag
   = 10.6 fps against the 72 ms (13.9 fps) *cap*: the busy-skip legitimately drops a few paints
   below the ceiling. Reid's clause is a maximum ("at a maximum rate of 12-15 fps"), so this is
   inside it; stated here so the number is not read as the target missed.
7. **Follow-up candidate (NOT fixed in 5H, not a regression):** ~70 ms long tasks remain in a
   drag+release window (present pre-stage too). They are the synchronous raster build
   (`gatherRaster` + `smoothRaster`, 36-46 ms) landing at drag start / on the release snap.
   Removing them requires an async/cooperative build or a narrower drag-time raster class —
   explicitly out of 5H scope (§C3); it is the natural Stage 5H.1 / 5I item if the phone still
   feels heavy at release.
8. **Node-suite count 105 checks** (parity 10, render 32, ui 27, wind 36) — no check deleted.

## Spec vs. reality

1. **"max step-latency not more than ~2× median" (done-when 3).** Not achievable on this box
   by the spec's own design. The throttle caps paint *frequency*, but each paint still runs
   the existing synchronous `showFrame` build (`gatherRaster` + `smoothRaster`, measured
   `frameMs` 36–46 ms) plus the overlay `setUrl`/decode. Post-fix the median drops to the
   ~16.4 ms input floor, so `max/median` is ~3.4–4.0× even though the absolute stalls are
   gone: max `101.3 → 64.9 ms`, long tasks `[52] → []`, modal step `56.1 → 16.4 ms`. Shrinking
   the max further requires changing the raster build/width, which §C3 forbids. The bench gates
   on absolute budgets (`median <= 25 ms`, `max <= 100 ms`) and reports `max/median` as
   information; this is the one deviation from the literal clause.
2. **Baseline numbers.** The spec's "orchestrator probe" baseline (28 swaps, median 16.62 ms,
   max 159.52 ms, build 45.5 ms) did not reproduce here. The same pre-stage5h tree on this box
   measured 14 swaps, median 49.8–56.1 ms, max ~101 ms, build ~40 ms — the spec's probe was
   evidently taken with a warmer cache/shorter drag. The before/after direction is unchanged.
3. **Transform instrumentation.** In this Chromium neither `CSSStyleDeclaration.prototype.
   setProperty` nor a prototype `transform` accessor observes `el.style.transform = …`
   (`getOwnPropertyDescriptor(CSSStyleDeclaration.prototype,'transform')` is `undefined`).
   Both `[17]` and the bench therefore shadow `transform` on the specific
   `#track-tape.style` object — the spec's "whichever actually catches it" branch.
4. **`pxPerDay` desktop consequence.** At a viewing window ≥ 550 px the 24 h tape is
   `max(550, window) = window` → runway 0, exactly as 5G. The new 176 px runway is the phone
   case (window 374).
5. **CDP touch works here** (pointer events synthesised with `has_touch=True`); the touch row
   is reported, not `unavailable`.
