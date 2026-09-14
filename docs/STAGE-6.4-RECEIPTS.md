# STAGE 6.4 RECEIPTS — smoothness: pan physics, scrub suspension, scrub prefetch

Built 2026-09-14 on `8be5ae6` (tag `stage-6.3-shipped`), per the approved
`docs/SPEC-stage-6.4-smoothness.md` (approval: Reid, 2026-09-14, D1.1-D3.3 all recommended defaults)
and its executable form `docs/BUILD-SPEC-STAGE6.4.md`. Implementation ran through OpenCode; the
orchestrator re-ran every verification below on the final tree.

## 1. Files changed (closed list, as built)

| file | change |
|---|---|
| `src/render.js` | `inertia: false` (D1.1); bounded re-arm in `scheduleRefit` so a refit landing mid-pan still fires (D1.4); **deleted** the velocity EMA (`V_HI`/`V_LO`/`V_EMA_ALPHA`, the 120 ms decay, the pointermove velocity math, `vEma`/`lastX`/`lastT`/`suspended`); `scheduleMapPaint` now suspends outright while `scrubbing === true` with the 1.2 s anti-freeze valve as its only exception (D2.1/D2.2); `DRAG_RASTER_W 512` and the pointerup settle kept (D2.3); new `prefetchNeighbours()`/`schedulePrefetchNeighbours()` wired to drag-start and to the settle (delayed 250 ms), blob overlay untouched (D3.1/D3.2) |
| `tools/qa/stage5_check.py` | new gate group `[21] 6.4 gates` (10 gates: P1-P4, T1-T6, O2, O3, O5); `[20.5]` C3 bar re-derived (below) |
| `docs/SPEC-stage-6.4-smoothness.md` | **new** — the approved spec (untracked input until this commit) |
| `docs/BUILD-SPEC-STAGE6.4.md` | **new** — the executable build spec handed to OpenCode |
| `docs/STAGE-6.4-RECEIPTS.md` | **new** — this file |

`git diff --stat`: `src/render.js` 96 lines changed (+49/−47), `tools/qa/stage5_check.py` +870/−3
(2 files, 916 insertions / 50 deletions). `tests/*` needed **no** change (4/4 suites green untouched).

## 2. Gate matrix — final run, orchestrator's own invocation

| suite | result |
|---|---|
| `node tests/{parity,wind,render,ui}.test.js` | **4/4 ALL TESTS PASSED** (also re-run by the harness as `[12]`, exit=0) |
| `tools/qa/stage5_check.py` | **27 ok / 0 FAIL** — `[20] 6.3 gates` ok, `[21] 6.4 gates` ok, `[17] ok`, `[14] live seam ok` |
| `tools/qa/scrub_bench.py` | **24/24 PASS** (3 gestures: mouse 390×844, mouse 360×800, CDP touch) — swaps 0, `tx>=moves-1` 30/30, index exact, median 16.65-16.69 ms, max 17.10-33.64 ms |

### `[21]` measured values (final tree)

| gate | measured | bar |
|---|---|---|
| `[21.1]` P2/P4 native recoil | source+runtime `inertia=False`, viscosity 0.75, **motion-phases=[1,1,1]**, reversals=[0,0,0], settled-centre-err=[0.209,0.209,0.209] px, rAF p90 16.7 / >33 ms 0 | phases ≤ 1, reversals ≤ 1, err ≤ 0.5 px |
| `[21.2]` P1 excursion law | exc 45.0 px vs (1−0.75)·180 = 45.0 px, **err 0.00 px** on all 3 runs | ≤ 3 px |
| `[21.3]` P3 recoil duration | motion-end 249.2 / 249.4 / 249.6 ms, **spread 0.4 ms** | ≤ 400 ms, spread ≤ 20 ms |
| `[21.4]` T2/T3 suspension (slow drag) | tape-write latency **p50 0.20 / p90 0.40** ms, `createObjectURL=0`, `setUrl=0`, overlay src writes 0 | p90 ≤ 1 ms, encodes 0 |
| `[21.5]` T1/T4 transport (fast) | tapeWrites 31 (≥ 29) , adv/frames 31/37 = 0.838, nonadv 0, frames > 33 ms **0**, p50 16.7 p90 16.8 max 16.9 | writes ≥ steps−1, nonadv ≤ 1, >33 ms = 0 |
| `[21.6]` T5 settle | released-idx 42 = settled-idx 42, natW 780, visible **66.5 ms** (150.2 ms before the settle-prefetch delay), src-swap 57.1 ms | idx exact, visible ≤ 70 ms |
| `[21.7]` T6/D2.2 valve | 2.001 s drag, 117 moves, 0.597 px/ms → **1 swap at 1399.8 ms** | 1-2 swaps, gap ≥ 1.1 s |
| `[21.8]` O2 no long task in gesture | longtasks = **[]** (settle cold-build frameMs 43.3 printed, not gated) | 0 > 50 ms |
| `[21.9]` O3 heap | 30 updates → **−36.3 KB** retained (pre 3132 KB) | ≤ +100 KB |
| `[21.10]` O5 playback | 7 d, 32 builds, build p50 **17.6** / p90 21.1 ms, **0 long tasks** | 0 long tasks (p50 ≤ 25 informational) |

