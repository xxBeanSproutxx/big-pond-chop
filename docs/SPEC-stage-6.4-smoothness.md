# SPEC — Stage 6.4 smoothness: pan physics, scrub transport decoupling, persistent-canvas overlay

**Status: DRAFT FOR APPROVAL.** No production file has been touched. Baseline `origin/main` ==
`8be5ae6` (tag `stage-6.3-shipped`), git tree clean. Every number below is measured on that tree by
four throwaway rigs (`tmp/64-smoothness/`, gitignored) — see §4 for the method and the one rig that
failed to produce artifacts.

Two headline corrections to the brief's premises, both measured, both in §1 and §3:

1. **Inertia does not fight `maxBoundsViscosity` on the main thread, and there is no frame-level
   jank to fix at the pan box.** 72 runs, rAF p50 **16.7 ms**, p99 **16.8 ms**, zero frames > 33 ms,
   zero long tasks. What exists is *positional*: a 4:1 finger-to-map slip at the edge and a recoil
   whose duration varies **133 → 300 ms** across identical gestures.
2. **The blob → `<img>` overlay pipeline is not the bottleneck.** Encode + object URL + decode
   ≈ **3.2 ms** per update against a **41.4 ms** synchronous cold frame build. Item 3's rewrite
   targets ~10 % of the cost.

---

## 0. Scope, sequencing, non-goals

| # | Item | Risk | Reversible by |
|---|------|------|---------------|
| 1 | Leaflet inertia / viscosity deconfliction — `L.map()` options only | low (feel) | revert the options block (`src/render.js:604-612`) |
| 2 | Scrubber transport: suspend lake-map paints while the finger flies | low | revert `scheduleMapPaint` + the gate constants (`src/render.js:23-30, 793-836`) |
| 3 | Evaluate a persistent canvas overlay vs the blob → `<img>` swap | medium (rendering path) | nothing to revert if D3.1 is "keep the blob path" |

**Sequencing:** 1 → 2 → 3. Item 1 is an option change. Item 2 changes the paint scheduler. Item 3, as
recommended (**keep the blob path, attack the build instead**), is a smaller change than the brief
assumed; a canvas-layer rewrite is offered as an alternative with its measured price (§3.5).

**Non-goals:** no visual redesign; no data pipeline changes; no iOS Safari or real-touchscreen claims —
every mobile statement here is headless Chromium with synthetic touch (§4), and the on-device pass
(§6.3) stays the blocking gate before any tag.

---

## 1. Item 1 — Leaflet inertia & viscosity deconfliction

### 1.1 Live configuration (read back from the running map, not assumed)

| option | live value | Leaflet 1.9.4 default (source) |
|---|---|---|
| `inertia` | `true` | `true` (§13720) |
| `inertiaDeceleration` | **`3400`** px/s² | `3400` (the code comment says 3000 — the value is what runs) |
| `easeLinearity` | `0.2` | `0.2` |
| `inertiaMaxSpeed` | `Infinity` | `Infinity` |
| `maxBoundsViscosity` | `0.75` (`src/render.js:611`) | `0.0` |
| `zoomSnap` / `zoomDelta` | `0.1` / `0.5` | `1` / `1` |

The app never sets `inertia`, so Leaflet's momentum engine is live. **At the fit zoom the pan box is
tight: on a 390 px viewport the box spans container x −55 … 445, i.e. only ±55 px of pan slack** — any
gesture longer than ~55 px reaches the bound, which is why all four measured scenarios exercise the edge.

### 1.2 Mechanism (traced in `leaflet-src-1.9.4.js`)

| phase | code | behaviour |
|---|---|---|
| drag follow | `_onDrag` → `Draggable` → `panBy(movement, {animate:false})` | raw per-move transform, 1:1 with the finger |
| viscous limit | `_onPreDragLimit` (§13852): `off − (off − limit)·viscosity` | recomputed per move from the gesture start; **the map follows only `1 − viscosity` of the over-travel** (0.75 → 25 %; 4:1 slip) |
| release (inertia on) | `_onDragEnd` (§13880): samples pruned to **50 ms**; `speed = 0.2·v`; `duration = v/3400` s; `offset = speed·duration/2` → **`glide_px ≈ 0.1·v²/3400`** | then the total offset is **hard-clamped** into the box by `_limitOffset` (§13911) — viscosity does *not* apply on release — and run as one CSS `PosAnimation` with quintic ease-out (`1/0.2 = 5`) |
| release (inertia off) | `_onDragEnd` → `moveend` | no pan; the view is left out of bounds |
| recoil | `setMaxBounds` (§3559) registers `_panInsideMaxBounds` on **every `moveend`** (§3577), and fires it **immediately on every call** | if the view is outside the box, one **0.25 s** default-ease `panTo` runs (§3616-3627) — a *second* animation, on a different easing and clock from the glide |

