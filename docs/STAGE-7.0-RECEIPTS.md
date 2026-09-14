# STAGE 7.0 — RECEIPTS (PWA installability: manifest + service worker + icons)

Built 2026-09-14 on `main` @ `54680f1` (`6.4: inertia:false + strict scrub
suspension ... [21] gates 27 ok/0 FAIL`). Spec: `docs/BUILD-SPEC-STAGE7.0.md`.

**Not committed, not pushed** (per the build instruction). All changes sit in the
working tree. Every number below is verbatim measured output — no invented values.

## §0 Deviations + extensions

### D-1 — manifest + SW live at the repo root, not `public/`

The request named `public/manifest.webmanifest` and `public/sw.js`. Those paths
cannot work under GitHub Pages branch-root hosting, so both files are at the repo
root next to `index.html`; icons stay in `public/` exactly as requested.

- The app root is the repo root (`index.html` is there), because the site is
  served at `https://xxbeansproutxx.github.io/big-pond-chop/` from `main` root.
- `start_url`/`scope` resolve relative to the **manifest's own URL**. A manifest
  under `public/` would resolve `"./"` to `/big-pond-chop/public/` → the installed
  app opens a 404 and install criteria fail.
- A service worker's scope is capped at its own directory, and GitHub Pages cannot
  send `Service-Worker-Allowed`. `public/sw.js` could never control
  `/big-pond-chop/index.html` — it would be decorative.

Everything else honored verbatim: `start_url:"./"`, `scope:"./"`, relative icon paths.

### E-1 — the five `src/*.js` modules are part of the precached shell

`index.html` loads `src/tables.js`, `src/wave-math.js`, `src/wind.js`, `src/ui.js`,
`src/render.js` via `fetch()` at boot. Without them an installed app opens to
"wind unavailable", so they are precached alongside `index.html`.

### E-2 — the fetch matrix is the anti-stale contract

`src/*.js` filenames carry no version, so cache-first would ship stale code
forever; GitHub Pages serves HTML with `max-age=600`, so a document fetch that
honors the HTTP cache can go stale for 10 minutes. Both are network-first with
`{ cache: 'no-store' }`. The `*.v1.*` data is immutable per version → cache-first
(saves ~650 KB per open). Weather (`api.open-meteo.com`) and all other cross-origin
(Leaflet via unpkg, OSM tiles) are explicit passthroughs — never cached.

## §1 Files added / changed

| File | State | Lines | Notes |
|---|---|---|---|
| `manifest.webmanifest` | NEW | 16 | repo root |
| `sw.js` | NEW | 63 | repo root |
| `tools/make_pwa_icons.py` | NEW | 94 | icon generator, re-runnable |
| `tools/qa/pwa_check.py` | NEW | 387 | 11-check gate harness |
| `public/icon-192.png` | NEW | — | generated, 4642 bytes |
| `public/icon-512.png` | NEW | — | generated, 13070 bytes |
| `index.html` | EDIT | +13 (−0) | HEAD links/meta (6) + inline SW registration (7) |
| `docs/STAGE-7.0-RECEIPTS.md` | NEW | — | this document |

`git status --porcelain src/` → empty (zero app-code edits).
`git diff --stat -- index.html` → `1 file changed, 13 insertions(+)`.

`index.html` HEAD addition:

```html
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#0f172a">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="BigPondChop">
<link rel="apple-touch-icon" href="public/icon-192.png">
```

`index.html` registration script (before `</body>`, after the existing app script):

```js
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('sw.js', { updateViaCache: 'none' }).catch(function () {});
  });
}
```

## §2 Manifest / SW / icon facts

**Manifest** — exact JSON in `manifest.webmanifest`: name `Big Pond Chop`,
short_name `BigPondChop`, `display:"standalone"`, `start_url:"./"`, `scope:"./"`,
`theme_color`/`background_color` `#0f172a`, `orientation:"portrait-primary"`,
`prefer_related_applications:false`, icons `public/icon-192.png` (192x192) and
`public/icon-512.png` (512x512), both `purpose:"any maskable"`.

