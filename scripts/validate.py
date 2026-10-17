#!/usr/bin/env python3
"""Validate buildings.geojson against the shared schema.

Usage:
    python3 scripts/validate.py [buildings.geojson]

Exits non-zero if any hard error is found. Missing thumbnail files are only
warnings until thumbnails are generated; pass --strict to make them errors.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

DAMAGE_CLASSES = {"none", "minor", "major", "destroyed"}
REQUIRED = ["id", "damage", "confidence", "address", "building_type", "before_img", "after_img"]


def main():
    strict = "--strict" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = Path(args[0]) if args else WEB / "buildings.geojson"

    fc = json.loads(path.read_text())
    errors, warnings = [], []
    seen = set()
    counts = Counter()

    for i, f in enumerate(fc.get("features", [])):
        p = f.get("properties", {})
        label = p.get("id", f"#{i}")

        for key in REQUIRED:
            if key not in p or p[key] in (None, ""):
                errors.append(f"{label}: missing {key}")

        if p.get("id") in seen:
            errors.append(f"{label}: duplicate id")
        seen.add(p.get("id"))

        if p.get("damage") not in DAMAGE_CLASSES:
            errors.append(f"{label}: bad damage class {p.get('damage')!r}")
        else:
            counts[p["damage"]] += 1

        c = p.get("confidence")
        if not isinstance(c, (int, float)) or not 0 <= c <= 1:
            errors.append(f"{label}: confidence {c!r} not in [0, 1]")

        if p.get("address") == "Unknown location":
            warnings.append(f"{label}: address unknown")

        if f.get("geometry", {}).get("type") not in ("Polygon", "MultiPolygon"):
            errors.append(f"{label}: geometry is not a polygon")

        for key in ("before_img", "after_img"):
            img = p.get(key)
            if img and not (path.parent / img).exists():
                (errors if strict else warnings).append(f"{label}: {key} file not found ({img})")

    total = len(fc.get("features", []))
    print(f"{total} buildings: " + ", ".join(f"{k}={counts[k]}" for k in sorted(DAMAGE_CLASSES)))
    for w in warnings[:20]:
        print("WARN ", w)
    if len(warnings) > 20:
        print(f"WARN  ...and {len(warnings) - 20} more warnings")
    for e in errors:
        print("ERROR", e)
    print("FAILED" if errors else "OK", f"({len(errors)} errors, {len(warnings)} warnings)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
