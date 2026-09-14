# STAGE 6.3 — RECEIPTS

Stage 6.3 polish: water-mask cleansing (item 1), map containment & rubber-band (item 2),
60 fps scrub (item 3), header gust trim (item 4). Spec: `docs/SPEC-stage-6.3-polish.md`
(APPROVED; bold defaults locked D1.1–D1.5, D2.1–D2.4, D3.1–D3.5, D4.1–D4.2).

- Base revision: `87a52cb` (6.2, tag `stage-6.2-polish`)
- Item-1 commit: `e68c90a` — water-mask cleansing
- Items 2–4 + gates commit: `[COMMIT-B]` (this tree)
- Tag `stage-6.3-shipped` + Pages deploy: **pending the two open decisions in §7**
  (the §6.2 matrix is green except `[20.7b]` and `[17]`; both are analysed below).

## 0. What was built

| item | files | summary |
|---|---|---|
| 1 | `tools/export_tables.py`, `public/tables.v1.bin`, `public/meta.v1.json`, `public/mask.v1.json` | largest 4-connected water body kept (D1.1); satellites dropped; mask receipt written |
| 2 | `src/render.js` | `maxBoundsViscosity: 0.75`; `fitLake()` rework (`setMinZoom(0)`-before-measure guard); pan box `fitCenter ± half(paddedSpan)`; debounced refit on resize/orientation |
| 3 | `index.html`, `src/render.js` | permanent `will-change: transform` on `#track-tape` (D3.1); velocity-gated encode/swap (V_HI 0.25 / V_LO 0.08 / EMA α 0.3 / 1.2 s valve, D3.3); drag-time raster 512 device px (D3.4-A/D3.5), 780 restored on settle |
| 4 | `index.html`, `src/render.js` | gust badge `[24 Gust]` (`.unit` span removed); dynamic `aria-label="Gust {gust} mph"` |
| gates | `tests/render.test.js`, `tools/qa/stage5_check.py`, `tools/qa/live_smoke.py` | §4.2 closed list + new group `[20]` |

Items 2–4 + gates were delegated to OpenCode (Run A: two files; Run B: three gate files),
then re-verified in-house (diff review, `node --check`, probes). Three in-house fixes on top
of Run A (all single-file, `src/render.js`):

1. **`vEma` seeded at `V_HI`** at gesture start — an EMA seeded at 0 needs ~4 samples
   (~66 ms) to cross `V_HI`, letting one expensive paint through on every fast drag
   (measured: one 46–51 ms stall per flick).
2. **Sustained-gap EMA decay** — the EMA only sampled `pointermove`; when the finger stopped
   mid-drag it never decayed, so suspension never lifted and the map waited for the 1.2 s
   anti-freeze valve (blob at +1.26 s after motion stopped). Decay (delta 0, same α) fixes
   the catch-up paint.
3. **`animate:false` on the refit** — the resize path read `getZoom()` mid zoom-animation,
   yielding a stale floor after rotation.

## 1. Item 1 — water-mask cleansing

**Reproducibility baseline (proved before mutating):** re-running `python3 tools/export_tables.py`
on the 6.2 tree regenerated `public/tables.v1.bin` **bit-identical** to the shipped blob
sha256 `33aa6e521777360d16b00abf7d137b869674c60a4ac6ddd1f072080b1bc2a2e7` (613,320 B; 5.1 s).
The before/after deltas below are therefore mask-only effects.

**Mask receipt (`public/mask.v1.json`):**

| comp | cells | area km² | centroid (lat, lon) | depth ft (min/med/max) |
|---|---|---|---|---|
| keep | 52,738 | 527.38 | 46.2424, −93.6466 | 0.0 / 30.8 / 40.0 |
| drop | 345 | 3.45 | 46.3351, −93.8053 | 0.0 / 6.8 / 42.0 |
| drop | 322 | 3.22 | 46.2058, −93.8129 | 0.0 / 0.2 / 42.0 |
| drop | 317 | 3.17 | 46.3560, −93.7723 | 0.0 / 1.9 / 42.0 |
| drop | 169 | 1.69 | 46.1110, −93.7239 | 0.0 / 2.2 / 12.7 |
| drop | 104 | 1.04 | 46.3666, −93.8067 | 0.0 / 3.8 / 5.7 |

6 components in, 5 dropped (1,257 cells / 12.57 km² = 2.33 % of water cells). Keep-assertion
(≥ 50,000 cells) held. 4-connectivity (D1.1); identical result under 8-connectivity.
Naming (D1.5): centroids + areas + townships recorded (Hazelton / Roosevelt / Kathio);
no names asserted (web-verify deliberately skipped per D1.5 = cosmetic only).

**Byte-level diff (`tmp/s63_verify_after.py`, section-by-section):**