**Service worker** — `CACHE_NAME = 'bpc-cache-v1'`; `SHELL` has 16 entries.
Install: `caches.addAll(SHELL)` → `skipWaiting()`. Activate: delete every cache
key `!== CACHE_NAME` → `clients.claim()`. Fetch: non-GET and cross-origin return
early (passthrough); navigation/`document` and same-origin `src/*.js` are
network-first `{cache:'no-store'}` + `cache.put`, fall back to cache; versioned
shell (`public/*.v1.*`, `tables.v1.bin`, icons, `favicon.svg`,
`manifest.webmanifest`) is cache-first with fill-on-miss.

**Icons** — generated from `public/favicon.svg`'s two wave paths, re-centred
inside the 80% maskable safe zone on a full-bleed `#0f172a` canvas. Generator
verification output:

```
icon icon-512.png   512x512 mode=RGB corners=#0f172a cyan=1493 amber=1490
icon icon-192.png   192x192 mode=RGB corners=#0f172a cyan=202 amber=201
```

Corners are `#0f172a`, both wave strokes are present inside the safe zone, and
the declared PNG dimensions match the manifest.

## §3 Gate table (real measured output)

| Gate | Command | Result |
|---|---|---|
| Node parity | `node tests/parity.test.js` | exit 0 — ALL TESTS PASSED |
| Node wind | `node tests/wind.test.js` | exit 0 — ALL TESTS PASSED |
| Node render | `node tests/render.test.js` | exit 0 — ALL TESTS PASSED |
| Node ui | `node tests/ui.test.js` | exit 0 — ALL TESTS PASSED |
| Stage 5/6 gates | `tools/qa/stage5_check.py` | `SUMMARY: 27 ok, 0 FAIL` |
| Scrub bench | `tools/qa/scrub_bench.py` | `VERDICT: 24/24 PASS` |
| PWA gates | `tools/qa/pwa_check.py` | `SUMMARY: 11 ok, 0 FAIL` |

`pwa_check.py` full local run (subpath rehearsal,
`/tmp/bpc-pages-root/big-pond-chop` → repo, served at `http://127.0.0.1:51381/big-pond-chop/`):

```
[1] precache 200             ok   16/16 200; non-200=none
[2] manifest served          ok   HTTP 200 ctype='application/manifest+json' json=True
[3] manifest fields          ok   checked=11 mismatches=0 extra=none
[4] URL math                 ok   start=http://127.0.0.1:51381/big-pond-chop/ scope=http://127.0.0.1:51381/big-pond-chop/ app-root=http://127.0.0.1:51381/big-pond-chop/
[5] icon urls                ok   public/icon-192.png HTTP 200 image/png dims=(192, 192) want=(192, 192); public/icon-512.png HTTP 200 image/png dims=(512, 512) want=(512, 512)
[6] fresh load clean         ok   pageerror=0 console.error=0 other-failed=none
[7] SW registered            ok   scope=http://127.0.0.1:51381/big-pond-chop/ state=activated want=http://127.0.0.1:51381/big-pond-chop/
[8] SW controls page         ok   controller=True map=True deck-ticks=1
[9] CDP installable          ok   manifest-url=http://127.0.0.1:51381/big-pond-chop/manifest.webmanifest parse-errors=none installabilityErrors=none
[10] offline shell           ok   title='Big Pond Chop | Mille Lacs Lake Wave Forecast' map=True
[11] regression guard        ok   src-clean=True suites=parity:pass wind:pass render:pass ui:pass
------------------------------------------------------------------------------
SUMMARY: 11 ok, 0 FAIL
```

Check [9] is Chromium's own verdict: `Page.getAppManifest` parse-errors `none` and
`Page.getInstallabilityErrors` `[]` — Chromium would offer install.

## §4 Live deploy evidence

