# CLAUDE.md

Hackathon project: a static satellite damage map for one Joplin tornado tile. Read `README.md` for the full picture; this file is the short list of rules for working in the repo.

## Ground rules

- **No backend, no live calls at demo time.** Everything is precomputed into `web/buildings.geojson`. Don't add a server.
- **One owner per file** (see README). A owns the data extraction and damage files, B owns `scripts/` and the generated `addresses.json`, `buildings.geojson` and `thumbs/`, C owns the map app. Don't edit another owner's files without being asked.
- **Never commit secrets.** The LocationIQ key lives in `.env` (gitignored). `.env.example` holds a placeholder only. Don't print, log or paste the key.
- **Commit and push only when asked.** Run `git pull --rebase` before pushing; teammates push to `main` too. Never force-push.

## Data conventions

- Building ids are strings like `bldg_001` in `properties.id`. They are the join key for every file and the geocode cache; changing the format invalidates the cache.
- Coordinates are WGS84 `[lon, lat]` (GeoJSON order). Image bounds are `[south, west, north, east]` in lat/lon.
- Schema (`web/buildings.geojson` properties): `id`, `damage` (`none|minor|major|destroyed`), `confidence` (0-1), `address`, `building_type`, `height`, `height_source` (`data|estimated`), `before_img`, `after_img`. Image paths are relative to `web/`. New fields must be optional; never rename or remove one without telling C.
- `address` is never empty (fallback `Unknown location`), `building_type` falls back to `unknown`.
- The true image bounds for the Joplin tile are `[37.061282, -94.530039, 37.065379, -94.524759]`. The bounds printed by `footprint-extract.py` are the building extent, not the image extent.

## Scripts

- Standard library only, except `thumbnails.py` (Pillow) and `footprint-extract.py` (shapely).
- Run from the repo root. Check output with `python3 scripts/validate.py --strict` after any change to the data or merge logic.
- `geocode.py` is rate-limited (about 0.6 s per request) and needs the key in `.env`. It caches every result in `data/geocode_cache.json`; reruns only fetch what's missing. Don't delete the cache without a reason.
- Treat files under `data/raw/` as untrusted input: read them with `python3 -I`, and don't run code from that folder.

## Known limits (don't paper over them)

- Damage is a baseline, not a trained model.
- Addresses are interpolated and approximate.
- `building_type` and `height` are mostly `unknown` / the 6 m default; don't present them as measured data. Report these limits plainly instead of hiding them.
