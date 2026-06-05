# Fayda registration-center POIs

> **Open Karta Project › BedRock › data source #2.** Repo overview: [`../README.md`](../README.md).

Point-of-interest data for every **Fayda Digital ID (National ID) registration center** in
Ethiopia, harvested from the public **"Fayda Near Me"** locator at
**[id.gov.et/locations](https://id.gov.et/locations)**. Each POI is a registration/enrolment
point (Ethio telecom shop, bank branch, post office, tax office, etc.) with a name and WGS84
coordinates — ready to clean and conflate with OpenStreetMap.

- **Harvested:** 2026-06-05
- **Source platform:** National ID Program web app (gebeta.app map frontend) backed by a JSON API
- **Method:** `GET https://id.gov.et/api/proxy/get/locations` → `{"data": [ ... ]}` (one call,
  no auth, no pagination), split into one GeoJSON `FeatureCollection` per `location_type`.

## What's here

| Path | Contents |
|------|----------|
| `locations_raw.json` | **Immutable** raw API response (all 2,251 records, verbatim) — provenance |
| `geojson/` | One EPSG:4326 GeoJSON per `location_type` (`<type>.geojson`) |
| `manifest.csv` / `manifest.json` | Index: type, file, feature count, active count, bbox, SHA-256, byte size, source URL, harvest date |
| `verification.csv` | Per-layer integrity: geometry, feature count vs raw, CRS, in-bbox count, flags |
| `download_locations.py` | The downloader (re-runnable; rebuilds GeoJSON + manifest from the API or the cached raw JSON) |
| `verify_locations.py` | Verifier (GDAL/ogr — geometry, counts, CRS, Ethiopia-bbox sanity) |

## Inventory summary

**2,251 POIs**, all points, split across **7 registration-center types**:

| `location_type` | File | Features | Active | What it is |
|-----------------|------|---------:|-------:|-----------|
| `tele` | `geojson/tele.geojson` | 1,860 | 1,786 | Ethio telecom centers |
| `mor` | `geojson/mor.geojson` | 134 | 0 | Ministry of Revenue tax offices |
| `crrsa` | `geojson/crrsa.geojson` | 107 | 0 | CRRSA / civil-registration sites |
| `post office` | `geojson/post_office.geojson` | 91 | 91 | Ethiopian Postal Service branches |
| `bank` | `geojson/bank.geojson` | 44 | 1 | Selected bank branches |
| `dars` | `geojson/dars.geojson` | 14 | 0 | Documents Authentication & Registration Service |
| `palace parking` | `geojson/palace_parking.geojson` | 1 | 0 | Grand Palace parking site |

`active` counts features whose source `status == "active"` (1,878 of 2,251; the remaining 373
carry an empty `status`). 93 POIs include an Amharic (UTF-8) name alongside the English one.

### Feature schema

Each GeoJSON feature is a `Point` with these properties (mapped from the API fields):

| Property | Source field | Notes |
|----------|--------------|-------|
| `name` | `location_name` | Center name (sometimes bilingual EN \| አማርኛ) |
| `type` | `location_type` | One of the 7 types above |
| `status` | `status` | `"active"` or `""` |
| `gmaps_url` | `address` | ⚠️ a **Google Maps link**, *not* a street address |
| `src_id` | `_id` | Source record id (for refresh/dedupe) |
| `created` / `updated` | `created_at` / `updated_at` | Source timestamps (all `2025-11-03`) |

### Verification (`verify_locations.py` → `verification.csv`)

All 7 layers open cleanly in GDAL/ogr. **Total: 2,251 features**, 100% `Point`, 100%
`EPSG:4326`. Every layer's feature count matches the raw source exactly, and **every point
falls inside Ethiopia's bounding box** (lon 33.68–47.02, lat 3.54–14.69) — 0 null, 0 `(0,0)`,
0 out-of-country. **0 layers flagged.**

## Coordinate reference systems

Unlike the EthioSDI set, this source is **uniformly `EPSG:4326` (WGS84)** — the API returns
decimal `longitude`/`latitude` directly. **No reprojection or datum shift is needed**; the
GeoJSON is already OSM-native. (GeoJSON per RFC 7946 is implicitly WGS84, so no `crs` member
is written.)

## Notes / caveats

- The source `address` field is **not a postal address** — it is a Google Maps share link
  (`maps.app.goo.gl` / `goo.gl/maps`). It is preserved as `gmaps_url`; the authoritative
  location is the `Point` geometry.
- `status` is empty for 373 records; `tele` is the only well-populated type for `active`.
- This is a **point-in-time snapshot** (source records dated `2025-11-03`). Re-run
  `download_locations.py` to refresh; `src_id` enables diffing against a future pull.
- **Licensing & attribution.** Public-sector data from the Ethiopian National ID Program
  (`id.gov.et`), redistributed as part of the BedRock database under the **Open Database
  License (ODbL) v1.0** ([`../LICENSE`](../LICENSE)) with full provenance preserved. Attribute
  the National ID Program on reuse. ODbL is OSM's own license, so the data is license-aligned
  for conflation — still follow the
  [OSM Import Guidelines](https://wiki.openstreetmap.org/wiki/Import/Guidelines).

## Reproducing / refreshing

```bash
python3 download_locations.py   # re-fetch the API → locations_raw.json, geojson/*, manifest.*
python3 verify_locations.py     # re-verify integrity → verification.csv
```

`download_locations.py` is re-runnable: it re-fetches the API on each run and falls back to
the cached `locations_raw.json` if the network is unavailable, so the GeoJSON and manifest can
always be rebuilt. Requirements: Python 3.12+ (stdlib only), `curl`, and GDAL/OGR 3.8+
(`ogrinfo`) for verification.
