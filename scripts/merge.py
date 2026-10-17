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
        addr = addresses.get(bid)
        if not addr:
            no_address += 1
            addr = UNKNOWN
        features.append({
            "type": "Feature",
            "geometry": f["geometry"],
            "properties": {
                "id": bid,
                "damage": d.get("damage", DEFAULT_DAMAGE),
                "confidence": d.get("confidence", DEFAULT_CONFIDENCE),
                "address": addr,
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