**Verified law (see §1.3): `excursion = (1 − viscosity) × over-travel`.** With viscosity 0.75 a
180 px drag leaves the box by exactly 45 px; 0.25 leaves it by 135 px; 1.0 by 0 px.

### 1.3 Measured matrix — 390×844 @ DSF 2, synthetic CDP touch, N = 3, 72 runs

Configs mutated at runtime and **read back** (C1 `inertia:false`, C2/C3 `inertiaDeceleration`
6000/12000, C4 `maxBoundsViscosity` 1.0, C5 0.25) — all six read-back rows confirmed in `RESULTS.json`.

| cfg | S1 flick | S2 flick→edge | S3 slow hug | S4 rubber-band hold | recoil duration (same gesture, N=3) |
|---|---|---|---|---|---|
| **C0 shipped** | 45 px | 46 px | 61 px | 31 px | **133.3 / 166.6 / 299.8 ms** |
| C1 `inertia:false` | 45 | 46 | 61 | 31 | **283.0 / 283.1 / 283.2 ms** |
| C2 decel 6000 | 45 | 46 | 61 | 31 | 16.6 / 16.6 / 16.7 ms |
| C3 decel 12000 | 45 | 46 | 61 | 31 | 16.5 / 16.6 / 16.7 ms |
| **C4 visc 1.0** | **0** | **0** | **0** | **0** | 16.6 / 16.6 / 16.8 ms |
| C5 visc 0.25 | 135 | 136 | 181 | 91 | 16.4 … 16.6 ms |

(Excursion = peak pane-x beyond the clamped edge, median of 3 — min == max in every cell. Recoil
duration from the pointerup-anchored probe; the matrix's own `settleMs` floors at ~366 ms and cannot
resolve this term — disclosed in the rig notes.)

**Law check — over-travel inferred as `excursion/(1 − viscosity)` vs the commanded drag:**

| scenario | commanded drag | inferred over-travel (C0) | error |
|---|---|---|---|
| S1 | 180 px | 180 px | 0 % |
| S2 | 180 px | 184 px | +2 % |
| S3 | 240 px | 244 px | +2 % |
| S4 | 120 px | 124 px | +3 % |
| S1 @ viscosity 0.25 (C5) | 180 px | 180 px | 0 % |

**Other metrics, all 72 runs:** rAF p50 16.7 / p90 16.7 / p99 16.8 / max 16.8 ms; frames > 33 ms = **0**;
frames > 50 ms = **0**; long tasks = **0**; direction reversals = **0**; `moveend` = 1 for C4, 2 for
every other config (two move ends ⇒ the glide and the recoil are separate motion phases).
Realized gesture velocities: 599-603 px/s (S1/S2/S4), 399-401 px/s (S3) — in-band.
Footnote: the rig's `noOpShare 0.53` is an artifact of paced synthetic moves (gaps between injected
samples), **not** jank — the pane is step-wise by integer-pixel rounding.

### 1.4 What the numbers say (the deconfliction answer)

* **No main-thread fight exists.** Inertia and viscosity do not contend for the main thread in any
  measurable way: 0 long tasks, 0 dropped frames, CV 0.000, across the full config matrix. The brief's
  "stutters because inertia fights viscosity on the main thread" is **not supported** by measurement.
* **Viscosity is the edge lever.** It alone determines how far the map leaves the box
  (0 / 31-61 / 91-181 px at 1.0 / 0.75 / 0.25) and therefore how far it must come back.