| section | changed | bytes |
|---|---|---|
| depth | 1,257 cells water→LAND | 2,514 |
| fetch | 2,594 u16 entries → LAND_U16 | 5,188 |
| path | 2,024 u8 entries → 0 | 2,024 |
| **total** | | **9,726 B (1.59 %)** |
| **file size** | | **613,320 B (0 delta — assertion holds)** |

**Deviation vs §1.3's prediction (2,242 / 1,786, ≈ 8,784 B):** the prediction charged only the
144 sampling points *inside* the bodies. Measured 182 fetch points: **144** start inside a
dropped body + **38** start on land whose ray ran *into* the then-water body (a ray's start
cell is never bounds-checked, only its first step). All 38 sit exactly 1 cell (Chebyshev)
from a dropped cell. **Kept-lake points changed: 0** — the §1.3 invariance claim holds, so
the Mille Lacs wave field is bit-identical (P2).

**meta.v1.json:** `depth_ft` [0.0, 42.0] → **[0.0, 40.0]**; `fetchEff_decam` [2, 2335] and
`pathEff_ft` [0, 34] unchanged.

**Golden fixtures:** worst |Δ| vs `golden.json` = 4.8e-5, identical before/after. §6.3:
fixtures are DEM point queries inside Mille Lacs — none embeds satellite cells →
**no regeneration** (recorded per §6.3).

**Runtime (P4/P5; crafted 25/12/38 series, `?frame=40`):** `p10Ft` 1.069 → **1.129** (up);
`hsFt` 2.871 = 2.871; peak card identical. 5 satellite centroids: tap `true`→**`false`**,
raster alpha 255→**0**, flash `land — no wave data here`.

## 2. Item 2 — map containment & rubber-band

Harness group `[20.3]–[20.6]` (authoritative, both viewports):

- **C1** `minZoom == zoom` at fit: **10.4** @390×844, **10.3** @360×800; box contains lakeBounds;
  viscosity 0.75.
- **C2** lake north edge y = **244.0 → 244.0 px** @390 (234.0 → 234.0 @360) across a synthetic
  vertical drag — the 29 px header-clearance contract holds (≥ 96 px bar).
- **C3** max mid-drag rubber-band overshoot 164.2 px → settles to **0.42 px** past the clamp
  (≤ 0.5 px, ≤ 5 px bars) within 120 ms of release.
- **C4** `zoomOut()` ×3 stops at exactly the fit floor **10.4**; lake width ratio 1.000 (≥ 0.95).
- **C5** `[19]` full group green (see §5) — 72 px header ceiling, corners, continuous scrub.

## 3. Item 3 — 60 fps scrub

**Direct probe (`tmp/s63_dragraster_probe.py`):** rest 780 → tap 780 (no flip) → slow drag
**512** → settle **780**; encodes: slow drag 7 (throttled), fast flick **0 during the
gesture**, 1 settle encode.

**Profiles (`[20.7]`, 390×844 DSF2, crafted series, sequential flick→slow→hold on one page;
slow pacing set to the §3.1 achieved velocity ≈ 0.13 px/ms):**

| gate | bar | 6.2 baseline (s63_attrib) | 6.3 measured | verdict |
|---|---|---|---|---|
| G1 flick | >33 ms == 0, p90 ≤ 20 | 7 / p90 41.4 | **0 / p90 16.8–16.9, max 16.9** | ✅ |
| G2 slow | >33 ms ≤ 2, p90 ≤ 25 | 22 / p90 46.1 | **3 / p90 16.9–17.0** | ⚠️ see §7-A |
| G3 hold | p90 ≤ 17, max ≤ 20 | p90 16.8 | **p90 16.8–16.9, max 16.9–17.1, 0 encodes** | ✅ |
| G4 tape advance | ≥ 0.95 advancing, matrix form | — | **1.000 / true** | ✅ |

**G2 attribution (timeline probe `tmp/s63_profile_timeline.py`):** the three >33 ms frames are
the slow drag's first three encodes — 143.6 ms (the session's **first-ever 512-class build**:
one-time land-frac gather + JIT), then 41.4 / 38.7 ms — all followed within ~4 ms by their
blob. Encodes 4–7 of the same drag are **≤ 33 ms**; the dead-zone after the clamp produces
**zero** encodes. So the drag path is clean in steady state; the miss is one-time cold cost
landing inside the measured window.

**G5 scrub_bench:** median **16.6 ms** (≤ 25 ✓), p90 **16.8–17.5** (≤ 30 ✓), max 17.2–33.4,
swaps **0** (≤ 12 ✓), long ≤ 50 ✓, `index_exact` ✓ (idx 42 → 42, pill 10:30 AM), `runway_24h`
176 ✓. One check fails: `tapeTx>=moves` (tx=30, moves=31) — **same instrument as `[17]`, see §7-B.**

