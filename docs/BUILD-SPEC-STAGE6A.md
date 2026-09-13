# BUILD SPEC — Stage 6A: dual-location wind ingest (lake + shore) in ONE batched request

Repo: `/home/reid/projects/big-pond-chop`, branch `stage6` (off `main` @ `89e3a2d`).
Reid's Stage 6 sign-off is APPROVED (decisions D1–D14 locked; a summary of the ones that matter to you is in
"Contract" below). **This leaf is DATA ONLY** —
no header/DOM/CSS work (that is 6B).

## Goal

Fetch **both** wind profiles — the existing mid-lake point and a new shore point — in **one** Open-Meteo
GET, expose the shore series beside the lake series, and leave everything that consumes the lake series
byte-for-byte unchanged in behaviour.

## Contract (frozen)

- `SHORE_POINT = { lat: 46.13, lon: -93.57 }` — approved, verified on land (644 m from the nearest water,
  South Harbor Township / Isle MN). Do not move it waterward.
- The **lake point stays `DEFAULT_POINT` (46.22, -93.657)**. It is the physics input and MUST NOT move in
  this stage — the header's "Lake" pill displays this exact series.
- **URL**: one request, comma-joined coordinates, params in this order —
  `latitude=<lake>,<shore>&longitude=<lake>,<shore>&hourly=…&minutely_15=…&wind_speed_unit=mph&timezone=America%2FChicago&past_days=1&forecast_days=<2|7>`.
  `forecast_days` stays the **last** param: `tests/wind.test.js` `[1e]` asserts
  `buildUrl(1,2).endsWith('forecast_days=2')` and **must keep passing unchanged**. Keep the existing
  `buildUrl(lat, lon, horizon)` semantics intact and add the dual-location builder next to it.
- **Response shape (verified live)**: a top-level JSON **ARRAY of 2 objects**, 72 hourly rows each,
  same field names as today. ⚠️ **Index 0 has NO `location_id` field; index 1 has `location_id: 1`** →
  parse by **array index** (0 = lake, 1 = shore), never by `location_id`.
- New pure helper, exported: `parseTwoLocations(json)` → `{ lake, shore }`, where each side is the raw
  location object (or `null`). Must validate `Array.isArray` and length.
- `ingest()` return value: the existing fields **unchanged** — `day` is still the lake series with the
  same 96/672 length, same 15-min grid, same entry shape (`time, speedMph, gustMph, dirTrueDeg, bearingGrid,
  tEffH`) — **plus a new parallel `shoreDay`** built through the SAME `buildSeriesFrom` path so the entry
  shape is identical and no second code path exists. `shoreDay` must be the same length as `day` with
  matching timestamps.
- **Failure modes (fail open, never throw):** non-array response, array of length < 2, missing/null
  `wind_speed_10m` for the shore location, or a fetch error on the whole request → `shoreDay = null`
  and `day` behaves exactly as today (one `console.warn`). Nothing else in the app may see a different
  behaviour than before this stage.
- **Exactly ONE network round-trip per ingest.** No second fetch, no retry, no cache added.

## Tests to add (`tests/wind.test.js`)

1. Dual URL: contains both latitudes and both longitudes; still `.endsWith('forecast_days=2')` / `=7`;
   single-location `buildUrl` output unchanged.
2. `parseTwoLocations` against a fixture shaped like the LIVE response — **index 0 WITHOUT `location_id`,
   index 1 WITH it** → returns `{lake: <index 0>, shore: <index 1>}` (proves index-keying).
3. Malformed payloads (object not array; array of 1; shore series all null) → `shoreDay === null`, no throw.
4. Single fetch: stub global `fetch`, call `ingest`, assert **`fetch` called exactly once** and the URL
   carries both coordinates.
5. `shoreDay.length === day.length` and `shoreDay[i].time === day[i].time` on a synthetic fixture.

Every existing case must keep passing **unchanged** — in particular `[1e]` (URL suffix), `[4]` (live ingest,
exactly 96 frames) and `[3b]` (7d window 672). Do not touch those cases.

## Files allowed to touch

`src/wind.js`, `tests/wind.test.js`. **Nothing else.** `src/render.js` is NOT touched in 6A — the shore
point lives inside `wind.js`, so the ingest call site is unchanged. If you believe another file must change,
STOP and report why instead of editing it.

## Done-when (print these lines verbatim)

1. `node tests/parity.test.js && node tests/wind.test.js && node tests/render.test.js && node tests/ui.test.js`
   → all exit 0 (print each tail).
2. A one-command live check (node one-liner or small script under `tmp/`) that prints:
   the number of `fetch` calls made (must be **1**), the coordinates the API echoed for both entries,
   and the current-hour `lake` vs `shore` speed in mph (raw numbers).
3. `git diff --stat` — only the two allowed files (+ the committed spec).
4. `git log --oneline -3` — no merge, no tag, no push.
5. `git status --porcelain` — clean.

## Procedure

- **You MUST edit `src/wind.js` and `tests/wind.test.js`.** A run that only reads files and exits is a
  failure, not a deliverable — the orchestrator checks for actual diffs.
- **Do not try to read files outside this repository** (anything under `~/.gstack/`, `~/.hermes/`, `/tmp/`):
  the permission wall auto-rejects them and wastes your budget. Everything you need is in this spec.
- When the suites below are green, commit: `git add src/wind.js tests/wind.test.js && git commit -m
  "stage6a: dual-location wind ingest (shore + lake in one request)"`.
- Follow the **ponytail** ruleset (laziest correct implementation — do not add options, config or
  abstractions nobody asked for).
- **Do NOT merge, tag or push** — the orchestrator owns that.
- If a number in this spec conflicts with observed reality, trust reality and report the conflict.
- Report the ACTUAL shipped function signatures and the `ingest()` return shape in your summary.
