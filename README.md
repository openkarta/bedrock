<div align="center">

# BedRock

### Foundational geospatial data layer of the **Open Karta Project**

*Authoritative source data — acquired, verified, normalized, and prepared for conflation with OpenStreetMap.*

</div>

---

## Table of contents

- [What this is](#what-this-is)
- [Open Karta Project & BedRock](#open-karta-project--bedrock)
- [Why "BedRock"](#why-bedrock)
- [Repository structure](#repository-structure)
- [Data sources](#data-sources)
  - [1. EthioSDI — Ethiopian Spatial Data Infrastructure](#1-ethiosdi--ethiopian-spatial-data-infrastructure)
  - [2. Fayda — National ID registration centers](#2-fayda--national-id-registration-centers)
  - [3. CBE — Commercial Bank of Ethiopia ATMs](#3-cbe--commercial-bank-of-ethiopia-atms)
- [The BedRock pipeline](#the-bedrock-pipeline)
- [Coordinate reference systems](#coordinate-reference-systems)
- [Licensing & attribution](#licensing--attribution)
- [Getting started](#getting-started)
- [Reproducing / refreshing a source](#reproducing--refreshing-a-source)
- [Status & roadmap](#status--roadmap)
- [Conventions](#conventions)

---

## What this is

**BedRock** is the data-acquisition and data-preparation repository of the **Open Karta
Project**. Its job is to collect *authoritative, non-OSM* geospatial datasets from official
and institutional sources (national mapping agencies, spatial data infrastructures, open
government portals), turn them into clean, well-documented, projection-normalized vector
data, and stage them for conflation with OpenStreetMap.

It is deliberately scoped to **vector data** — boundaries, roads, place names, points of
interest, facilities — i.e. data that can be cleaned, attributed, and merged into a map.
Raster products (satellite imagery, DEMs, scanned maps) are intentionally **out of scope**.

Everything here is reproducible: each source ships with the exact scripts used to fetch and
verify it, a machine-readable manifest, full provenance, and per-layer metadata.

## Open Karta Project & BedRock

| | |
|---|---|
| **Open Karta Project** | The root/organizational project — an open mapping effort focused on Ethiopia, building on and contributing back to OpenStreetMap. |
| **BedRock** *(this repo)* | The foundational **data layer**: ingest authoritative source data → clean → normalize → prepare OSM-ready outputs. |

BedRock sits *upstream* of the project's mapping and conflation work. Other Open Karta repos
consume what BedRock produces; BedRock itself does not edit OSM directly — it prepares the
material that informs and feeds those edits.

> ℹ️ The one-line descriptions of *Open Karta Project* above reflect the project's current
> direction (open mapping for Ethiopia, OSM-aligned). Refine this paragraph as the
> organization's mission statement is finalized.

## Why "BedRock"

In geology, *bedrock* is the solid foundation beneath the loose surface material — the layer
everything else rests on. That is exactly this repository's role in Open Karta: it provides
the **trusted base data** that the rest of the project builds the map on top of. Source data
lands here first, gets hardened (verified, normalized, documented), and only then becomes a
dependable foundation for downstream mapping.

## Repository structure

```
bedrock/
├── README.md                  ← you are here (repo overview)
├── ethionsdi/                 ← Data source #1: Ethiopian SDI vector harvest
│   ├── README.md              ← source-specific documentation
│   ├── shapefiles/            ← 69 zipped shapefiles (.shp/.shx/.dbf/.prj), 26 MB
│   ├── metadata/              ← per-layer GeoNode metadata (JSON)
│   ├── manifest.json / .csv   ← index: layer, file, feature count, CRS, SHA-256, status
│   ├── verification.csv       ← post-download integrity check (geometry, counts, EPSG)
│   ├── metadata_full_catalog.json   ← full source catalog dump (vector + raster)
│   ├── restricted_layers.json       ← layers that need authentication (see source README)
│   ├── wfs_downloadable_layers.txt  ← authoritative list of publicly served layers
│   ├── download_shapefiles.py ← fetch script (re-runnable, resumable)
│   └── verify_shapefiles.py   ← verification script (ogr-based)
├── fayda/                     ← Data source #2: Fayda National ID registration centers
│   ├── README.md              ← source-specific documentation
│   ├── geojson/               ← one EPSG:4326 GeoJSON per location_type (2,251 POIs)
│   ├── locations_raw.json     ← immutable raw API response (provenance)
│   ├── manifest.json / .csv   ← index: type, file, feature count, bbox, SHA-256
│   ├── verification.csv       ← integrity check (geometry, counts, CRS, in-bbox)
│   ├── download_locations.py  ← fetch script (re-runnable)
│   └── verify_locations.py    ← verification script (ogr-based)
└── cbebank/                   ← Data source #3: Commercial Bank of Ethiopia ATMs
    ├── README.md              ← source-specific documentation
    ├── geojson/atm.geojson    ← EPSG:4326 GeoJSON of ATM points (2,884)
    ├── atm_locations_raw.json ← immutable raw API records (provenance)
    ├── manifest.json / .csv   ← index: layer, file, feature count, bbox, SHA-256
    ├── verification.csv       ← integrity check (geometry, counts, CRS, in-bbox)
    ├── download_locations.py  ← fetch script (paginated, re-runnable)
    └── verify_locations.py    ← verification script (ogr-based)
```

Each **data source gets its own top-level subdirectory** with the same internal layout
(a vector-data folder, `manifest.*`, fetch + verify scripts, a source `README.md`). The exact
output format follows the source — zipped `shapefiles/` for EthioSDI, `geojson/` for Fayda.
Add new sources as sibling folders.

## Data sources

### 1. EthioSDI — Ethiopian Spatial Data Infrastructure

> **Source:** https://ethionsdi.gov.et (GeoNode + GeoServer) · **Harvested:** 2026-06-05 ·
> **Full docs:** [`ethionsdi/README.md`](ethionsdi/README.md)

The national SDI portal. We catalogued all **129 datasets** (85 vector + 44 raster, plus 15
image documents), excluded everything raster, and exported every **publicly available vector
layer** as a verified shapefile.

| Metric | Value |
|---|---|
| Vector layers downloaded | **69** |
| Total features | **216,263** |
| Geometry mix | 61 point · 5 polygon · 2 line · 1 multipoint |
| Integrity | 100% — every layer's feature count matches the server's WFS count; 0 empty/corrupt |
| Excluded (raster/imagery) | 44 |
| Access-restricted (need login) | 20 — listed in [`ethionsdi/restricted_layers.json`](ethionsdi/restricted_layers.json) |

**Highlights** (most useful for OSM conflation): a 67,689-feature road/street network, a
23,105-entry 1:50k **gazetteer** (place names), 42,741 rural + 21,064 urban **schools**,
woreda (district) **boundary polygons**, plus health facilities, markets, and POI layers.

**Method:** GeoServer OGC **WFS `GetFeature` → `outputFormat=SHAPE-ZIP`**, which yields a
clean shapefile bundle (with `.prj`) in the layer's native CRS, with no row caps. See the
source README for the GeoNode-specific gotchas (self-signed cert, API page-size limit, one
serializer-crashing record, and the 20 WFS-hidden layers).

> ⚠️ **Open item:** 20 vector layers — including some of the most OSM-relevant data (ERA
> roads, land use, hospitals, bus stops, contours, the Addis Ababa street network, market
> centres) — are gated behind an EthioSDI login and could not be fetched anonymously.
> Obtaining them requires credentials; see the source README.

### 2. Fayda — National ID registration centers

> **Source:** https://id.gov.et/locations ("Fayda Near Me" locator) · **Harvested:** 2026-06-05 ·
> **Full docs:** [`fayda/README.md`](fayda/README.md)

Every **Fayda Digital ID (National ID) registration/enrolment center** in Ethiopia, harvested
from the locator's JSON API (`GET /api/proxy/get/locations`) and split into one **EPSG:4326
GeoJSON** per `location_type`.

| Metric | Value |
|---|---|
| POIs downloaded | **2,251** |
| Geometry | 100% point · all `EPSG:4326` (no datum shift) |
| Types | tele 1,860 · mor 134 · crrsa 107 · post office 91 · bank 44 · dars 14 · palace parking 1 |
| Integrity | 100% — every layer's count matches the raw source; all points inside Ethiopia's bbox; 0 flagged |
| Attributes | name, type, status, `gmaps_url`, source id, created/updated |

**Highlights** (most useful for OSM conflation): a large set of named **Ethio telecom**
centers, plus **post offices**, **bank branches**, **tax (MoR) offices**, and civil-registration
(**CRRSA/DARS**) sites — each a named point with WGS84 coordinates.

**Method:** a single anonymous **JSON API** call (no auth, no pagination), converted to
per-type GeoJSON `FeatureCollection`s. The source `address` field is a **Google Maps link**,
not a postal address (kept as `gmaps_url`); the authoritative location is the point geometry.

> 🛑 **Open item:** this is National ID Program data with **no stated open license** — license
> compatibility must be cleared (or permission obtained) before any OSM import. See the source README.

### 3. CBE — Commercial Bank of Ethiopia ATMs

> **Source:** https://combanketh.et/ways-of-banking/atm-branch-locator (Strapi CMS) · **Harvested:** 2026-06-05 ·
> **Full docs:** [`cbebank/README.md`](cbebank/README.md)

The bank's **ATM & Branch Locator**, backed by a Strapi REST API. The locator exposes two
separate collections — **ATMs** (`/api/atm-locations`, geolocated) and **branches**
(`/api/branches`, **no coordinates**). Only the geolocated ATM layer is captured as points.

| Metric | Value |
|---|---|
| ATM points downloaded | **2,884** |
| Geometry | 100% point · all `EPSG:4326` (no datum shift) |
| Integrity | count matches the raw source; 2,881/2,884 inside Ethiopia's bbox (3 source lat/lon swaps) |
| Branches | 1,934 — **excluded**: the source provides no branch coordinates |
| Attributes | name, terminal id, branch, district, venue type, city, telephone |

**Highlights** (most useful for OSM conflation): a national set of **CBE ATMs**, each with a
unique **terminal ID** and parent **branch**. ⚠️ Coordinates are low-precision (rounded to
~1 km; many ATMs share an identical point), so they locate the *area*, not the exact machine.

**Method:** paginated **JSON API** (`pageSize=200`, 15 pages; `curl --globoff` for the Strapi
`pagination[...]` params), converted to one EPSG:4326 GeoJSON. Acquire/verify keep the data
faithful to source — the 3 swapped-coordinate ATMs are flagged, not silently fixed.

> 🛑 **Open item:** CBE data with **no stated open license** — clear license/permission before
> any OSM import. The companion branch list (no geometry) is not included; see the source README.

## The BedRock pipeline

Every source moves through the same four stages:

```
   ┌──────────┐     ┌──────────┐     ┌────────────┐     ┌──────────────┐
   │ ACQUIRE  │ ──▶ │  VERIFY  │ ──▶ │ NORMALIZE  │ ──▶ │  OSM-READY   │
   └──────────┘     └──────────┘     └────────────┘     └──────────────┘
   fetch from        validate every    reproject to       conflation /
   the authority,    archive opens,    EPSG:4326,         tagging mapping,
   record provenance feature counts    fix datums,        dedupe vs OSM
   + checksums       match the source  clean attributes   (downstream repos)
```

1. **Acquire** — pull from the official endpoint with a re-runnable script; capture full
   metadata, a manifest, and SHA-256 checksums. Never hand-edit source files.
2. **Verify** — open every archive with GDAL/ogr; confirm geometry, feature counts (against
   the source's own count), and CRS. Fail loudly on empty/corrupt/truncated layers.
3. **Normalize** — reproject to WGS84 (`EPSG:4326`), applying proper datum shifts; clean and
   standardize attribute schemas. *(Per-source; run during cleanup for conflation.)*
4. **OSM-ready** — hand off normalized data to the project's conflation/tagging workflow.
   *(Downstream of this repo.)*

Stages 1–2 are complete and scripted for EthioSDI; stages 3–4 are performed per dataset as
it's prepared for merge.

## Coordinate reference systems

Source layers are preserved in their **native CRS** (with `.prj`) so nothing is lost. The
EthioSDI set spans four CRSs:

| EPSG | Name | Note |
|---|---|---|
| `4326` | WGS84 geographic | Most layers; OSM-native |
| `4201` | **Adindan** geographic | Old Ethiopian datum — needs a **datum shift** to WGS84 (≈100–200 m otherwise) |
| `3857` | Web Mercator | The WFS-only layers |
| `32637` | Adindan / WGS UTM 37N | Woreda boundaries |

To stage everything in WGS84 for OSM:

```bash
mkdir -p wgs84
for z in ethionsdi/shapefiles/*.zip; do
  n=$(basename "$z" .zip)
  ogr2ogr -t_srs EPSG:4326 "wgs84/$n.shp" "/vsizip/$z"
done
```

> ⚠️ Use `ogr2ogr -t_srs EPSG:4326` for the Adindan (`4201` / `32637`) layers — it applies
> the datum transformation. **Do not** just relabel the `.prj`, or the data will be offset.

## Licensing & attribution

BedRock data is **third-party source data**, not original work. Each dataset remains the
property of its publisher (for EthioSDI: the Ethiopian Geospatial Information Institute /
EthioSDI). Per-layer license and use constraints are recorded in each source's
`metadata/` JSON and `metadata_full_catalog.json`.

> 🛑 **Before importing anything into OpenStreetMap**, confirm the dataset's license is
> OSM-compatible (or obtain explicit permission), and follow the
> [OSM Import Guidelines](https://wiki.openstreetmap.org/wiki/Import/Guidelines). License
> compatibility has **not** been cleared here — it is a required gate before any upload.

The **scripts** in this repository may be used freely within the Open Karta Project.

## Getting started

**Requirements** (validated with the versions below):

- Python **3.12+** (standard library only — no third-party packages needed)
- **GDAL/OGR 3.8+** — `ogrinfo`, `ogr2ogr` (`sudo apt install gdal-bin`)
- `curl`, `unzip`

Inspect the harvested data without any extraction (GDAL reads inside the zip):

```bash
# list layers + feature counts for one archive
ogrinfo -so -al /vsizip/ethionsdi/shapefiles/58_road_2.zip

# browse the inventory
column -s, -t < ethionsdi/manifest.csv | less -S
```

## Reproducing / refreshing a source

Each source is fully reproducible from its own folder:

```bash
cd ethionsdi
python3 download_shapefiles.py   # re-fetch (skips files already present)
python3 verify_shapefiles.py     # re-verify integrity → verification.csv
```

The download script is idempotent (existing valid zips are skipped) and records a SHA-256 per
file, so refreshes and diffs are straightforward.

## Status & roadmap

- [x] **EthioSDI** — 69/85 public vector layers acquired & verified
- [x] **Fayda** — 2,251 National ID registration-center POIs acquired & verified (EPSG:4326)
- [x] **CBE** — 2,884 ATM POIs acquired & verified (EPSG:4326)
- [ ] **CBE branches** — 1,934 branches have no coordinates in the source; geocode or source them separately
- [ ] **EthioSDI restricted layers** — 20 layers behind authentication (roads, land use,
      health, contours, AA street network, …) — *blocked on credentials*
- [ ] **Clear Fayda / CBE / EthioSDI licensing** for OSM import (no open license stated)
- [ ] **Normalize EthioSDI to WGS84** and clean attribute schemas for conflation
- [ ] **OSM conflation** — dedupe/merge against existing OSM data *(downstream)*
- [ ] **Additional sources** — add further authoritative datasets as sibling folders

## Conventions

- **One folder per source**, named after the authority (`ethionsdi/`), with the standard
  internal layout (`shapefiles/`, `metadata/`, `manifest.*`, `*.py`, `README.md`).
- **Source files are immutable** — never hand-edit a downloaded shapefile; derive cleaned
  outputs into separate folders so provenance stays intact.
- **Everything is scripted and checksummed** — if it can't be reproduced from a script, it
  doesn't belong in BedRock.
- **Provenance travels with the data** — keep the manifest, metadata, and source URL together.

---

<div align="center">
<sub><b>BedRock</b> · part of the <b>Open Karta Project</b> · open mapping for Ethiopia</sub>
</div>