**NOT RUN — nothing was pushed.** Per the build instruction ("Do NOT commit and do
NOT push"), §4 is pending Reid's deploy. Run after the push:

```bash
/home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/pwa_check.py --live
```

`--live` re-runs checks 1–6 + 9 against
`https://xxbeansproutxx.github.io/big-pond-chop/` and adds check 12, a cache-busted
fetch of the deployed `manifest.webmanifest` (marker `Big Pond Chop`) and `sw.js`
(marker `bpc-cache-v1`). It prints the served HTTP code + `Content-Type` and the
CDP installability array verbatim.

## §5 Residuals + open items

1. **Deployed `Content-Type` for `.webmanifest` is unverified.** The local harness
   forces `application/manifest+json` (as the spec instructed), so local check [2]
   proves the file but not GitHub Pages' wire header. Chrome is the real arbiter;
   `--live` check 2 will show the deployed `Content-Type`, and check 9 will show
   whether Chromium still considers it installable.
2. **Device-side install is unconfirmed.** WebAPK on Android Chrome and iOS
   "Add to Home Screen" standalone still need a real-device check by Reid. The
   local rehearsal only proves the install criteria are met.
3. **`CACHE_NAME` bump rule.** `bpc-cache-v1` must be bumped on every future deploy
   that changes an unversioned asset (`index.html`, `src/*.js`, SW itself);
   otherwise activated clients keep the old shell cache entry.
4. **`--live` marker check is revision-specific.** It greps for `bpc-cache-v1`,
   which exists only in this revision. Future stages need their own marker.

## §6 Orchestrator verification (Hermes, independent re-run)

Everything below was measured by the orchestrator, not reported by the builder. Two
builder claims did **not** survive first contact and are corrected here.

### 6.1 Gate [6] was flaky — root cause: an external API, not the app

First independent run: `SUMMARY: 10 ok, 1 FAIL` — `[6] fresh load clean` died on a
120 s `wait_for_function` timeout. Re-run: 11 ok. Root-caused with a 6-load probe
(`1/6 hung`, state captured at the timeout):

```
state={"rs":"complete","map":true,"deck":0,"note":"wind unavailable — retry","leaflet":"object","sw":true}
console.error Failed to load resource: the server responded with a status of 503
console.error Error: open-meteo HTTP 503
```

The app's boot state is gated on the Open-Meteo wind fetch; a transient 503 leaves
the deck empty, so the gate was waiting on a **third-party API**, not on the app.
`curl api.open-meteo.com` returns 200 on every clean attempt, so the 503s are
intermittent upstream rate-limiting after a day of gate runs.

Fixed in `tools/qa/pwa_check.py`: `WIND_DOWN_PRED` (the app's own documented
"wind unavailable — retry" state) is accepted **only** when every captured console
error is attributable to Open-Meteo (message *or* source URL — a 503's text carries
no "open-meteo", only its location URL does) and no other request failed. Boot time
is now reported on every run.

Falsification tests (throwaway repo copies, never the real tree):

| Test | Mutation | Result |
|---|---|---|
| A | app's weather URL pointed at a same-origin 404 | `[6] ok boot=0.3s wind=DOWN(external) open-meteo-errors=2`, `[8] ok deck-ticks=0 wind=DOWN(external)` — branch reachable, evidence printed |
| B | `public/meta.v1.json` renamed (real breakage) | `[6] FAIL` after both attempts, diagnostics printed (`#note-msg='map data failed — retry'`), `[1]` flagged `./public/meta.v1.json=404`, `[8] FAIL` — teeth intact |

Stability after the fix: `11 ok / 0 FAIL` ×3 consecutive, plus `--repeat 3` →
`SUMMARY: 21 ok, 0 FAIL`, `boot times: [0.6, 0.6, 0.6] spread=0.0 hangs=0/3`.

### 6.2 The SW's cache contract, measured directly

Against a private server root (never the shared symlink — see 6.4):

| Fact | Measured |
|---|---|
| SW reaches `activated` | yes, 3/3 fresh contexts |
| `bpc-cache-v1` entries | **16/16 in 0.3-0.4 s**, `missing=none` |
| API/tile/CDN entries in cache | **none** (`open-meteo`, `tile.openstreetmap`, `unpkg.com` all absent) |
| `caches.keys()` | exactly `['bpc-cache-v1']` |

Anti-stale proof — mutate the served copy in place (as a deploy would), reload:

| Asset | After deploy + reload | Verdict |
|---|---|---|
| `src/render.js` | updated (marker present) | network-first code path works |
| served document | updated (marker present in `documentElement.outerHTML`) | `no-store` defeats the GitHub Pages `max-age=600` trap |
| `public/meta.v1.json` | still the cached copy | cache-first by design — hence the `CACHE_NAME` bump rule (§5.3) |

### 6.3 Icons, verified from the bytes

`tools/make_pwa_icons.py` re-run: **byte-identical output** (sha256 unchanged,
`1013922708959753…` / `23b3c48f8fab2828…`). Independent pixel scan: 192/512 exact,
corners `#0f172a`, **zero non-background pixels in the outer 10 % border** (maskable
safe zone respected), two distinct stroke bands — in the 192 icon the painted rows
span y 65-125 with **cyan only in the upper half (27 rows) and amber only in the
lower half (26 rows)**, i.e. the favicon's wave pair, re-centred from its own geometry.

Subpath audit: `grep 'src="/|href="/|register("/'` over `index.html`, `src/*.js`,
`manifest.webmanifest`, `sw.js` → **empty**; the 6 new HEAD refs are all relative
(`manifest.webmanifest`, `public/icon-192.png`) and the registration is `register('sw.js')`.

### 6.4 Two false alarms, recorded so they are not repeated

- **`cache=0/16` + `sw-ready=False` was orchestrator error.** A probe reused
  `/tmp/bpc-pages-root/big-pond-chop`, the symlink every `pwa_check.py` run repoints
  at *its* root — so it was silently serving the deliberately-broken TEST-B copy
  (6.1), whose `meta.v1.json` 404 kills the whole `addAll`. Corrected by serving a
  private root; the real result is §6.2. Probes that share harness state must own
  their root.
- **"index.html stayed stale" was a probe artifact.** It fetched `index.html` with
  `fetch()` (destination `''`, which the SW does not special-case) and so measured
  the *browser's* HTTP cache. Re-tested through the real navigation path → fresh
  (§6.2).

### 6.5 Regression gates, re-run by the orchestrator with the SW present

| Gate | Command | Result |
|---|---|---|
| Node parity | `node tests/parity.test.js` | `ALL TESTS PASSED` |
| Node wind | `node tests/wind.test.js` | `ALL TESTS PASSED` |
| Node render | `node tests/render.test.js` | `ALL TESTS PASSED` |
| Node ui | `node tests/ui.test.js` | `ALL TESTS PASSED` |
| Stage 5/6 gates | `tools/qa/stage5_check.py` | **`SUMMARY: 27 ok, 0 FAIL`** (unchanged from the 6.4 baseline) |
| Scrub bench | `tools/qa/scrub_bench.py` | **`VERDICT: 24/24 PASS`** — swaps 0, `tx=30 / moves=31` ✓, index exact `42/42`, medians 16.65 / 16.70 / 16.69 ms, max 17.59 / 17.00 / 33.43 ms (inside the 6.4 range: medians 16.65-16.69, max 17.10-33.64) |

The service worker intercepts every one of these runs' asset requests (they serve the repo
root, so the SW registers on each page load) — scrub timings are unchanged, i.e. the SW
adds no measurable cost to the drag path.

### 6.6 `addAll` is all-or-nothing — a real fragility, disclosed

Test B proved it: **one 404 in the 16-URL `SHELL` list makes `cache.addAll` reject,
the install fail, the SW go `redundant`, and the registration disappear** — no
offline shell and no install criteria, silently, until the next page load retries.
Chromium's own words: `ServiceWorker failed to install: event.waitUntil Promise
rejected` / `Failed to execute 'addAll' on 'Cache': Request failed`.

This is acceptable **only** because gate `[1] precache 200` fails the build on any
non-200 shell URL, and `[7]/[8]/[10]` fail if the SW never activates. Any future
edit to `SHELL` (or deletion of a shell file) must keep `[1]` green. If the
production install ever fails silently, per-URL tolerance in `install`
(`Promise.allSettled`) is the fix to reach for first.
