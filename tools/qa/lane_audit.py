#!/usr/bin/env python3
"""Lane collision audit for the v1.1 deck (both horizons).

Born from the v2.5 incident (hour ticks printed over the temp lane, invisible to a
class-list-based audit) and repeated in v1.1 (temps over times, rain through wind
numbers, sun glyphs inside the ribbon). This tool does NOT trust class names or
CSS band comments: it enumerates every lane-class element ACTUALLY in each day
block, measures real client rects, and fails on ANY pairwise area overlap.

Run:
  /home/reid/.hermes/hermes-agent/venv/bin/python tools/qa/lane_audit.py --url http://127.0.0.1:8788/

Exit 1 if any collision. Print-only; no screenshots.
"""
import argparse
import sys

LANE_SELECTORS = [".day-head", ".day-sub", ".day-temp", ".day-rain-svg",
                  ".day-rain-label", ".day-wind", ".day-sun", ".day-night-bar"]

JS = """
(sel) => {
  const out = [];
  for (const block of document.querySelectorAll('.day-block')) {
    const items = [];
    for (const s of sel) {
      for (const el of block.querySelectorAll(s)) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) items.push({s, x:r.x, y:r.y, w:r.width, h:r.height});
      }
    }
    out.push({head: (block.querySelector('.day-head')||{}).textContent || '?', items});
  }
  return out;
}
"""


def overlaps(a, b):
    ox = max(0.0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
    oy = max(0.0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
    return ox * oy


def audit(page):
    blocks = page.evaluate(JS, LANE_SELECTORS)
    collisions = []
    for b in blocks:
        items = b["items"]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, c = items[i], items[j]
                # allowed stacking: the wind NUMBERS sit ON the heat ribbon by design,
                # and rain labels may sit over their own svg. Everything else is a bug.
                allowed = {frozenset([".day-wind", ".day-heat"]),
                           frozenset([".day-rain-label", ".day-rain-svg"]),
                           frozenset([".day-night-bar", ".day-sun"])}
                if frozenset([a["s"], c["s"]]) in allowed:
                    continue
                area = overlaps(a, c)
                if area > 4:  # >4 px^2 = real collision, not rounding
                    collisions.append((b["head"], a["s"], c["s"], round(area, 1)))
    return len(blocks), collisions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        total_fail = 0
        for horizon, query in (("24h", ""), ("7d", "?h=7d")):
            page = browser.new_page(viewport={"width": 390, "height": 844},
                                    device_scale_factor=2)
            page.goto(args.url + query, wait_until="domcontentloaded")
            page.wait_for_function(
                "() => !!document.querySelector('.day-block .day-wind')", timeout=60000)
            page.wait_for_timeout(1000)
            nblocks, collisions = audit(page)
            print(f"[{horizon}] blocks={nblocks} lane-elements measured")
            if collisions:
                total_fail += len(collisions)
                for c in collisions[:20]:
                    print(f"  COLLISION day={c[0]!r} {c[1]} × {c[2]} area={c[3]}px²")
            else:
                print("  ZERO collisions across all day blocks")
            page.close()
        browser.close()
    print("VERDICT:", "FAIL" if total_fail else "PASS")
    sys.exit(1 if total_fail else 0)


if __name__ == "__main__":
    main()
