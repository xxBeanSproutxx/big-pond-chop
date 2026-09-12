# STAGE 5P — PRODUCTION DEPLOYMENT RECEIPTS (six UI passes: 5L + 5M + 5N + 5O + 5P)

Deployed 2026-09-12 by Reid's explicit approval ("Stage 5P is approved. Let's ship it to production").

## Merge & tag

- Merge commit **`1063031`** — `git merge --no-ff stage5p` into `main` (base `383126e` = 5I).
  Landing **21 files, +2,284 / −121** (7 spec docs, 7 receipts docs, `index.html`, `src/render.js`,
  `src/ui.js`, `tests/render.test.js`, `tests/ui.test.js`, `tools/qa/live_smoke.py`,
  `tools/qa/stage5_check.py`).
- Tag **`stage-5p-live`** → annotated `b5c41d3` → commit `1063031` (`refs/tags/stage-5p-live^{}` on the remote).
- `origin/main` == **`1063031`** (verified with `git log -1 origin/main` after push).
- Pre-merge gate on the merged tree: `git diff stage5p main` = **0 lines** (the shipped tree is exactly the
  gated tree), physics vs 5I = **0 lines**, node suites `parity / wind / render / ui` **4/4 PASS**.

## GitHub Pages build

- `gh api repos/xxBeanSproutxx/big-pond-chop/pages/builds/latest`: **`status=built`, `commit=1063031`**,
  `created_at=2026-09-12T23:10:40Z` (polled 5×8 s: 4× `building` → `built`).
- The Pages build record can lag; therefore the deployed bytes were **verified by content fetch** —
  this is the decisive check (see next section).

## Deployed-content verification (production bytes)

Fetched live and grepped (markers unique to the new stages):

| asset | marker | present |
| --- | --- | --- |
| `index.html` | `deck-h: 62px` (5P) | ✅ |
| `index.html` | `text-shadow: 0 1px 2px` (5P) | ✅ |
| `index.html` | `top: 40px` (5P number row inside the ribbon) | ✅ |
| `index.html` | `height: 20px` (5P ribbon) | ✅ |
| `src/ui.js` | `WIND_HEAT`, `windHeatColor`, `windHeatGradient` (5O) | ✅ |
| `src/render.js` | `.day-heat` append (5O) | ✅ |

## Live smoke — 10 ok / 0 FAIL

`tools/qa/live_smoke.py --url https://xxbeansproutxx.github.io/big-pond-chop/`:

```
deck two-row       ok  deckH=62.0 blocks=1 absent=True          <- 5P deck height live
pill permanent     ok  text='6 PM' hidden=False above-bar=True
reticle centred    ok  pill centre == timeline centre (<=1px)
play pinned        ok  overlays the window's left edge, z-index>=10
tape wired         ok  tape=550 px inside #timeline=True
wind row           ok  block0 .day-wind count=8 all-numeric=True list=['14','20','23','18','21','21','21','21']
day header         ok  header='Saturday 12' subs=['12','03','06','09','12','03','06','09','12']
7 day live         ok  blocks=7 alt=True boot-hidden=True tape=2310 sub-labels=[8,8,8,8,8,8,8]
                       headers: Saturday 12 | Sunday 13 | Monday 14 | Tuesday 15 | Wednesday 16 | Thursday 17 | Friday 18
back to 24 h       ok  aria-valuemax=95
no page errors     ok  errors=0 []
SUMMARY: 10 ok, 0 FAIL
```

- **Zero console/runtime errors** (`errors=0 []`).
- The live 24h wind row reads `14 20 23 18 21 21 21 21` while the local pre-merge run read
  `14 20 23 18 23 22 21 20` — expected: it is live NWS forecast data, not a fixed fixture.
- The script carries **10 assertions** (not 12); the "12" in the brief maps to the **asset audit**
  below, which is 12/12.

## Asset delivery audit — 12/12 HTTP 200

Every same-origin asset the page references, plus the CDN files:

```
index.html                  200      src/ui.js         200
public/favicon.svg          200      src/render.js     200
public/meta.v1.json         200      src/wind.js       200
public/spots.v1.json        200      src/wave-math.js  200
public/tables.v1.bin        200      src/tables.js     200
public/warp.v1.json         200      og-preview.png    200
TOTAL: 12/12 same-origin HTTP 200
+ unpkg leaflet 1.9.4 dist/leaflet.css 200 · dist/leaflet.js 200
```

## Rollback

- `git revert -m 1 1063031` (or reset `main` to `383126e`) — 5I is the previous production state.
- Safety tags still in place: `pre-stage5i` (`46d92cc`), `pre-stage5h` (`ed377a4`), `pre-stage5g` (`809d84d`),
  `pre-stage5f` (`be29ba2`), `pre-stage5` (`9ec0f97`), `pre-stage4`.
- All six stage branches (`stage5l`…`stage5p`) remain on the remote; nothing was deleted.

## Housekeeping

- Local preview servers (`python3 -m http.server` on **8796** LAN and **8791** loopback) **stopped** —
  production is the only served copy now.
- `tools/qa/live_smoke.py` now points at production by default.

## What is live now (user-visible)

Three-tier 62 px deck: sticky day header · 3-hourly ticks · **20 px colour-graded wind heat ribbon with the
mph numbers embedded inside it**. Alternating day blocks with a crisp midnight divider, 24 h tape at
550 px/day and a **7 day tape at 330 px/day** (2,310 px, no colliding digits), bright turquoise calm water
(`#0891b2` at 0.68) with map labels still readable underneath, a fixed centre reticle with permanent amber
pill, drag-to-scroll tape at 16.4–18.0 ms per step with no long tasks, and the downwind flow arrow (5I).
