import json
import os
import shapely.wkt
from shapely.geometry import mapping, box

PRE_JSON = "./data/raw/joplin-tornado_00000144_pre_disaster.json" # Update tile ID
OUTPUT_GEOJSON = "./data/footprints.geojson"

def extract_footprints():
    with open(PRE_JSON, "r") as f:
        data = json.load(f)

    lng_lat_list = data.get("features", {}).get("lng_lat", [])
    features = []
    all_lons, all_lats = [], []

    for idx, bldg in enumerate(lng_lat_list):
        if bldg.get("properties", {}).get("feature_type") != "building":
            continue
        poly = shapely.wkt.loads(bldg["wkt"])
        bldg_id = f"bldg_{idx+1:03d}"

        minx, miny, maxx, maxy = poly.bounds
        all_lons.extend([minx, maxx])
        all_lats.extend([miny, maxy])

        features.append({
            "type": "Feature",
            "id": bldg_id,
            "geometry": mapping(poly),
            "properties": {"id": bldg_id}
        })

    os.makedirs(os.path.dirname(OUTPUT_GEOJSON), exist_ok=True)
    with open(OUTPUT_GEOJSON, "w") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)

    print(f"[Done] Saved {len(features)} footprints to {OUTPUT_GEOJSON}")
    if all_lons and all_lats:
        print(f"[For Person C Leaflet ImageOverlay Bounds] [[{min(all_lats):.6f}, {min(all_lons):.6f}], [{max(all_lats):.6f}, {max(all_lons):.6f}]]")

if __name__ == "__main__":
    extract_footprints()