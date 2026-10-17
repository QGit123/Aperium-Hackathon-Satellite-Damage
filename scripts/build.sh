#!/usr/bin/env bash
# Build the map data and (optionally) serve the map.
#
# Usage (from anywhere):
#   scripts/build.sh                 build using data/damage.json (from A), then serve
#   scripts/build.sh --xbd-labels    no damage.json yet: use the xBD ground-truth labels (interim)
#   scripts/build.sh --geocode       re-run geocoding (needs LOCATIONIQ_KEY in .env, ~3 min)
#   scripts/build.sh --no-serve      build only
#   PORT=9000 scripts/build.sh       serve on another port
#
# Steps: footprints + imagery.json -> addresses (reused if present) -> thumbnails
#        -> merge -> validate -> serve maplibre/ on http://localhost:$PORT
# Output goes to maplibre/ (buildings.geojson and thumbs/), where the map reads it.
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${PORT:-8000}"
XBD_LABELS=0; GEOCODE=0; SERVE=1
for arg in "$@"; do
  case "$arg" in
    --xbd-labels) XBD_LABELS=1 ;;
    --geocode)    GEOCODE=1 ;;
    --no-serve)   SERVE=0 ;;
    -h|--help)    sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 1 ;;
  esac
done

step() { printf '\n==> %s\n' "$1"; }

step "Python environment (.venv)"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q --disable-pip-version-check shapely numpy pillow
PY="$PWD/.venv/bin/python"

step "Footprints and imagery.json (footprint-extract.py)"
"$PY" footprint-extract.py

step "Addresses"
if [ "$GEOCODE" = 1 ] || [ ! -f data/addresses.json ]; then
  "$PY" scripts/geocode.py data/footprints.geojson
else
  echo "Using existing data/addresses.json (pass --geocode to refetch)"
fi

step "Damage"
DAMAGE=data/damage.json
if [ "$XBD_LABELS" = 1 ]; then
  DAMAGE=data/damage_xbd_labels.json
  "$PY" -I - "$DAMAGE" <<'EOF'
import json, sys
post = json.load(open("data/raw/joplin-tornado_00000144_post_disaster.json"))["features"]["lng_lat"]
classes = {"destroyed": "destroyed", "major-damage": "major", "minor-damage": "minor",
           "no-damage": "none", "un-classified": "none"}
damage = {f"bldg_{i + 1:03d}": {"damage": classes[b["properties"].get("subtype", "no-damage")],
                                "confidence": 1.0} for i, b in enumerate(post)}
json.dump(damage, open(sys.argv[1], "w"))
print(f"Wrote {sys.argv[1]}: xBD ground-truth labels (interim, NOT a model prediction)")
EOF
elif [ ! -f "$DAMAGE" ]; then
  echo "ERROR: $DAMAGE not found. Wait for A's damage.json, or run with --xbd-labels." >&2
  exit 1
else
  echo "Using $DAMAGE"
fi

step "Thumbnails (maplibre/thumbs)"
"$PY" scripts/thumbnails.py data/footprints.geojson data/imagery.json maplibre/thumbs

step "Satellite imagery for the map (maplibre/imagery)"
mkdir -p maplibre/imagery
cp data/imagery.json maplibre/imagery/imagery.json
"$PY" -I - <<'EOF'
import json, shutil
imagery = json.load(open("data/imagery.json"))
for name in ("before", "after"):
    shutil.copy("data/" + imagery[name]["file"], "maplibre/imagery/")
print("Copied imagery.json and the before/after images")
EOF

step "Merge and validate"
"$PY" scripts/merge.py data/footprints.geojson "$DAMAGE" data/addresses.json maplibre/buildings.geojson
"$PY" scripts/validate.py --strict maplibre/buildings.geojson

if [ "$SERVE" = 1 ]; then
  step "Serving the map at http://localhost:$PORT (Ctrl+C to stop)"
  if command -v open >/dev/null 2>&1; then (sleep 1; open "http://localhost:$PORT") & fi
  cd maplibre && exec "$PY" -m http.server "$PORT"
fi
echo; echo "Done. Serve with: cd maplibre && python3 -m http.server $PORT"
