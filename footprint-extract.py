import json
import os
import numpy as np
import shapely.wkt
from shapely.geometry import mapping, box

PRE_JSON = "./data/raw/joplin-tornado_00000144_pre_disaster.json" # Update tile ID
OUTPUT_GEOJSON = "./data/footprints.geojson"
OUTPUT_IMAGERY = "./data/imagery.json"

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
        print(f"[Building extent, NOT the image extent] [[{min(all_lats):.6f}, {min(all_lons):.6f}], [{max(all_lats):.6f}, {max(all_lons):.6f}]]")

    write_imagery_json(data)


def image_bounds(data):
    """Return the image's [south, west, north, east] in lat/lon.

    The raw file lists every building in pixel coordinates (features.xy) and in
    lon/lat (features.lng_lat), in the same order. Fit a straight-line (affine)
    pixel -> lon/lat transform to those pairs, then apply it to the image corners.
    """
    xy_list = data["features"]["xy"]
    ll_list = data["features"]["lng_lat"]
    px, ll = [], []
    for a, b in zip(xy_list, ll_list):
        pa = shapely.wkt.loads(a["wkt"]).exterior.coords
        pb = shapely.wkt.loads(b["wkt"]).exterior.coords
        px.extend(pa)
        ll.extend(pb)
    px, ll = np.array(px), np.array(ll)
    design = np.c_[px, np.ones(len(px))]
    lon_fit, *_ = np.linalg.lstsq(design, ll[:, 0], rcond=None)
    lat_fit, *_ = np.linalg.lstsq(design, ll[:, 1], rcond=None)

    def to_lonlat(x, y):
        return lon_fit @ [x, y, 1], lat_fit @ [x, y, 1]

    meta = data["metadata"]
    west, north = to_lonlat(0, 0)
    east, south = to_lonlat(meta["width"], meta["height"])
    return [float(south), float(west), float(north), float(east)]


def write_imagery_json(data):
    bounds = image_bounds(data)
    pre_png = os.path.basename(PRE_JSON).replace(".json", ".png")
    post_png = pre_png.replace("pre_disaster", "post_disaster")
    imagery = {
        "before": {"file": f"raw/{pre_png}", "bounds": bounds},
        "after": {"file": f"raw/{post_png}", "bounds": bounds},
    }
    with open(OUTPUT_IMAGERY, "w") as f:
        json.dump(imagery, f, indent=2)
    print(f"[Done] Saved {OUTPUT_IMAGERY}")
    print(f"[For Person C Leaflet ImageOverlay Bounds] [[{bounds[0]:.6f}, {bounds[1]:.6f}], [{bounds[2]:.6f}, {bounds[3]:.6f}]]")


if __name__ == "__main__":
    extract_footprints()