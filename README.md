# Aperium: Satellite Damage Map

A hackathon demo that shows first responders which buildings were damaged by a disaster, and where. It compares before and after satellite imagery for one small area, colors each building by damage level, and shows an approximate street address with before/after thumbnails when you click it.

**Demo area:** Joplin, Missouri, after the May 2011 tornado. One xBD tile (`joplin-tornado_00000144`, 1024 x 1024 px, about 470 m across) with 276 building footprints.

Everything is precomputed. There is no backend, no live inference and no live geocoding during the demo: the frontend loads `web/buildings.geojson` as a static file.

## Team and ownership

| Person | Role | Owns |
|---|---|---|
| A | Data and ML | `footprint-extract.py`, `data/footprints.geojson`, `data/raw/`, damage scoring (`data/damage.json`) |
| B | Geocoding and merge | `scripts/`, `data/addresses.json`, `web/buildings.geojson`, `web/thumbs/` |
| C | Frontend and pitch | the map app in `web/` (everything except B's generated files) |

One owner per file. Don't edit someone else's files; ask them.

## Data flow

```
A: footprints.geojson, damage.json, imagery.json, raw imagery
        |
B: geocode.py -> addresses.json
   thumbnails.py -> web/thumbs/
   merge.py -> web/buildings.geojson
        |
C: map app loads web/buildings.geojson
```

## The schema

`web/buildings.geojson` is a GeoJSON FeatureCollection. Each feature has a Polygon geometry in WGS84 (`[lon, lat]`) and these properties:

| Property | Type | Notes |
|---|---|---|
| `id` | string | Unique, e.g. `bldg_001`. The key that joins every file. |
| `damage` | string | `none`, `minor`, `major` or `destroyed` |
| `confidence` | number | 0 to 1 |
| `address` | string | Approximate. Never empty; may be `Unknown location` or `near <street>`. |
| `building_type` | string | e.g. `house`, `building`, or `unknown` (see Limits) |
| `height` | number | Metres. Mostly the 6 m default (see Limits). |
| `height_source` | string | `data` (real value) or `estimated` |
| `before_img` | string | Path relative to `web/`, e.g. `thumbs/bldg_001_before.jpg` |
| `after_img` | string | Same, for the after image |

## Setup

Python 3 is required. The scripts use only the standard library, except:

- `thumbnails.py` needs Pillow: `pip install pillow`
- `footprint-extract.py` (A's script) needs shapely: `pip install shapely`

Geocoding uses [LocationIQ](https://locationiq.com) (free key):

```
cp .env.example .env     # then paste your key into .env
```

`.env` is gitignored. Never commit a key.

## Running the pipeline

```
python3 scripts/geocode.py data/footprints.geojson                      # ~3 min, cached per id
python3 scripts/thumbnails.py data/footprints.geojson data/imagery.json # needs imagery.json from A
python3 scripts/merge.py data/footprints.geojson data/damage.json data/addresses.json
python3 scripts/validate.py --strict
```

| Script | What it does |
|---|---|
| `scripts/geocode.py` | Reverse-geocodes each footprint centroid. Caches to `data/geocode_cache.json`, so reruns only fetch what's missing. Writes `data/addresses.json`. |
| `scripts/thumbnails.py` | Crops a before and after thumbnail per building from the pre/post images. Grey placeholder if a crop fails. |
| `scripts/merge.py` | Joins footprints, damage and addresses into `web/buildings.geojson`, with safe defaults for anything missing. |
| `scripts/validate.py` | Checks the schema, ids, damage classes, confidence, height and image paths. `--strict` makes missing images errors. |
| `scripts/osm_types.py` | Experimental: looks up building type from OpenStreetMap polygons. Coverage is low (see Limits) and it is not wired into the merge. |

`data/imagery.json` is written by `footprint-extract.py`. Each of `before` and `after` has the image `file` plus its georeferencing:

```json
{
  "before": {
    "file": "raw/joplin-tornado_00000144_pre_disaster.png",
    "bounds": [south, west, north, east],
    "corners": [[lon, lat], [lon, lat], [lon, lat], [lon, lat]],
    "transform": {"lon": [ax, ay, a0], "lat": [bx, by, b0]}
  },
  "after": { "...": "same keys for the post-disaster image" }
}
```

The satellite tile is slightly rotated relative to north (about 7 m across the 1024 px), so it is **not** a simple north-up rectangle:

- `transform` is exact: `lon = ax*x + ay*y + a0`, `lat = bx*x + by*y + b0`, with x/y in pixels. It is fitted from the pixel (`features.xy`) and lon/lat (`features.lng_lat`) coordinates in the raw xBD file and maps every building to within 0.02 px. `thumbnails.py` uses it.
- `corners` are the four image corners (top-left, top-right, bottom-right, bottom-left). The map's image overlay uses these.
- `bounds` is only the axis-aligned envelope of the corners. Using it alone (for example two corners of it) misplaces buildings by about 8 px (3.7 m) on average and up to 16 px (7 m).

The GeoTIFFs A added (`data/pre_disaster.tif`, `data/post_disaster.tif`) carry the same transform.

## Status

- Done: footprints (276), addresses (276), merge, validate and thumbnail scripts.
- Waiting on A: `data/damage.json` (ids must be `bldg_###`) and `data/imagery.json`.
- Not yet done: real thumbnails in `web/thumbs/`, the real merged `web/buildings.geojson` (the committed one is dummy data), and the map app.

## Limits (be honest in the pitch)

- **Damage** is a baseline, not a trained model. The xBD post-disaster files also contain ground-truth labels (172 destroyed, 69 major, 33 minor, 2 unclassified), which can be used to check the baseline.
- **Addresses are approximate.** LocationIQ returned house numbers by interpolating along the street, not by matching a building. Only 141 distinct addresses cover the 276 buildings, so neighbours often share one. A human must verify before anyone acts on it.
- **Building type and height are mostly unknown.** The geocoder returned no building class, and OpenStreetMap matched only 55 of 276 footprints (16 with a specific type, none with a height). Most buildings show `unknown` and the 6 m default height, so a 3D view would look flat.
- Thumbnails are small and blurry (a building is only a few dozen pixels in the source image).
- The footprints come from the 2011 imagery; current OpenStreetMap reflects the rebuilt city.
