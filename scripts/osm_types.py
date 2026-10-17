#!/usr/bin/env python3
"""Look up building type, levels and height from OpenStreetMap polygons.

Usage:
    python3 scripts/osm_types.py [footprints.geojson] [osm_types.json]

Downloads OSM building outlines for the footprints' area once (Overpass API),
caches the raw response in data/osm_raw.json, and matches each footprint to the
OSM building that contains its centroid. Writes {id: {building_type, levels, height}};
buildings with no OSM match are omitted. No API key needed. Standard library only.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_PATH = DATA / "osm_raw.json"

ID_FIELD = "id"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "damage-map-hackathon/0.1"
MARGIN_DEG = 0.0005  # ~50 m around the footprints
# If building=yes, the use of the building may still be in one of these tags.
USE_TAGS = ("amenity", "shop", "office", "tourism", "leisure", "healthcare", "craft")
GENERIC = {"yes", "building"}


def centroid(geom):
    ring = geom["coordinates"][0] if geom["type"] == "Polygon" else geom["coordinates"][0][0]
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def point_in_ring(x, y, ring):
    """Ray casting. ring is a list of (x, y)."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def fetch(bbox):
    s, w, n, e = bbox
    query = f'[out:json][timeout:90];way["building"]({s},{w},{n},{e});out tags geom;'
    req = urllib.request.Request(
        OVERPASS_URL,
        data=urllib.parse.urlencode({"data": query}).encode(),
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def osm_type(tags):
    b = tags.get("building", "yes")
    if b in GENERIC:
        for key in USE_TAGS:
            if key in tags and tags[key] != "yes":
                return tags[key].replace("_", " ")
        return "building"
    return b.replace("_", " ")


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA / "footprints.geojson"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else DATA / "osm_types.json"
    features = json.loads(src.read_text())["features"]

    cents = {str(f["properties"][ID_FIELD]): centroid(f["geometry"]) for f in features}
    lons = [c[0] for c in cents.values()]
    lats = [c[1] for c in cents.values()]
    bbox = (min(lats) - MARGIN_DEG, min(lons) - MARGIN_DEG, max(lats) + MARGIN_DEG, max(lons) + MARGIN_DEG)

    if RAW_PATH.exists():
        print(f"Using cached {RAW_PATH.name} (delete it to re-download)")
        raw = json.loads(RAW_PATH.read_text())
    else:
        print("Downloading OSM buildings for", [round(v, 5) for v in bbox])
        raw = fetch(bbox)
        RAW_PATH.write_text(json.dumps(raw))

    polys = []
    for el in raw.get("elements", []):
        geom = el.get("geometry")
        if el.get("type") != "way" or not geom or len(geom) < 4:
            continue
        ring = [(p["lon"], p["lat"]) for p in geom]
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        polys.append((min(xs), min(ys), max(xs), max(ys), ring, el.get("tags", {})))
    print(f"{len(polys)} OSM buildings downloaded")

    out = {}
    for bid, (x, y) in cents.items():
        for x0, y0, x1, y1, ring, tags in polys:
            if x0 <= x <= x1 and y0 <= y <= y1 and point_in_ring(x, y, ring):
                out[bid] = {
                    "building_type": osm_type(tags),
                    "levels": tags.get("building:levels"),
                    "height": tags.get("height"),
                }
                break

    dst.write_text(json.dumps(out, indent=2))
    typed = sum(1 for v in out.values() if v["building_type"] != "building")
    print(f"Matched {len(out)}/{len(cents)} footprints to an OSM building; "
          f"{typed} have a specific type, "
          f"{sum(1 for v in out.values() if v['levels'])} levels, "
          f"{sum(1 for v in out.values() if v['height'])} heights")
    from collections import Counter
    print(Counter(v["building_type"] for v in out.values()).most_common(10))
    print(f"Wrote {dst}")


if __name__ == "__main__":
    main()