* **Inertia is the release-tail lever only.** C0 ≡ C1 ≡ C2 ≡ C3 are *bit-identical* on every
  excursion and post-release-distance metric — the excursion is created during the drag, so momentum
  has no leverage on it. Inertia's measurable effect is the **duration and variability** of the recoil:
  133-300 ms and variable at the default, **283.0-283.2 ms and fixed** with `inertia:false`, and a
  **single-frame teleport** at decel 6000/12000 (45 px inside one frame — the clamp correction is
  squeezed into a speed-derived window that is far too short for it).
* **The shipped defect is the variable-duration recoil, not the frame rate.** Same gesture, three
  runs, three different return durations (133 / 167 / 300 ms) — that is what reads as "the map fights
  the boundary".
* **Caveat:** headless Chromium on an 8-core box is not a phone. On-device thermal/compositor jank
  cannot be ruled out here; §6.3 stays the arbiter.

### 1.5 Proposed design

| option | change | measured consequence |
|---|---|---|
| **(A) recommended** | `inertia:false`, keep `maxBoundsViscosity: 0.75` | glide removed; one smooth, **fixed-duration 283 ms** recoil (Leaflet's own `panInsideBounds` 0.25 s ease); no speed coupling, no second animation |
| (B) firm edge | `inertia:false` + `maxBoundsViscosity: 1.0` | the map never leaves the box (0 px), `moveend` 1, no recoil animation at all; drag tracking becomes "map stops, finger keeps moving" |
| (C) keep momentum | `inertia:false` is dropped, `inertiaDeceleration: 3400` (as shipped) | keeps the small interior glide (10.6 px at 0.6 px/ms; 118 px at 2 px/ms) but restores the 133-300 ms variable recoil |
| (D) steepen deceleration | `inertiaDeceleration: 12000` | recoil becomes a **45 px single-frame jump** — rejected: a teleport is not smoothness |

Option A matches the brief ("track the touch point 1:1", "elastic recoil without oscillatory
shuddering") and is one option line. If Reid prefers the map to feel firm rather than springy, B is
the same diff with one extra digit.

### 1.6 Item-1 gates

* **P1** edge slack: with viscosity 0.75, measured excursion `= (1 − viscosity) × over-travel` ± 3 px.
* **P2** post-release motion phases ≤ **1** (`moveend` ≤ 1 per gesture at the bound; C4 measured 1).
* **P3** recoil duration spread across N = 3 identical gestures ≤ **±20 ms** (shipped config: 167 ms
  spread — fails; C1: 0.2 ms).
* **P4** rAF p90 ≤ 20 ms and frames > 33 ms = 0 in all four scenarios (already true today — guard
  against regression).
* **P5** existing containment gates C1-C4 (`stage5_check.py` group `[20]`) stay green.

---

## 2. Item 2 — Timeline scrubber transport decoupling

### 2.1 Shipped implementation (already partly "suspended")

`scrubUiToMinutes` (781) writes tape + pill **every rAF** from raw pixel deltas; the map paint goes
through `scheduleMapPaint` (793) → velocity gate (`V_HI 0.25` / `V_LO 0.08`, EMA α 0.3, 1.2 s valve,
26-29) → `MAP_PAINT_MIN_MS 72` throttle → newest-wins, one encode in flight → `showFrame`.

### 2.2 Measured by regime — 240 px left drag, N = 3 each, plus a 2.0 s valve run

All three regimes realized in-band: **0.450 / 0.160 / 0.040 px/ms**.

| metric | R-fast (suspended) | R-medium (throttled) | R-slow (throttled) |
|---|---|---|---|
| mid-drag encodes (`createObjectURL`) | **0** | 11 | **30** |
| tape write latency p50 / p90 / max | **0.2 / 0.3 / 16.9 ms** | 0.3 / **38.0** / 40.2 ms | **36.6 / 39.6 / 41.7 ms** |
| pill write latency p50 / p90 | 0.2 / 0.3 ms | 0.3 / 22.7 ms | 0.3 / 0.4 ms |
| rAF p50 / p90 / p99 / max | 16.7 / 16.8 / 16.8 / 16.8 ms | 16.7 / 22.0 / 24.5 / 24.8 ms | 16.7 / 16.9 / **24.0 / 26.0 ms** |
| frames > 16.7 / > 33 / > 50 ms | 0 / 0 / 0 | 19 / **0** / **0** | 64 / **0** / **0** |
| tape writes/s · non-advancing | 56.2 · 1 | 27.9 · 12 | 8.7 · **30** |
| first-move stall | 16.6 ms | 39.6 ms | 38.9 ms |
| release → new overlay blob visible | 12.4 / 27.5 ms | 59.7 / 60.4 ms | 69.5 / 70.3 ms |
| settle paint (app `data-frame-ms`) | 68.3 ms | 40.7 ms | 42.5 ms |
| long tasks > 50 ms | 0 | 0 | 0 |
| drag wall | 534 ms | 1 504 ms | 6 874 ms |

**Valve run** (2.0 s continuous fast drag, 117 moves, 0.598 px/ms): **1** forced paint at 1 404.8 ms
(correct for a 1.2 s re-arming valve), costing one **35.6 ms** frame; 0 long tasks.

### 2.3 Attribution of what remains

Suspension already works at high velocity — R-fast pays **zero** encodes and its writes land in the
same frame (0.2 ms). The residual cost is concentrated in the *throttled* branch, and it is not
frame-dropping (`frames > 33 ms = 0` in every regime): it is **write latency and encoder count**.
At R-slow the tape's response to a pointermove is **36.6 ms late (p50)** — over two frames — because
30 encodes × ~23-40 ms of build work interleave with the gesture on one thread (the 36.6 ms p50 also
equals the ~24-26 ms frame p99 tail). Corroborating: the settle paint (`data-frame-ms`) is 40.7 and
42.5 ms in the throttled regimes against 68.3 ms in R-fast (whose settle is the only full-width build
in the gesture). R-slow is the "heavy under the thumb" case Reid describes, and **R-slow is exactly
what the shipped gate does not suspend** (0.04 px/ms is far below V_HI 0.25).

### 2.4 Proposed design

| option | change | measured expectation |
|---|---|---|
| **(A) recommended** | suspend lake-map paints whenever `scrubbing === true`; keep one anti-freeze paint per 1.2 s and the pointerup settle. This *deletes* the EMA/threshold logic (`V_HI`/`V_LO`/`V_EMA_ALPHA`, the 120 ms decay branch) and the 72 ms throttle on the drag path | tape latency → 0.2-0.3 ms in all three regimes; encodes during a gesture → 0 (1 per 1.2 s at most); drag-time builds → 0; map preview goes stale during the gesture (max 1.2 s) |
| (B) keep the gate, raise the throttle | `MAP_PAINT_MIN_MS` 72 → 150 on the drag path only | halves the encodes (30 → ~15 at R-slow); latency stays tens of ms |
| (C) ship as-is | — | R-slow stays at 36.6 ms p50 tape latency, 30 encodes |

Option A is **less code** than what ships today and is the only variant that reaches the R-fast
numbers in R-slow. Its cost is deliberate: during a slow deliberate scrub the wave map does not
follow until the finger stops. That is a product call — flagged as **D2.1** for approval.

### 2.5 Item-2 gates

* **T1** tape transform advances on ≥ 95 % of rAF frames; pill writes ≥ 55 / s at R-fast, ≥ 25 / s at
  R-slow (the R-slow rate is gesture-bound, not paint-bound).
* **T2** tape write latency p90 ≤ **1 ms** and max ≤ **17 ms** in **all three** regimes (shipped:
  38.0 / 39.6 ms p90 at R-medium/R-slow — fails).
* **T3** `createObjectURL` during a gesture = 0, except ≤ 1 per 1.2 s of continuous drag (valve).
* **T4** frames > 33 ms = 0 in all regimes; the valve's forced paint ≤ 1 frame > 33 ms per valve fire.
* **T5** release → new overlay visible ≤ 70 ms (unchanged from today) and the released frame index
  equals the throttled target (`expectedIdx` gate).
* **T6** `tools/qa/scrub_bench.py` stays green (swaps ≤ 12, latency median ≤ 25 ms, group `[17]`).

---

## 3. Item 3 — Persistent canvas overlay vs DOM image swapping

### 3.1 Shipped pipeline

`frameFor` (1076) → `computeFrame` (236) → `gatherRaster` (213) → `landMaskRaster` (283) →
`smoothRaster` (299) → `paintRaster` (258, sync, into an `OffscreenCanvas`) →
`convertToBlob('image/png')` (275, async) → `createObjectURL` → `overlay.setUrl` (754) → `<img>.src` →
decode → composite. LRU holds **8** entries keyed `idx|pinIdx|W×H`, payload = the blob URL;
`onEvict` revokes it (689).

### 3.2 Measured per-update cost (real app, 30 consecutive cold frames)

| stage | rest class 780×796 | drag/second class | 7 d playback (10 s @ 3 fps) |
|---|---|---|---|
| sync build (`data-frame-ms`) | **p50 41.4 / p90 48.6 / max 74.6 ms** | p50 **23.1** / p90 26.6 / max 40.0 ms | p50 18.9 / p90 25.9 / max 43.7 ms |
| async PNG encode (`data-encode-ms`) | 7.9 / 11.0 ms (off-main-thread) | 4.5 / 6.2 ms | 3.1 / 5.1 ms |
| object URL create+revoke | ~0.4 ms | ~0.4 ms | ~0.4 ms |
| `src` write → load/decode | 0.8 / 0.9 ms | 0.7 / 0.8 ms | 1.7 / 19.8 ms |
| `src` write → post-load composite | 4.4 / 15.4 ms | 5.4 / 6.9 ms | 21.0 / 31.9 ms |
| object URLs created / revoked (30 updates) | 30 / 24 | 28 / 28 | 33 / 33 |
| JS heap retained after GC | **+34.7 KB** (peak 4.77 MB) | +15.8 KB (peak 13.33 MB) | post-GC 3.49 MB |
| long tasks > 50 ms | **3** (max 76 ms) | 2 (56.4, 50.3 ms) | **0** |

**Read:** the synchronous build is **76 % of the wall time and ~90 % of the main-thread work** per
update, and it *is* the long-task source (3 × 50-76 ms in 30 cold updates). Encode + URL + decode
together are **≈ 3.2 ms**, and `retainedAfterGc` is a rounding error — there is no GC-thrash story
here. Playback is clean (0 long tasks, build p50 18.9 ms) precisely because `prefetch()` warms the
next frame off the critical path.

Class caveat (disclosed, not papered over): the rig's dims probe reported `780×796` for the
"during-drag" window while the build cost dropped to 23.1 ms — the row is consistent with the 512-class
drag raster but the exact raster for that burst is **ambiguous**. Treat it as "the drag class, 23-40 ms",
not as a hard 512 datum.

### 3.3 Isolated per-op micro-benchmarks (same page, 780×796, 30 iterations)

| op | p50 | p90 / max | thread | bytes |
|---|---|---|---|---|
| (a) `createImageData` + fill | 6.0 ms | 8.5 / 28.0 ms | sync | 2 483 520 B |
| (b) `convertToBlob('image/png')` | 1.8 ms | 2.0 / 2.4 ms | **async, off-main-thread** (6× probe: 33.4 ms total, 5.5 ms max main-thread stall, 0 long tasks) | 26 191 B |
| (c) `createObjectURL` + revoke | 0.4 ms | 0.5 / 0.7 ms | sync | — |
| (d) blob URL → decode | 0.5 ms | 0.7 / 1.1 ms | async | — |
| (e) `putImageData` → visible | **0.2 ms** | 0.2 / 1.7 ms | sync | — |
| (f) `drawImage(OffscreenCanvas)` → visible | **0.0 ms** | 0.0 / 0.1 ms | sync | — |

Decode and load are not separable in this harness: Chromium fires `load` only once the bitmap is
ready, and on a local blob both complete in ≤ 1.1 ms (disclosed in the rig notes).

### 3.4 CPU and memory delta, canvas layer vs blob pipeline (the brief's question, answered)

| quantity | blob → `<img>` (shipped) | persistent canvas layer | delta |
|---|---|---|---|
| per-update CPU on the critical path | encode 1.8 + URL 0.4 + src 0.8 + decode 0.5 ≈ **3.5 ms** (+ composite wait 4.4 ms) | `drawImage` **0.0 ms** / `putImageData` 0.2 ms | **−3.5 ms** |
| async machinery | encode promise, `inFlightEncode`, `paintGen`/`shouldPaintResult` stale guard, URL dedupe/revoke | none — the update is synchronous and bounded | deletes ~40 lines |
| per-cached-frame memory | measured PNG blob **26 191 B** × 8 ≈ **210 KB** (+ browser-side decoded bitmaps, **not measured here**) | `W·H·4` = **2 483 520 B** × 8 ≈ **19.9 MB** | **≈ +19.7 MB** at the current cache depth |
| GC pressure | 30 URLs, 24 revokes, retained +34.7 KB after GC | none per update | small but real |
| correctness risk | — | must reproduce `ImageOverlay`'s transform/zoom math; **unverified** — the prototype rig produced no artifacts (§4) | — |

**Read:** the canvas layer is worth **≈ 3.5 ms per update and a chunk of deleted async code**, and
costs **≈ 20 MB** of cache. It does not touch the 23-41 ms build, which is where the time goes.

### 3.5 Proposed design

| option | change | verdict |
|---|---|---|
| **(A) recommended** | **keep the blob overlay**; attack the build instead: (i) keep the existing `prefetch()` for playback, (ii) extend it to scrubs — prefetch the neighbouring frame when a drag starts or the tape is idle for a frame (reuses `prefetch`/`frameFor`/LRU, no new machinery), (iii) if on-device still hitches, cap the settle raster (780 → 640 ≈ 28 ms by area) and accept the same upscale the drag class already ships | smallest diff; the 41 ms build is the only measured main-thread cost worth moving |
| (B) adopt the canvas layer now | canvas in the overlay pane, cache = `OffscreenCanvas` per entry, `drawImage` on paint | buys 3.5 ms + code deletion, costs ~20 MB, and needs the O1/O2 equivalence gates that have **not** been run yet |
| (C) ship as-is | — | cold builds keep producing 50-76 ms long tasks on every scrub jump |

### 3.6 Item-3 gates

* **O1** *(required only if B is chosen)* canvas vs image-layer rect delta ≤ 0.5 px after boot, 2 pans
  and a zoom; per-pixel channel Δ ≤ 2 on the same frame — **not measured; the prototype rig failed (§4)**.
* **O2** *(either option)* a scrub jump must not produce a long task > 50 ms on the main thread; the
  cold build is currently 38-75 ms at rest class.
* **O3** *(either option)* retained heap after 30 updates ≤ **+100 KB** over the pre-state, and the
  overlay `src`/`drawImage` path stays free of monotonic growth after GC.
* **O4** `tests/*.test.js` + harness groups that read `.leaflet-image-layer` (they assume an `<img>`)
  must be updated in the same commit if B is chosen.
* **O5** playback profile unchanged or better: build p50 ≤ 19 ms, 0 long tasks (measured today).

---

## 4. Method and its limits

| rig | item | status |
|---|---|---|
| `tmp/64-smoothness/leaflet/leaflet_physics_bench.py` | 1 | run: 72 runs, 6 configs × 4 scenarios × N=3 (`RESULTS.json`, `RUN.log`, `SUPPLEMENTARY-pointerup-probe.json`) |
| `tmp/64-smoothness/scrub/scrub_regimes_bench.py` | 2 | run: 9 runs + valve (`RESULTS.json`, `RUN.log`) |
| `tmp/64-smoothness/overlay/overlay_pipeline_bench.py` | 3 | run: 3 phases + op bench (`RESULTS.json`, `RUN.log`) |
| `tmp/64-smoothness/canvas/canvas_layer_proto_bench.py` | 3 | **FAILED — no artifacts produced.** The canvas-layer prototype (positional equivalence, pixel diff, heap) was never executed, so O1 is an open verification item, and §3.4's correctness column is an estimate of effort, not a measurement |

Environment: 8 cores / 7 GB RAM, headless Chromium (build 1228), 390×844 @ DSF 2, `has_touch`, no CPU
throttling; every measured run serialized behind `flock /tmp/bpc64-bench.lock` so concurrent Chromium
instances could not corrupt frame timings. Noise handling: N = 3 with min/max reported; medal cells
that came back min == max are marked.

**Not measured here:** iOS Safari, a real touchscreen, thermal throttling, tile-network latency, the
browser-side decoded-bitmap memory of the current pipeline. Local-rig limitations disclosed in §3
(load/decode not separable; drag-raster dims ambiguous; longtask observer unreliable in one phase, a
gap-sampler fallback was used).

---

## 5. Architecture & data flow (item ownership)

```
                  ┌── [1] L.map() options: inertia / maxBoundsViscosity
                  │        └─ setMaxBounds (fitLake) → _panInsideMaxBounds on every moveend
gesture ──────────┤
                  ├── [2] #deck pointer handlers → scrubUiToMinutes (rAF, 60 fps, untouched)
                  │        └─ scheduleMapPaint → [suspension] → settle paint on pointerup
                  └── [3] showFrame → frameFor → compute → gather → smooth → paint
                           ├─ shipped: convertToBlob → objectURL → img.src → decode  (≈3.5 ms)
                           └─ bottleneck: the SYNC build 23-41 ms  ← [3] targets this, not the blob
```

Items 1 and 2 share the main thread; item 2's numbers must be read with item 3's build cost present
(they were: §2.2 and §3.2 come from the same tree).

---

## 6. Verification plan

### 6.1 Fast loop
`node tests/{parity,wind,render,ui}.test.js` after every edit batch; `tools/qa/scrub_bench.py` after any
scheduler change; the item-1 option change needs only the containment gates.

### 6.2 Full matrix (before commit)

| suite | proves | bar |
|---|---|---|
| `node tests/*.test.js` | unit contracts | 4/4 green |
| `tools/qa/stage5_check.py` | containment C1-C4, `[17]`/`[20]` profiles | P5, T6 green |
| `tools/qa/scrub_bench.py` | drag latency + swaps | T6 |
| **new gates (this stage)** | P1-P4, T1-T5, O2-O3 | per §1.6/§2.5/§3.6 |
| *(if D3.1 = B)* equivalence probe | O1 | rect ≤ 0.5 px, channel Δ ≤ 2 |
| `tools/qa/live_smoke.py` (post-deploy) | deployed bytes | 16 ok / 0 FAIL |

### 6.3 On-device pass (Reid — blocking for the tag)
One wet test: drag into each edge and flick, slow-scrub 24 h and 7 d, and compare the edge feel
(spring vs firm) against **D1.2**. Headless numbers are CI bars, not on-device promises.

---

## 7. Decision table (approval request)

| id | decision | recommendation | alternatives | impact if deferred |
|---|---|---|---|---|
| **D1.1** | Leaflet momentum | **disable it (`inertia:false`)** — the interior glide is small (10.6 px at 0.6 px/ms; 118 px at 2 px/ms) and momentum has *zero* measured leverage on edge behaviour, while the release tail becomes deterministic (283 ms ± 0.1 vs 133-300 ms) | keep `inertia:true` (as shipped); `inertiaDeceleration:12000` — **rejected: 45 px single-frame teleport** | keeps the variable-duration recoil Reid feels as "fighting the boundary" |
| **D1.2** | Edge give | **keep `maxBoundsViscosity: 0.75`** — a real, smooth rubber band: 45-61 px of give on a 180-240 px drag, returned in one fixed-duration 283 ms pan | `1.0` = firm edge, 0 px give, no recoil animation at all (also the lowest-risk feel, but no rubber band); `0.25` = 135-181 px of give (excessive) | the edge stays springy-but-inconsistent |
| **D1.3** | recoil source | **accept Leaflet's own `moveend` → `panInsideMaxBounds` (0.25 s) as the single recoil**; do not add an app-owned spring | app-owned `moveend` handler with a custom duration/easing | no measured downside; adding a spring is unrequested abstraction |
| **D1.4** | refits mid-gesture | **skip `scheduleRefit()` while a pointer is down** (`map.dragging.moving()`), since `setMaxBounds` immediately fires its own pan | leave as-is | an orientation change mid-drag can pan the map under the finger |
| **D2.1** | Scrub transport | **suspend lake-map paints while `scrubbing === true`** (one valve paint per 1.2 s + the existing pointerup settle). Deletes the EMA gate and the drag throttle | (B) keep the gate and raise `MAP_PAINT_MIN_MS` to 150; (C) ship as-is | R-slow keeps 36.6 ms p50 tape latency and 30 encodes per gesture |
| **D2.2** | Anti-freeze valve | **keep 1.2 s** (measured: exactly 1 forced paint in a 2.0 s drag, cost 1 × 35.6 ms frame) | 0.6 s (more frequent 35 ms frames); none (a frozen map on long drags) | — |
| **D2.3** | Drag raster | **keep 512** for the valve/settle paints; revisit only if the on-device pass says so | 384 (cheaper build, softer preview) | — |
| **D3.1** | Overlay path | **keep the blob → `<img>` pipeline** — its total per-update cost is ≈ 3.5 ms against a 23-41 ms build; the rewrite targets ~10 % of the time | adopt the canvas layer for the −3.5 ms and the deleted async code, paying ≈ +19.7 MB of cache and O1's unrun equivalence check | cold builds keep producing 50-76 ms long tasks |
| **D3.2** | Build-cost mitigation | **extend the existing `prefetch()` to scrubs** (neighbour frame on drag-start / idle), reusing `frameFor` + LRU — playback already proves the mechanism (build p50 18.9 ms, 0 long tasks) | cap the settle raster 780 → 640 (≈ 28 ms by area, visible softness at rest); chunk the build across frames (most code) | the 50-76 ms cold build stays on the critical path |
| **D3.3** | Canvas layer, if ever adopted | mirror `ImageOverlay._reset`'s transform math and keep `zoomend → regather`; run O1 first | re-derive from `latLngToLayerPoint` | a drifting canvas is worse than a 3.5 ms decode |

**Approval request:** confirm D1.1-D1.4, D2.1-D2.3, D3.1-D3.3 (or mark what to change). Bold defaults
become the build. Nothing is implemented until this table is signed off.

---

## 8. File manifest (prospective, closed list — nothing else after approval)

| item | file | change |
|---|---|---|
| 1 | `src/render.js` | `L.map()` options: `inertia: false` (+ optional viscosity); refit guard in `scheduleRefit` |
| 2 | `src/render.js` | `scheduleMapPaint`: suspension branch while `scrubbing`; delete `V_HI`/`V_LO`/`V_EMA_ALPHA` + the 120 ms decay; valve kept |
| 3 | `src/render.js` | `prefetch()` call on drag-start / idle-frame for the neighbour index (no other render change) |
| tests | `tests/render.test.js`, `tools/qa/stage5_check.py`, `tools/qa/scrub_bench.py` | P1-P4, T1-T5, O2-O3 gates |
| docs | `docs/STAGE-6.4-RECEIPTS.md` (new) | receipts after the build |

*(If D3.1 flips to the canvas layer, `index.html` (layer CSS) and the `.leaflet-image-layer` gates
join this list — and O1 must pass first.)*

## 9. Risks, rollback, open questions

* **R1 (item 1, feel):** disabling momentum is a deliberate behaviour change; a user who likes the glide
  may read the release as "heavy". One option line to revert; the on-device pass decides (D1.2).
* **R2 (item 2, staleness):** strict suspension means the wave map does not follow a slow scrub until
  the finger stops (≤ 1.2 s). If that reads as "broken" on device, D2.1-B is the fallback and its
  numbers are already known (encodes halve; latency stays tens of ms).
* **R3 (item 3, wrong target):** the recommended path deliberately does **not** rewrite the overlay. If
  Reid wants the canvas layer regardless (for the code deletion or future features), it is now known to
  buy 3.5 ms and cost 19.7 MB — an informed choice rather than a smoothness fix.
* **R4 (measurement):** all numbers are headless Chromium, synthetic touch, shared 8-core box. Item 1's
  frame-level "no jank" result is the most environment-sensitive claim in this document; the on-device
  pass is the arbiter.
* **R5 (unverified):** the canvas prototype never ran (O1 open). No claim in §3.5 depends on it — the
  recommendation is to keep the shipped path.
* **Open question O1:** should the *tape* also suspend during a *map* gesture (they are already
  independent; nothing in §2.2 shows contention) — no action recommended.
* **Open question O2:** `zoomSnap 0.1` plus `_limitOffset`'s integer-pixel rebound (§4691) is a
  candidate for sub-pixel edge jitter at deeper zooms; not observed at the fit zoom (reversals = 0).
  Re-check if the on-device pass zooms in and feels a stutter at the edge.
