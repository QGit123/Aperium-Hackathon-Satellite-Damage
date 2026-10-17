#!/usr/bin/env python3
"""Merge footprints, damage and addresses into web/buildings.geojson.

Usage:
    python3 scripts/merge.py [footprints.geojson] [damage.json] [addresses.json] [out.geojson]

Defaults use the dummy data in data/. Missing damage/address entries get safe
defaults so the frontend never sees a null.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEB = ROOT / "web"

ID_FIELD = "id"
THUMB_DIR = "thumbs"  # relative to web/, so paths work locally and when deployed
DEFAULT_DAMAGE = "none"
DEFAULT_CONFIDENCE = 0.0
UNKNOWN = "Unknown location"
UNKNOWN_TYPE = "unknown"

# Typical heights in metres, used only when the footprint data has no real height.
# Keys are building_type values as written by geocode.py (underscores become spaces).
DEFAULT_HEIGHT = 6.0
HEIGHT_BY_TYPE = {
    "shed": 3, "garage": 3, "garages": 3, "carport": 3, "roof": 3, "hut": 3,
    "cabin": 4, "bungalow": 4, "restaurant": 5, "shop": 5, "kiosk": 3,
    "house": 6, "residential": 6, "detached": 6, "semidetached house": 6,
    "terrace": 7, "building": 7, "retail": 6,
    "industrial": 8, "warehouse": 8, "school": 8, "chapel": 8,
    "civic": 9, "public": 9, "place of worship": 10, "church": 12,
    "commercial": 12, "dormitory": 12, "university": 12,
    "apartments": 15, "hotel": 15, "office": 15, "hospital": 15,
}
LEVEL_HEIGHT_M = 3.0  # metres per storey when the data gives building levels


def number(value):
    """Parse a positive number from a value like 12, '12' or '12 m'; else None."""
    try:
        n = float(str(value).lower().replace("m", "").strip())
    except ValueError:
        return None
    return n if n > 0 else None


def building_height(footprint_props, building_type):
    """Return (height_m, source). Real data wins, then storeys, then type default."""
    h = number(footprint_props.get("height"))
    if h:
        return round(h, 1), "data"
    levels = number(footprint_props.get("levels") or footprint_props.get("building:levels"))
    if levels:
        return round(levels * LEVEL_HEIGHT_M, 1), "estimated"
    return float(HEIGHT_BY_TYPE.get(building_type, DEFAULT_HEIGHT)), "estimated"


def main():
    args = sys.argv[1:]
    footprints = Path(args[0]) if len(args) > 0 else DATA / "dummy_footprints.geojson"
    damage_path = Path(args[1]) if len(args) > 1 else DATA / "dummy_damage.json"
    addr_path = Path(args[2]) if len(args) > 2 else DATA / "addresses.json"
    out = Path(args[3]) if len(args) > 3 else WEB / "buildings.geojson"

    fc = json.loads(footprints.read_text())
    damage = json.loads(damage_path.read_text())
    addresses = json.loads(addr_path.read_text())

    no_damage = no_address = 0
    features = []
    for f in fc["features"]:
        bid = str(f["properties"][ID_FIELD])
        d = damage.get(bid)
        if d is None:
            no_damage += 1
            d = {}
        entry = addresses.get(bid)
        if isinstance(entry, str):  # older addresses.json: {id: address}
            entry = {"address": entry}
        entry = entry or {}
        addr = entry.get("address")
        if not addr:
            no_address += 1
            addr = UNKNOWN
        btype = entry.get("building_type") or UNKNOWN_TYPE
        height, height_source = building_height(f["properties"], btype)
        features.append({
            "type": "Feature",
            "geometry": f["geometry"],
            "properties": {
                "id": bid,
                "damage": d.get("damage", DEFAULT_DAMAGE),
                "confidence": d.get("confidence", DEFAULT_CONFIDENCE),
                "address": addr,
                "building_type": btype,
                "height": height,
                "height_source": height_source,
                "before_img": f"{THUMB_DIR}/{bid}_before.jpg",
                "after_img": f"{THUMB_DIR}/{bid}_after.jpg",
            },
        })

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    print(f"Wrote {out}: {len(features)} buildings "
          f"({no_damage} without damage, {no_address} without address)")


if __name__ == "__main__":
    main()