**G6 settle correctness:** `[19]` continuous-scrub + Home-settle gates green; released frame ==
the throttled target index (`expectedIdx`) — harness `[16]/[17] final` lines: idx 42 == 42.

## 4. Item 4 — header gust trim

- Markup `index.html:288`: `<span id="pill-gust" … aria-label="Gust 24 mph"><span id="gust">24</span><span id="gust-u">Gust</span></span>`
  — `#pill-gust .unit` gone; `#lake`/`#mph` untouched (tier tint + white unit kept).
- `src/render.js:1202`: `pillGustEl.setAttribute('aria-label', 'Gust ' + pills.gust + ' mph')`.
- §4.2 closed list applied: `tests/render.test.js` (negative: `#pill-gust` must not contain
  `class="unit"`, inner spans exactly `['gust','gust-u']`, `[24 Gust]` labels), `stage5_check.py`
  ([19.4]/[19.5] gust clauses), `live_smoke.py` (DOM absence + deployed-bytes absence + row text).
- **H1** header 72.00 px, ink ≤ available at all four viewport/viewport-profile combos —
  `[19.1]–[19.3]` green (slack 168.8–213.3 px). **H2** `[17 mph]` badge unchanged — `[19.5]/[19.6]`
  (lake unit white, contrast ≥ 5.11:1). **H3** rendered `[24 Gust]` — `[19.4]`, plus live-smoke
  run post-deploy.

## 5. Verification matrix (§6.2)

| suite | result |
|---|---|
| `node tests/*.test.js` (4 files) | **4/4 ALL TESTS PASSED** (harness `[12]`) |
| `stage5_check.py` `[19]` (6.2 regression) | **ok — all gates ok=True** |
| `stage5_check.py` `[20]` (new) | `[20.1]–[20.6]` ✅, `[20.7a/c/d]` ✅, **`[20.7b]` ⚠️ §7-A** |
| `stage5_check.py` full | **24 ok, 2 FAIL** — `[17]` (⚠️ §7-B) + `[20.7b]`; both runs identical (`tmp/s63-harness-final.log`, `tmp/s63-harness-final2.log`) |
| `scrub_bench.py` | median/p90/swaps/index all ✅; `tapeTx>=moves` ⚠️ (§7-B, same instrument as `[17]`) |
| `live_smoke.py` | pending deploy (run post-push) |

`[9]` playback perf ok (canvas 780, frameMs avg 45.5 — path untouched by 6.3);
`[10]/[11]` radar smoothing unchanged; `[13]` lazy 7d ok; `[14]` live seam pass.

## 6. Rollback

- Item 1: `git checkout 87a52cb -- public/tables.v1.bin public/meta.v1.json` (+ delete
  `public/mask.v1.json`), or re-run the exporter from the old tree.
- Items 2–4: revert the items 2–4 commit (map init/fit; CSS + scheduler; markup + aria) —
  each item is separately reversible (§0).
- Full: reset to `87a52cb`.

## 7. Open decisions before tag/publish

**A. `[20.7b]` G2 = 3 frames > 33 ms vs bar ≤ 2** (p90 16.9 ✓; 6.2 was 22 / p90 46.1).
   Root cause: the session's first 512-class builds (one-time 143 ms cold + two ~40 ms JIT-warm)
   fall inside the first drag; steady-state encodes are ≤ 33 ms. Options:
   1. **Accept + document** (recommended): the gate's spirit — "a slow drag does not hitch" —
      is met in steady state; first-drag cold cost is a one-time, on-device-checkable item (O2).
   2. Adopt the rig's standard warm-up convention (as `[17]`/`scrub_bench` already do) so G2
      measures steady state, with the cold first-drag cost recorded separately (out of manifest —
      needs explicit approval).
   3. D3.4-B (raise drag-time throttle to ~120 ms) — weak, and it edits a locked D3.3 constant.

**B. `[17]` + `scrub_bench.tapeTx>=moves` fail (tx=30, moves=31).**
   Root cause: `moves` counts one pre-down positioning event that writes nothing in **every**
   era (cdp-touch, moves=30, is exactly 30/30). The check only ever passed via mid-drag
   **paint-flush writes** (6.2: tx = 30 + 11 swaps; Run B tree: 30 + 1) — and item 3's
   suspension (D3.3) removes mid-drag paints on fast drags **by design** (G1 requires 0
   encodes). The tape still follows every drag step 1:1 (30/30 measured). Fix = compare against
   the drag-step count (`tx >= moves - 1`) in both files, with a comment. One line each;
   outside §4.2's closed list → held for approval.

**C. After A/B sign-off:** re-run the full suite, update §5, commit, tag `stage-6.3-shipped`,
push, then `live_smoke.py` against Pages (§4 H3 + `[19]`-live) before the final report.
