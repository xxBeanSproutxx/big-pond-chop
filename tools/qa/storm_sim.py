#!/usr/bin/env python3
"""Storm simulation — inflate rain probability to a given % and audit the deck.

Intercepts the live Open-Meteo response (real fetch -> real parse -> real render,
no app-code changes, no fixtures to drift) and sets every hour's
precipitation_probability to --pct. Then measures every day block: does the
curve's apex collide with the % label at full band height?

Born from Reid's question: "what does 90-100% look like?" (Answer: the curve
clamps at the band ceiling — 50%+ renders identically — and the label sits
tangent to the apex. No overlap possible by geometry.)

Run:
  /home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/storm_sim.py --pct 95 \
      --url http://127.0.0.1:8788/ [--shot /tmp/storm.png]

Exit 1 on any label/curve overlap.
"""
import argparse
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pct", type=int, default=95)
    ap.add_argument("--url", default="http://127.0.0.1:8788/index.html")
    ap.add_argument("--horizon", default="7d")
    ap.add_argument("--shot", default="")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    def storm(route):
        r = route.fetch()
        j = r.json()

        def inflate(loc):
            for block in ("hourly", "minutely_15"):
                arr = loc.get(block, {}).get("precipitation_probability")
                if arr:
                    loc[block]["precipitation_probability"] = [
                        args.pct if (v is not None) else None for v in arr]

        # Dual-location responses are a JSON ARRAY of two location objects.
        for loc in j if isinstance(j, list) else [j]:
            inflate(loc)
        route.fulfill(response=r, json=j)

    fails = 0
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        # service_workers="block": the SW would answer data fetches from cache
        # before our route interceptor ever sees them.
        ctx = b.new_context(viewport={"width": 390, "height": 844},
                            device_scale_factor=3, service_workers="block")
        page = ctx.new_page()
        page.route("**api.open-meteo.com/**", storm)
        sep = "&" if "?" in args.url else "?"
        page.goto(f"{args.url}{sep}h={args.horizon}&cb=storm{args.pct}",
                  wait_until="domcontentloaded")
        page.wait_for_function("() => !!document.querySelector('.day-block .day-wind')",
                               timeout=60000)
        page.wait_for_timeout(2500)
        rows = page.evaluate("""() => {
          const out = [];
          for (const blk of document.querySelectorAll('.day-block')) {
            const lbl = blk.querySelector('.day-rain-label');
            const curveBox = blk.querySelector('.day-rain-svg').getBoundingClientRect();
            const ys = blk.querySelector('.day-rain-svg polyline')
              .getAttribute('points').split(' ').map(p => parseFloat(p.split(',')[1]));
            const labelBox = lbl.getBoundingClientRect();
            const apexY = curveBox.top + Math.min(...ys);
            out.push({ label: lbl.textContent, dim: lbl.classList.contains('dim'),
                       clearance: +(apexY - labelBox.bottom).toFixed(1),
                       overlap: apexY < labelBox.bottom - 0.5 });
          }
          return out;
        }""")
        for d in rows:
            flag = "OVERLAP" if d["overlap"] else "ok"
            print(f"  {d['label']:>7} dim={str(d['dim']):5} clearance={d['clearance']:>5}px  {flag}")
            if d["overlap"]:
                fails += 1
        if args.shot:
            deck = page.evaluate(
                "() => { const d = document.getElementById('deck').getBoundingClientRect();"
                " return {y: d.y, h: d.height}; }")
            page.screenshot(path=args.shot,
                            clip={"x": 0, "y": max(0, deck["y"] - 6),
                                  "width": 390, "height": deck["h"] + 12})
            print(f"  screenshot: {args.shot}")
        b.close()
    print(f"VERDICT: {'FAIL ' + str(fails) + ' overlaps' if fails else 'PASS — no overlap at ' + str(args.pct) + '%'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
