# CBE ATM locations

> **Open Karta Project › BedRock › data source #3.** Repo overview: [`../README.md`](../README.md).

Point-of-interest data for **Commercial Bank of Ethiopia (CBE) ATMs**, harvested from the
public **"ATM & Branch Locator"** at
**[combanketh.et/ways-of-banking/atm-branch-locator](https://combanketh.et/ways-of-banking/atm-branch-locator)**.
Each ATM is a named point with WGS84 coordinates, its terminal ID, parent branch, and the
type of venue it sits in — ready to clean and conflate with OpenStreetMap.

- **Harvested:** 2026-06-05
- **Source platform:** Strapi v5 headless CMS (REST API at `/api/`)
- **Method:** `GET https://combanketh.et/api/atm-locations?populate=*` paginated
  (`pageSize=200`, 15 pages), converted to one EPSG:4326 GeoJSON `FeatureCollection`.

## Scope: ATMs only (branches are not geolocated)

The locator is fed by **two separate** Strapi collections:

| Collection | Count | Coordinates? | In BedRock |
|------------|------:|--------------|------------|
| `/api/atm-locations` | 2,884 | **Yes** (`lat`/`lon`) | ✅ this layer |
| `/api/branches` | 1,934 | **No** — only `name, district, region, grade, city, telephone, is_smart_branch` | ❌ excluded |

The `branches` collection carries **no coordinates at all** (confirmed with `populate=*`), so
branches cannot be represented as points from this source and are out of scope here. Only the
geolocated **ATM** layer is captured.

## What's here

| Path | Contents |
|------|----------|
| `atm_locations_raw.json` | **Immutable** raw API records (all 2,884, every page) — provenance |
| `geojson/atm.geojson` | EPSG:4326 GeoJSON `FeatureCollection` of all ATM points |
| `manifest.csv` / `manifest.json` | Inventory: layer, file, feature count, bbox, SHA-256, byte size, source URL, harvest date |
| `verification.csv` | Integrity: geometry, feature count vs raw, CRS, in/out-of-bbox counts, flags |
| `download_locations.py` | The downloader (paginates the API; re-runnable, offline fallback) |
| `verify_locations.py` | Verifier (GDAL/ogr — geometry, counts, CRS, Ethiopia-bbox sanity) |

### Feature schema

Each GeoJSON feature is a `Point` with these properties (mapped from the API fields):

| Property | Source field | Notes |
|----------|--------------|-------|
| `name` | `atmName` | ATM name (often the locality) |
| `terminal_id` | `terminalId` | Unique ATM terminal ID (e.g. `AAD00183`) |
| `branch` | `branch` | Parent branch / district grouping (e.g. `ADAMA`) |
| `district` | `district` | Free-text site label (e.g. `MEKI BRANCH ATM3`) |
| `venue` | `locationTypeDesc` | Venue the ATM sits in (Financial Institution, Hotel, University…) |
| `venue_code` | `locationType` | Numeric venue-type code |
| `city` | `city` | Usually null |
| `telephone` | `telephone` | Usually null |
| `src_id` | `documentId` | Stable Strapi document UUID (for refresh/dedupe) |

### Verification (`verify_locations.py` → `verification.csv`)

The layer opens cleanly in GDAL/ogr: **2,884 features**, 100% `Point`, 100% `EPSG:4326`,
feature count matches the raw source exactly. **2,881 of 2,884** points fall inside Ethiopia's
bounding box; the **3** that don't have **swapped lat/lon at the source** (see caveats).

## Coordinate reference systems

Coordinates are decimal `lat`/`lon` in **`EPSG:4326` (WGS84)** — already OSM-native, **no
reprojection or datum shift needed**. (GeoJSON per RFC 7946 is implicitly WGS84, so no `crs`
member is written.)

## Notes / caveats

These matter for any downstream **normalize/conflation** step:

- **Low coordinate precision.** Values are rounded to ~2 decimal places (~1.1 km). The 2,884
  ATMs occupy only **1,167 distinct coordinates**; **532** coordinate groups are shared by more
  than one ATM, and as many as **38 ATMs** sit on a single identical coordinate. Expect heavy
  stacking — coordinates locate the *area*, not the exact machine.
- **3 ATMs have swapped lat/lon** at the source (longitude in the latitude field), which throws
  them outside Ethiopia: `AAR00154`, `ADM00081`, `ADM00082`. They are kept **as-is** here
  (acquire/verify stays faithful to source); swap them during normalization. Note the manifest
  `bbox` is widened by these bad points.
- **`venue` casing is inconsistent** — 25 distinct `locationTypeDesc` labels include
  case/spelling variants (`Office Building`/`office Building`, `Hotel`/`hotel`/`HOTEL`,
  `University`/`university`/`UNIVERSITY`). Normalize before grouping on it.
- **`city` and `telephone` are almost always null.**
- **Licensing & attribution.** Public-sector data from the Commercial Bank of Ethiopia
  (`combanketh.et`), redistributed as part of the BedRock database under the **Open Database
  License (ODbL) v1.0** ([`../LICENSE`](../LICENSE)) with full provenance preserved. Attribute
  CBE on reuse. ODbL is OSM's own license, so the data is license-aligned for conflation —
  still follow the
  [OSM Import Guidelines](https://wiki.openstreetmap.org/wiki/Import/Guidelines).

## Reproducing / refreshing

```bash
python3 download_locations.py   # paginate the API → atm_locations_raw.json, geojson/atm.geojson, manifest.*
python3 verify_locations.py     # re-verify integrity → verification.csv
```

`download_locations.py` re-fetches all pages each run and falls back to the cached
`atm_locations_raw.json` if the network is unavailable. Requirements: Python 3.12+ (stdlib
only), `curl` (the script uses `-g/--globoff` for Strapi's `pagination[...]` brackets), and
GDAL/OGR 3.8+ (`ogrinfo`) for verification.
