#!/usr/bin/env python3
"""Render Mille Lacs DNR bathymetry contours (KML) to a transparent PNG raster
that exactly fills the app's lake frame (public/warp.v1.json corners).

Why raster: Leaflet imageOverlay re-anchors its image to the lat/lng bounds on
every move/zoom, so a raster can never drift relative to the basemap (the
stage-6.4 §D3.3 lesson — a custom canvas layer would have to re-derive
ImageOverlay._reset's transform math and that path drifted before).

Usage: python3 tools/export_depth_raster.py <lakefinder.kml>
Writes: public/depth.v1.png (subtle slate lines, alpha baked in, JS opacity 1).
"""
import json
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

WARP = "public/warp.v1.json"
OUT = "public/depth.v1.png"

BASE_W = 1280          # px on the long axis at 1x (≈22 m/px — coarse enough that
                       # hairlines survive phone-fit downscale; sharper would vanish)
SS = 2                 # supersample factor -> 1px AA hairlines after downscale
LINE_RGB = (58, 96, 122)   # desaturated slate blue — reads as "depth" on gray water
LINE_ALPHA = 104           # ~40%: quiet under the wave layer. Tune HERE, not in JS.
DP_EPS_PX = 1.5            # Douglas-Peucker tolerance (1x px): kills source jitter
MIN_LOOP_PX = 6            # drop closed segments smaller than this (1x px) — noise

NS = {"kml": "http://www.opengis.net/kml/2.2"}


def simplify(pts, eps):
    """Iterative Douglas-Peucker on [(x, y), ...] (px coords)."""
    n = len(pts)
    if n < 3:
        return pts
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        norm = (dx * dx + dy * dy) ** 0.5
        dmax, imax = -1.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            if norm == 0.0:  # closed ring: P0 == Pn → chord degenerates to a point
                dist = ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
            else:
                dist = abs(dy * (px - ax) - dx * (py - ay)) / norm
            if dist > dmax:
                dmax, imax = dist, i
        if dmax > eps:
            keep[imax] = True
            stack.append((a, imax))
            stack.append((imax, b))
    return [p for p, k in zip(pts, keep) if k]


def main(kml_path: str) -> None:
    warp = json.load(open(WARP))
    west, north = warp["corners"]["nw"]
    east, south = warp["corners"]["se"]
    mid_lat = (north + south) / 2.0
    w_m = (east - west) * 111320.0 * __import__("math").cos(__import__("math").radians(mid_lat))
    h_m = (north - south) * 110574.0
    W = BASE_W * SS
    H = round(W * h_m / w_m)
    fx = lambda lon: (lon - west) / (east - west) * (W - 1)
    fy = lambda lat: (north - lat) / (north - south) * (H - 1)

    # --- parse KML: bathymetry placemarks are named "<N> ft" ---
    depths = {}  # depth_ft -> list of point-lists
    root = ET.parse(kml_path).getroot()
    for pm in root.iter("{http://www.opengis.net/kml/2.2}Placemark"):
        name = pm.findtext("kml:name", namespaces=NS)
        m = re.fullmatch(r"\s*(\d+)\s*ft\s*", name or "")
        if not m:
            continue
        coords_txt = pm.findtext(".//kml:coordinates", namespaces=NS)
        if not coords_txt:
            continue
        pts = []
        for tok in coords_txt.split():
            lonlat = tok.split(",")
            if len(lonlat) >= 2:
                pts.append((fx(float(lonlat[0])), fy(float(lonlat[1]))))
        if len(pts) < 2:
            continue
        pts = simplify(pts, DP_EPS_PX * SS)  # eps in supersampled px
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if (max(xs) - min(xs) < MIN_LOOP_PX * SS
                and max(ys) - min(ys) < MIN_LOOP_PX * SS):
            continue  # micro-loop / speck: source noise, not a readable contour
        depths.setdefault(int(m.group(1)), []).append(pts)

    if not depths:
        sys.exit("no '<N> ft' placemarks found — wrong KML?")

    # --- draw supersampled, downscale for AA hairlines ---
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    total_lines = 0
    for depth in sorted(depths):
        for pts in depths[depth]:
            d.line(pts, fill=LINE_RGB + (LINE_ALPHA,), width=2 * SS, joint="curve")
            total_lines += 1
    img = img.resize((W // SS, H // SS), Image.Resampling.LANCZOS)
    img = img.quantize(colors=64, method=Image.Quantize.FASTOCTREE)  # indexed PNG: tiny
    img.save(OUT, optimize=True)

    # --- receipt ---
    import os
    xs = [p[0] for lst in depths.values() for pts in lst for p in pts]
    ys = [p[1] for lst in depths.values() for pts in lst for p in pts]
    print(f"levels: {sorted(depths)}")
    print(f"lines: {total_lines}  points: {sum(len(p) for l in depths.values() for p in l)}")
    print(f"contour extent in frame-px: x [{min(xs):.0f}..{max(xs):.0f}] of {W//SS}, "
          f"y [{min(ys):.0f}..{max(ys):.0f}] of {H//SS}")
    print(f"out: {OUT}  {os.path.getsize(OUT)/1024:.0f} KB  {img.size[0]}x{img.size[1]}")


if __name__ == "__main__":
    main(sys.argv[1])
