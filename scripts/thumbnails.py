#!/usr/bin/env python3
"""Crop a before/after thumbnail for every building footprint.

Usage:
    python3 scripts/thumbnails.py [footprints.geojson] [imagery.json] [out_dir]

imagery.json (from A) describes the web-ready pre/post images and their extent:
    {
      "before": {"file": "data/pre.png",  "bounds": [south, west, north, east]},
      "after":  {"file": "data/post.png", "bounds": [south, west, north, east]}
    }
Bounds are lat/lon (WGS84). File paths are relative to imagery.json.

Output: out_dir/{id}_before.jpg and out_dir/{id}_after.jpg (default web/thumbs).
If a crop fails, a grey placeholder is written so no image link is ever broken.
Needs Pillow: pip install pillow
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ID_FIELD = "id"
PAD = 0.5        # extra context around the footprint, as a fraction of its size
MIN_SPAN_M = 25  # never crop tighter than this, so tiny sheds still show surroundings
THUMB_PX = 240   # longest side of the saved thumbnail
M_PER_DEG = 111_000

Image.MAX_IMAGE_PIXELS = None  # satellite images can exceed Pillow's default limit


def polygon_bbox(geom):
    """Return (min_lon, min_lat, max_lon, max_lat) of a Polygon or MultiPolygon."""
    if geom["type"] == "Polygon":
        rings = geom["coordinates"]
    elif geom["type"] == "MultiPolygon":
        rings = [r for poly in geom["coordinates"] for r in poly]
    else:
        raise ValueError(f"Unsupported geometry type: {geom['type']}")
    pts = [p for ring in rings for p in ring]
    lons, lats = [p[0] for p in pts], [p[1] for p in pts]
    return min(lons), min(lats), max(lons), max(lats)


def padded_box(bbox, lat):
    """Pad the bbox and enforce a minimum size (in degrees, using local scale)."""
    min_lon, min_lat, max_lon, max_lat = bbox
    cx, cy = (min_lon + max_lon) / 2, (min_lat + max_lat) / 2
    lon_per_m = 1 / (M_PER_DEG * max(0.01, math.cos(math.radians(lat))))
    lat_per_m = 1 / M_PER_DEG
    half_w = max((max_lon - min_lon) * (1 + PAD) / 2, MIN_SPAN_M * lon_per_m / 2)
    half_h = max((max_lat - min_lat) * (1 + PAD) / 2, MIN_SPAN_M * lat_per_m / 2)
    return cx - half_w, cy - half_h, cx + half_w, cy + half_h


def to_pixels(box, bounds, size):
    """Convert a lon/lat box to a pixel box. Image top-left = (west, north)."""
    south, west, north, east = bounds
    w, h = size
    min_lon, min_lat, max_lon, max_lat = box
    left = (min_lon - west) / (east - west) * w
    right = (max_lon - west) / (east - west) * w
    top = (north - max_lat) / (north - south) * h
    bottom = (north - min_lat) / (north - south) * h
    return left, top, right, bottom


def crop(img, bounds, box):
    left, top, right, bottom = to_pixels(box, bounds, img.size)
    left, top = max(0, round(left)), max(0, round(top))
    right, bottom = min(img.width, round(right)), min(img.height, round(bottom))
    if right - left < 2 or bottom - top < 2:
        raise ValueError("footprint is outside the image")
    out = img.crop((left, top, right, bottom)).convert("RGB")
    out.thumbnail((THUMB_PX, THUMB_PX))
    return out


def placeholder():
    img = Image.new("RGB", (THUMB_PX, THUMB_PX), (200, 200, 200))
    ImageDraw.Draw(img).text((THUMB_PX // 2 - 40, THUMB_PX // 2 - 5), "no image", fill=(90, 90, 90))
    return img


def load(entry, base):
    path = base / entry["file"]
    s, w, n, e = entry["bounds"]
    if not (s < n and w < e):
        raise ValueError(f"bounds for {path.name} must be [south, west, north, east]")
    return Image.open(path), entry["bounds"]


def main():
    args = sys.argv[1:]
    footprints = Path(args[0]) if len(args) > 0 else ROOT / "data" / "footprints.geojson"
    imagery_path = Path(args[1]) if len(args) > 1 else ROOT / "data" / "imagery.json"
    out_dir = Path(args[2]) if len(args) > 2 else ROOT / "web" / "thumbs"

    imagery = json.loads(imagery_path.read_text())
    sources = {}
    for name in ("before", "after"):
        img, bounds = load(imagery[name], imagery_path.parent)
        sources[name] = (img, bounds)
        print(f"{name}: {imagery[name]['file']} {img.size} bounds={bounds}")

    out_dir.mkdir(parents=True, exist_ok=True)
    features = json.loads(footprints.read_text())["features"]
    failed = 0
    for f in features:
        bid = str(f["properties"][ID_FIELD])
        bbox = polygon_bbox(f["geometry"])
        box = padded_box(bbox, (bbox[1] + bbox[3]) / 2)
        for name, (img, bounds) in sources.items():
            try:
                thumb = crop(img, bounds, box)
            except Exception as e:
                print(f"{bid} {name}: {e}, using placeholder")
                thumb, failed = placeholder(), failed + 1
            thumb.save(out_dir / f"{bid}_{name}.jpg", quality=85)

    print(f"Wrote {len(features) * 2} thumbnails to {out_dir} ({failed} placeholders)")


if __name__ == "__main__":
    main()