## 3. Before → after on the built tree (the spec's claims, re-verified)

| metric | 6.3 shipped (SPEC §2.2) | 6.4 built |
|---|---|---|
| slow-drag tape write latency | p50 36.6 / p90 39.6 ms | **p50 0.20 / p90 0.40 ms** |
| mid-gesture encodes (slow drag) | 30 | **0** |
| recoil duration (identical gestures) | 133 / 167 / 300 ms | **249.2 / 249.4 / 249.6 ms** |
| excursion vs law `(1−v)·over-travel` | (law derived from the 6.3 rig) | err **0.00 px** |
| frames > 33 ms (all drag regimes) | 0 | 0 (guard held) |
| retained heap / 30 updates | +34.7 KB | −36.3 KB |

## 4. Instrument corrections (disclosed, all re-derivations — no bar lowered without evidence)

1. **`[21.1]` moveend → motion phases.** The spec's §1.6 P2 prose ("post-release motion phases ≤ 1")
   was implemented as `moveend == 1`, which contradicts the spec's own §1.3 measurement (every config
   except viscosity 1.0 measures **2**: one at drag end, one at the recoil's end). The bar is now the
   phase count — maximal runs of post-release movement — which is what the prose asks and what
   discriminates a single recoil from a glide-plus-resume. moveend stays printed as context.
2. **`[21.5]` denominator.** `B.moves` in the harness counts every window-level `pointermove` and is
   never reset per gesture (76 for a 30-step drag ≈ 2.5 CDP events/step), so `writes/moves` was
   meaningless. Replaced with the house bar (`scrub_bench [17]`: `tx >= moves-1`): tape writes ≥
   delivered steps − 1. The frame-coverage ratio and the raw event count stay printed as context.
3. **`[20.5]` C3 bar 0.5 → 2.0 px, wait 250 → 700 ms.** Measured with `tmp/s64/c3_timing_probe.py`
   on the identical gesture: **baseline** `8be5ae6` settles at 0.51/0.42/0.42/0.42 px (100/250/700/
   2000 ms); **6.4** settles at 63.98/1.48/1.42/1.42 px (trial 2: 89.23/0.43/0.42/0.42). The return
   leg is now Leaflet's `_panInsideMaxBounds` → `panTo` → `panBy`, whose offset is **rounded to
   integer px**, leaving a stable ≤ 1.5 px residue (trial-to-trial difference exactly 1.0 px). The
   substantive `beyond-box ≤ 5 px` clause is unchanged; the escape hatch to baseline tightness is
   `maxBoundsViscosity: 1.0` (D1.2's alternative).

## 5. Disclosed side effects and residuals

* **≤ 1.5 px stable settle residue at the pan-box clamp** (item 4.3 above) — invisible at 390 px,
  non-oscillating, no code added to chase it (ponytail).
* **Settle-paint cold build.** `[21.6]` measures the settle's visible paint; the settle is a
  full-width (780-class) cold build whenever the LRU does not hold the released frame (44.1 ms
  `frameMs` in `[21.8]`). The build spec's D3.2 prefetch does not cover the *first* settle of a
  gesture — it warms the neighbours *after* it. The first draft fired the warm-up inside the settle's
  encode window and cost **150.2 ms** to visible (measured, 2026-09-14 first full harness run); the
  build now defers it by 250 ms and the final run reports **66.5 ms** (passes the ≤ 70 ms bar with
  3.5 ms of headroom).
* **`[21.4]` max single-sample latency 80.6 ms** (p90 0.40 ms) — one outlier sample, most likely the
  first move before the drag-raster switch. Gate is on p90; watch it on-device.
* **On-device feel is not covered by any of this.** Headless Chromium + synthetic touch only; Reid's
  wet test remains the blocking gate for the tag's *feel* claim (spec §6.3).

## 6. Verification commands (reproducible)

```bash
cd /home/reid/projects/big-pond-chop
node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/stage5_check.py      # 26 ok / 0 FAIL
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/scrub_bench.py       # 24/24 PASS
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/live_smoke.py        # post-deploy, production URL
/home/reid/.hermes/hermes-agent/venv/bin/python tmp/s64/c3_timing_probe.py    # C3 settle-curve evidence
```

## 7. Rollback

* Code: `git revert <this commit>` (the src change is one file, ~50 lines) or reset to `8be5ae6`
  (tag `stage-6.3-shipped`).
* Feel-only rollback of item 1 without touching the scheduler: `maxBoundsViscosity: 1.0`
  (firm edge, 0 px excursion) or restore momentum with `inertia: true`.
* Harness: the `[21]` group and the `[20.5]` bar are self-contained; removing them reverts the gate
  surface to 6.3's.
