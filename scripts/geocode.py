#!/usr/bin/env python3
"""Reverse-geocode building centroids with LocationIQ.

Usage:
    Put LOCATIONIQ_KEY=your_key_here in .env at the repo root (copy .env.example),
    or export it in your shell, then:
    python3 scripts/geocode.py [footprints.geojson] [addresses.json]

Defaults to the dummy footprints. Results are cached per id in
data/geocode_cache.json, so reruns and crashes only fetch what's missing.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Assumptions agreed with A: ids are strings in properties.id, coords are lon/lat WGS84.
ID_FIELD = "id"
USER_AGENT = "damage-map-hackathon/0.1"
GEOCODER_URL = "https://us1.locationiq.com/v1/reverse"  # Nominatim-compatible response format
ROOT = Path(__file__).resolve().parent.parent


def load_env(path):
    """Read KEY=value lines from a .env file into os.environ (real env vars win)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_env(ROOT / ".env")
API_KEY = os.environ.get("LOCATIONIQ_KEY")
DELAY_SECONDS = 0.6  # LocationIQ free tier: max 2 requests/sec
UNKNOWN = "Unknown location"
UNKNOWN_TYPE = "unknown"
# Geocoder classes whose 'type' describes a building or its use (school, shop, ...).
POI_CLASSES = {"amenity", "shop", "office", "tourism", "leisure", "historic",
               "craft", "healthcare", "man_made", "emergency"}

DATA = Path(__file__).resolve().parent.parent / "data"
CACHE_PATH = DATA / "geocode_cache.json"


def centroid(geom):
    """Return (lon, lat) as the mean of the outer ring's vertices."""
    if geom["type"] == "Polygon":
        ring = geom["coordinates"][0]
    elif geom["type"] == "MultiPolygon":
        ring = geom["coordinates"][0][0]
    else:
        raise ValueError(f"Unsupported geometry type: {geom['type']}")
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError(
            f"Centroid ({lon}, {lat}) is not valid lon/lat. Is the file in EPSG:4326?"
        )
    return lon, lat


def format_address(data):
    """Best available address: house+road, near road, neighbourhood, unknown."""
    a = data.get("address") or {}
    road = a.get("road") or a.get("pedestrian") or a.get("footway")
    area = (
        a.get("neighbourhood") or a.get("suburb") or a.get("quarter")
        or a.get("village") or a.get("town") or a.get("city")
    )
    if a.get("house_number") and road:
        base = f"{a['house_number']} {road}"
    elif road:
        base = f"near {road}"
    elif area:
        return f"near {area}"
    else:
        return UNKNOWN
    return f"{base}, {area}" if area else base


def building_type(data):
    """Friendly type from the geocoder's class/type, e.g. 'house', 'school', 'building'.

    Returns 'unknown' when the nearest feature isn't a building (e.g. a road).
    """
    cls, typ = data.get("class"), data.get("type")
    if cls == "building":
        return "building" if typ in (None, "yes", "building") else typ.replace("_", " ")
    if cls in POI_CLASSES and typ and typ != "yes":
        return typ.replace("_", " ")
    if cls == "place" and typ == "house":
        return "house"
    return UNKNOWN_TYPE


def reverse(lon, lat):
    params = urllib.parse.urlencode(
        {"key": API_KEY, "format": "json", "lat": lat, "lon": lon, "zoom": 18, "addressdetails": 1}
    )
    req = urllib.request.Request(f"{GEOCODER_URL}?{params}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def main():
    if not API_KEY:
        sys.exit("No key found. Add LOCATIONIQ_KEY=your_key_here to .env (see .env.example)")
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA / "dummy_footprints.geojson"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else DATA / "addresses.json"

    features = json.loads(src.read_text())["features"]
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}

    # Old cache entries were plain address strings with no building_type: refetch them.
    cache = {k: v for k, v in cache.items() if isinstance(v, dict)}
    todo = [f for f in features if str(f["properties"][ID_FIELD]) not in cache]
    print(f"{len(features)} buildings, {len(cache)} cached, {len(todo)} to fetch "
          f"(~{int(len(todo) * DELAY_SECONDS)}s)")

    for i, f in enumerate(todo, 1):
        bid = str(f["properties"][ID_FIELD])
        lon, lat = centroid(f["geometry"])
        try:
            result = reverse(lon, lat)
            entry = {"address": format_address(result), "building_type": building_type(result)}
        except Exception as e:  # network error, 429, etc.: don't cache, retry on next run
            print(f"[{i}/{len(todo)}] {bid}: FAILED ({e})")
            time.sleep(DELAY_SECONDS)
            continue
        cache[bid] = entry
        CACHE_PATH.write_text(json.dumps(cache, indent=2))  # save after every request
        print(f"[{i}/{len(todo)}] {bid}: {entry['address']} [{entry['building_type']}]")
        time.sleep(DELAY_SECONDS)

    # Every building gets an entry, even if its request failed.
    fallback = {"address": UNKNOWN, "building_type": UNKNOWN_TYPE}
    out = {str(f["properties"][ID_FIELD]): cache.get(str(f["properties"][ID_FIELD]), fallback)
           for f in features}
    dst.write_text(json.dumps(out, indent=2))
    missing = sum(1 for f in features if str(f["properties"][ID_FIELD]) not in cache)
    print(f"Wrote {dst} ({missing} failed, rerun to retry)" if missing else f"Wrote {dst}")


if __name__ == "__main__":
    main()
