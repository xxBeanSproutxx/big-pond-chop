# STAGE 6 — RECEIPTS (marine header + dual-location wind; verification pass)

Branch `stage6`. HEAD when this pass started: `1ab711b` (`6A` `a829ee0`, `6B` `10327b2`,
`6B.2` `8431be1`, `6B.2.1` `1ab711b`). This stage is **QA-only**: it proves the 6A/6B code and
does not touch it. `src/**`, `index.html` and `tests/**` were out of scope; the only files
changed are `tools/qa/stage5_check.py`, `tools/qa/live_smoke.py` and this document.
No merge, no tag, no push.

---

## 1. What shipped (ids + behaviours)

**6A — dual-location ingest (`src/wind.js`).** One batched GET for lake + shore
(`buildDualUrl`, `parseTwoLocations`, `SHORE_POINT`); `ingest()` returns
`{ day (lake, unchanged), shoreDay (nullable) }`. Physics untouched. Verified live: exactly
**1** request to `api.open-meteo.com` on boot, its URL carrying **both** latitudes
(`46.22` lake, `46.13` shore).

**6B / 6B.2 / 6B.2.1 — the floating marine header (`index.html`, `src/ui.js`, `src/render.js`).**

| shipped | value / behaviour |
| --- | --- |
| `<header>` band | `position: fixed`, `z-index: 1001`, `backdrop-filter: blur(8px)`, `rgba(15,23,42,.85)`, 72 px band (+ 1 px hairline `border-bottom`) |
| three-pill row `#three` | `#pill-shore` (`#shore` + `#shore-u`) · `#arrow` (SVG) · `#pill-lake` (`#lake` + `#lake-u`) · `#dot` · `#pill-gust` (`#gust` + `#gust-u`) · `#mph` |
| `#help` | 44×44 target, absolute so it cannot inflate the text column; exactly **8 px** clear of `#refresh` |
| `#help-pop` | sibling of `<header>` (never sliced by the band's `overflow: hidden`), `position: fixed`, `z-index: 1002` |
| retired | `#wind-info`, `#frame-info`, `.sep` and `ui.windLine` — **zero** references remain in `src/**`, `index.html`, `tests/**` |
| lake pill | tinted from `WIND_HEAT` (`ui.windPills(lakeMph, shoreMph, gustMph)` → `{lake, shore, gust, lakeTint, lakeBorder}`), all pill ink white |
| `fitLake` | `paddingTopLeft: [12, headerBand() + 12]` — the top reserve is computed from the **live** header band, not hard-coded |

---

## 2. Gates — raw numbers

| gate | raw result |
| --- | --- |
| `tests/parity.test.js` | exit 0 — `ms/hour 1.23` (budget 2–6) · ALL TESTS PASSED |
| `tests/wind.test.js` | exit 0 — `1.70 ms/frame` (budget ≤ 6) · ALL TESTS PASSED |
| `tests/render.test.js` | exit 0 — three-pill ids present, `#wind-info`/`#frame-info`/`.sep` gone · ALL TESTS PASSED |
| `tests/ui.test.js` | exit 0 — `windHeatGradient` stops/endpoints flat-gradient and empty cases · ALL TESTS PASSED |
| `tools/qa/stage5_check.py` | **SUMMARY: 25 ok, 0 FAIL** (see §3 for the `[19]` block) |
| `tools/qa/live_smoke.py` (local server) | **SUMMARY: 15 ok, 0 FAIL** — the original 10 + 5 new 6B chrome assertions |
| `tools/qa/scrub_bench.py` | **VERDICT: 24/24 PASS**, **0 long tasks** in all three cases (see §2.1) |

> Note on `[9] playback perf`: it failed in my first full run (`avg=65.4 max=94.6`) **only
> because I ran `scrub_bench.py` concurrently** and the two Chromium instances contended for the
> CPU. Re-run alone it is `ok avg=44.4 max=55.6`, matching the orchestrator's pre-existing green
> (`avg=44.3 max=55.6`). Not a regression — a measurement-hygiene artefact, recorded here so the
> number is not mistaken for one.

### 2.1 Scrub bench vs the 5P baseline

The floating frosted header (`backdrop-filter: blur(8px)` over a live map) is the thing being
priced. The 5P baseline was **16.72 / 16.71 / 18.01 ms, 0 long tasks**.

| case | 6C median | 5P baseline | delta | long tasks | max |
| --- | --- | --- | --- | --- | --- |
| 390x844 mouse | **16.42 ms** | 16.72 | −1.8 % | **0** (`longtasks=[]`) | 62.47 ms |
| 360x800 mouse | **16.80 ms** | 16.71 | +0.5 % | **0** (`longtasks=[]`) | 55.39 ms |
| 360x800 cdp-touch | **18.34 ms** | 18.01 | +1.8 % | **0** (`longtasks=[]`) | 66.99 ms |

All three medians are within **2 %** of the baseline — well inside the ±15 % regression bar —
and **no long task** appeared in any case. `swaps=10` and `index_exact idx=42 expected=42`
are unchanged. **No regression to report.**

Other harness lines: `[15] deckH=62.0 … trackH=62.0 timelineH=62.0`; `[16] 7d tape=2310.0
blocks=7 tones-ok=True`; `[17] swaps=10<=12 long-max=0<=50 idx=42 expected=42`.

---

## 3. Group `[19] 6 marine header` — verbatim

Driven from **route-intercepted** `api.open-meteo.com` responses returning a crafted **array of
two location objects** (a single-object response silently yields `shoreDay = null` — that trap
cost an earlier leaf time, and gate 11 now pins it deliberately). Measured at **360×800** and
**390×844**.

```
[19.8] normal @boot open-meteo=1 url-has-both-lats=True hosts=['127.0.0.1', 'api.open-meteo.com', 'tile.openstreetmap.org', 'unpkg.com'] unexpected=none
[19.9] identity @360x800 idx=82 day[idx]=17 shoreDay[idx]=8 DOM lake='17' shore='8' lake-match=True shore-match=True
[19.9] identity @390x844 idx=82 day[idx]=17 shoreDay[idx]=8 DOM lake='17' shore='8' lake-match=True shore-match=True
[19.1] normal @360x800 header_h=72 scrollH=71 clientH=71
[19.2] normal @360x800 #three sw=232 cw=232 mph_w=19.45 (>=19)
[19.3] normal @360x800 ink=209.8 avail=232 slack=22.19999999999999
[19.4] normal @360x800 pills-inside=True help=44x44 gap=8
[19.5] normal @360x800 numerals=13px/700/tabular-nums labels=10px font=-apple-system, BlinkMacSystemFont, Inter, "Segoe UI", Roboto, sans-serif
[19.6] normal @360x800 contrast min=5.11:1 (#lake numeral vs #pill-lake) pairs=#lake=5.11 #shore=12.26 #gust=12.26 #lake-u=5.11 #shore-u=8.64 #gust-u=8.64 #mph=11.76 #dot=6.81 #arrow=6.81 #help=11.76
[19.1] normal @390x844 header_h=72 scrollH=71 clientH=71
[19.2] normal @390x844 #three sw=262 cw=262 mph_w=19.45 (>=19)
[19.3] normal @390x844 ink=209.8 avail=262 slack=52.19999999999999
[19.4] normal @390x844 pills-inside=True help=44x44 gap=8
[19.5] normal @390x844 numerals=13px/700/tabular-nums labels=10px font=-apple-system, BlinkMacSystemFont, Inter, "Segoe UI", Roboto, sans-serif
[19.6] normal @390x844 contrast min=5.11:1 (#lake numeral vs #pill-lake) pairs=#lake=5.11 #shore=12.26 #gust=12.26 #lake-u=5.11 #shore-u=8.64 #gust-u=8.64 #mph=11.76 #dot=6.81 #arrow=6.81 #help=11.76
[19.1] wide @360x800 header_h=72 scrollH=71 clientH=71
[19.2] wide @360x800 #three sw=232 cw=232 mph_w=19.45 (>=19)
[19.3] wide @360x800 ink=217.03 avail=232 slack=14.969999999999999
[19.4] wide @360x800 pills-inside=True help=44x44 gap=8
[19.5] wide @360x800 numerals=13px/700/tabular-nums labels=10px font=-apple-system, BlinkMacSystemFont, Inter, "Segoe UI", Roboto, sans-serif
[19.6] wide @360x800 contrast min=6.81:1 (#dot vs header glass) pairs=#lake=7.76 #shore=12.26 #gust=12.26 #lake-u=7.76 #shore-u=8.64 #gust-u=8.64 #mph=11.76 #dot=6.81 #arrow=6.81 #help=11.76
[19.1] wide @390x844 header_h=72 scrollH=71 clientH=71
[19.2] wide @390x844 #three sw=262 cw=262 mph_w=19.45 (>=19)
[19.3] wide @390x844 ink=217.03 avail=262 slack=44.97
[19.4] wide @390x844 pills-inside=True help=44x44 gap=8
[19.5] wide @390x844 numerals=13px/700/tabular-nums labels=10px font=-apple-system, BlinkMacSystemFont, Inter, "Segoe UI", Roboto, sans-serif
[19.6] wide @390x844 contrast min=6.81:1 (#dot vs header glass) pairs=#lake=7.76 #shore=12.26 #gust=12.26 #lake-u=7.76 #shore-u=8.64 #gust-u=8.64 #mph=11.76 #dot=6.81 #arrow=6.81 #help=11.76
[19.1] calm @360x800 header_h=72 scrollH=71 clientH=71
[19.2] calm @360x800 #three sw=232 cw=232 mph_w=19.45 (>=19)
[19.3] calm @360x800 ink=195.33 avail=232 slack=36.66999999999999
[19.4] calm @360x800 pills-inside=True help=44x44 gap=8
[19.5] calm @360x800 numerals=13px/700/tabular-nums labels=10px font=-apple-system, BlinkMacSystemFont, Inter, "Segoe UI", Roboto, sans-serif
[19.6] calm @360x800 contrast min=6.81:1 (#dot vs header glass) pairs=#lake=7.22 #shore=12.26 #gust=12.26 #lake-u=7.22 #shore-u=8.64 #gust-u=8.64 #mph=11.76 #dot=6.81 #arrow=6.81 #help=11.76
[19.1] calm @390x844 header_h=72 scrollH=71 clientH=71
[19.2] calm @390x844 #three sw=262 cw=262 mph_w=19.45 (>=19)
[19.3] calm @390x844 ink=195.33 avail=262 slack=66.66999999999999
[19.4] calm @390x844 pills-inside=True help=44x44 gap=8
[19.5] calm @390x844 numerals=13px/700/tabular-nums labels=10px font=-apple-system, BlinkMacSystemFont, Inter, "Segoe UI", Roboto, sans-serif
[19.6] calm @390x844 contrast min=6.81:1 (#dot vs header glass) pairs=#lake=7.22 #shore=12.26 #gust=12.26 #lake-u=7.22 #shore-u=8.64 #gust-u=8.64 #mph=11.76 #dot=6.81 #arrow=6.81 #help=11.76
[19.12] overlay backdropFilter=blur(8px) zIndex=1001 overlaps-map=True fit-padding-dynamic=True horizon-clearance=12 badge-clearance=12
[19.7] jitter @360x800 frames=24 equal-digit-pairs=23 max-lake-delta=0.00px row-crosses-refresh=False lakes=16,17,17,17,17,18,18,18,18,19,19,19,19,20,20,20,20,21,21,21,21,22,22,22
[19.7] jitter @390x844 frames=24 equal-digit-pairs=23 max-lake-delta=0.00px row-crosses-refresh=False lakes=16,17,17,17,17,18,18,18,18,19,19,19,19,20,20,20,20,21,21,21,21,22,22,22
[19.10] popover @360x800 pin-opened=True chip-open(hidden=False aria=true sibling=True prev=HEADER top=78 bottom=198.34>72) inside-keeps-card=True pins=1==1 escape(hidden=True aria=false focus=help) outside-tap@180,300(hidden=True aria=false focus=help missing=[])
[19.10] popover @390x844 pin-opened=True chip-open(hidden=False aria=true sibling=True prev=HEADER top=78 bottom=198.34>72) inside-keeps-card=True pins=1==1 escape(hidden=True aria=false focus=help) outside-tap@195,300(hidden=True aria=false focus=help missing=[])
[19.11] shore-missing @360x800 #shore='—' #lake='17' header=72.00 new-console-errors=0
[19.11] shore-missing @390x844 #shore='—' #lake='17' header=72.00 new-console-errors=0
[19] 6 marine header        ok   all gates ok=True
```

Final harness line:

```
SUMMARY: 25 ok, 0 FAIL
```

---

## 4. Deliberate gate deltas (all numbered, all justified)

1. **`[3] header layout` now asserts the BORDER-BOX height.** 6B gave the header a 1 px
   hairline `border-bottom` as part of the approved design, so `clientHeight` is 71 (content-box)
   while the band is still 72 px. The gate now asserts `offsetHeight == 72` and prints
   `box / content / scroll` per viewport. Same intent, correct box model.
   ```
   390: box=72 content=71 scroll=71 | 360: box=72 content=71 scroll=71
   ```
2. **New group `[19] 6 marine header`** — 12 numbered checks, added after `[18]` and registered
   in the same table as every other group (`safe(19, "6 marine header", check_marine_header, pw, port)`).
3. **Retired the `windLine` test.** `ui.windLine` no longer exists (6B moved the numbers into the
   `#three` row), so its unit test was removed rather than left asserting against a dead symbol.
   Nothing else in the suites changed — `grep -rn windLine src/ index.html tests/` returns **0 hits**.
4. **`live_smoke.py` additions** — 5 assertions that the DEPLOYED bytes carry the 6B chrome:
   `6b ids live`, `6b ids in bytes`, `6b avionics font`, `6b frosted glass`, `6b popover sibling`.
   They read both the live DOM (`getComputedStyle`) and the served markup, so a Pages deploy
   from a pre-6B tree fails them. The original 10 assertions are untouched.
5. **Stale probe repair** (`stage5_check.py` `check_tier`). It still read
   `document.getElementById('frame-info').textContent` — an id deleted in 6B, which would throw.
   Re-pointed at the shipped `#three` row and made null-safe; `#three` carries no H/L any more,
   so `hl` stays `NaN` and the tier is decided by the max/roller body datasets, as designed.
6. **`[19.12]` checks the dynamic fit padding** — `"headerBand() + 12" in render_src`, because
   6B.2 replaced the hard-coded 84 px top reserve with a live measurement. This is the
   orchestrator's delta and is preserved.

### 4.1 Harness hardening found by this pass (mutation-tested)

The group-19 block was **not** simply trusted — every gate was mutation-tested against a
deliberately broken copy of `index.html` to prove it *fails* when its condition is false:

| mutation | gates that correctly went red |
| --- | --- |
| glass → `rgb(200,30,30)`, `blur(0px)` | `[19.6]` contrast (min 2.24:1, ×6), `[19.12]` overlay |
| band → 60 px, `pill-gust`/`mph` ids renamed | `[19.1]`–`[19.6]` (×6), `[19.12]`, `[19.11]` (×2) |
| numerals 18 px, labels 14 px, no `tabular-nums` | `[19.1]`, `[19.5]` (×6 each) |
| `#help` 28×28, gap 4 px | `[19.4]` (×6) |

Two real defects were found and fixed in the **harness** (not the app):

- **A mid-check navigation crashed the whole group.** The outside-tap coordinate
  `(w//2, h-140)` = `(180, 660)` landed on Leaflet's attribution control — an
  `<a href="https://leafletjs.com/">` — which **navigated the page away**. The next
  `page.evaluate` then ran in a destroyed context and `S6_POPOVER_JS`'s
  `document.querySelector('header').getBoundingClientRect()` threw
  (`Cannot read properties of null`), killing the group before gates 10 and 11 ran. The probe
  now scans for a bare map point that is provably not a link, button or `.leaflet-control`,
  and prints the coordinate it used (`outside-tap@180,300`).
- **No probe may throw.** `S6_GEOMETRY_JS` and `S6_POPOVER_JS` are now null-safe: a missing
  element is returned as `null` **and named** in a `missing` list, which fails only the sub-check
  that needs it. Each numbered gate additionally runs inside a `gate()` wrapper, so any
  Python/Playwright exception marks **that one gate** failed with the exception text inline and
  the group continues — twelve results, never one red for twelve.

---

## 5. The 6B.1 contrast fix

The lake label sits on the `.55`-alpha `WIND_HEAT` tier tint, where `#cbd5e1` measured
**3.58:1** on the amber tier — below the 4.5:1 gate. It was moved to `#f8fafc`, which clears
every reachable tier: **teal 7.24, green 5.68, amber 5.08, orange 6.25, crimson 7.72**.

Measured by `[19.6]` across all three states and both viewports: **minimum 5.11:1**
(`#lake numeral vs #pill-lake`, normal state), and the worst label pair `#lake-u` also 5.11:1.
Full pair table (normal @360): `#lake=5.11 #shore=12.26 #gust=12.26 #lake-u=5.11 #shore-u=8.64
#gust-u=8.64 #mph=11.76 #dot=6.81 #arrow=6.81 #help=11.76`. **Status: fixed and gated.**

## 6. The 6B.2 / 6B.2.1 header fixes (measured before → after)

| symptom | before | after |
| --- | --- | --- |
| verdict row 1 pushed out of the band and clipped | y **−5.5 px** | y **+7.5 px** (inside) |
| Leaflet's top controls sat under the fixed band | y **10 px** | y **92 px** (`calc(var(--header-h) + 10px)`) |
| `.head-text` over-tall → row 1 clipped | **76.3 px** | **60.1 px** |

The `.head-text` shrink came from moving the 52 px `?`-pill reservation off the whole column and
onto the wind row only (`margin-right` on `#three`, not `padding`), so `clientWidth` still equals
the usable row width and the `ink ≤ avail` gate stays meaningful. `#help` is absolutely
positioned so its 44 px hit box cannot inflate the text column. Current measurements:
header `box=72` at both viewports, `#three sw == cw` at both, `#mph` width **19.45 px** (≥ 19
crush detector), and the row's tightest state — wide @360 — carries **14.97 px** of slack.

---

## 7. Open items

1. **One pre-existing, data-dependent gate:** `[14] live seam` runs against the live API. It
   **passed** in this run — `exit=0 dSpeed=0.60 dDir=3.00 | SEAM 2026-09-14 frame=288 dSpeed=0.60
   dDir=3.00 PASS` — with no FAIL to quote.
2. **`#shore-u` / `#gust-u` still use `#cbd5e1`.** They measure 8.64:1 on the shared
   `rgba(148,163,184,.18)` fill, so they clear the gate comfortably — but they are *not* on the
   tier tint, which is why only `#lake-u` needed the 6B.1 fix. No action; recorded so the
   asymmetry is not mistaken for an oversight.
3. **The `#help-pop` outside-tap point is discovered at runtime.** If a future layout puts a
   control across the whole lower map, `[19.10]` reports `NO BARE MAP POINT FOUND` and fails —
   by design, rather than silently tapping a link.
4. **No defect found in `src/**` or `index.html`** during this pass. The one failure this pass
   surfaced was in the harness itself (§4.1), and it is fixed.

---

Changed files: `tools/qa/stage5_check.py`, `tools/qa/live_smoke.py`, `docs/STAGE-6-RECEIPTS.md`.
Evidence: `tmp/s6-shots/` (header @360 and @390, the widest value state @360, popover open @360),
`tmp/scrub-bench/stage6c.json`, `tmp/s6c-harness.log`, `tmp/s6c-bench.log`.
