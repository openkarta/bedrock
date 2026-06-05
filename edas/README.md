# EDAS GeoServer vector harvest

> **Open Karta Project › BedRock › data source #4.** Repo overview: [`../README.md`](../README.md).

A **curated** harvest of the vector layers published by the **EDAS** GeoServer
(**http://edas.et:8080/geoserver**) — an Ethiopian digital-addressing / city-mapping platform
covering Addis Ababa, Adama, Bishoftu, Dukem and surrounds. Layers include road networks,
building footprints, cadastral parcels, land use / land cover (LULC), city points, landmarks,
road signs, and areas of interest — captured as shapefiles for cleanup and conflation with
OpenStreetMap.

- **Harvested:** 2026-06-05
- **Source platform:** GeoServer (OGC **WFS** at `/geoserver/wfs`)
- **Method:** WFS `GetFeature` with `outputFormat=SHAPE-ZIP` (native CRS preserved, `.prj`
  included). The layer list + per-layer metadata come from WFS `GetCapabilities` (this is a
  plain GeoServer, with no GeoNode catalog). WFS serves only vector data, so all served
  layers are in scope.

## What's here

| Path | Contents |
|------|----------|
| `shapefiles/` | One zipped shapefile per kept layer (`<name>.zip` → `.shp/.shx/.dbf/.prj`) |
| `metadata/` | Per-layer metadata from WFS capabilities (name, title, CRS, WGS84 bbox, keywords) |
| `wfs_capabilities.xml` | Full raw WFS `GetCapabilities` document — the complete 49-layer server inventory (provenance) |
| `manifest.csv` / `manifest.json` | Index of the **23 kept** layers: name, file, WFS feature count, CRS, SHA-256, bytes |
| `excluded_layers.json` | The **26 layers deliberately not downloaded**, each with a reason (duplicate / stub / broken) |
| `verification.csv` | Post-download integrity check (geometry, feature count vs WFS, EPSG) |
| `download_shapefiles.py` | The downloader (re-runnable; encodes the curation in an `EXCLUDE` map) |
| `verify_shapefiles.py` | The verifier (GDAL/ogr-based) |

## Inventory summary

The GeoServer publishes **49 vector layers**. This is a **curated set of 23**
(**1,603,641 features**) — one canonical layer per dataset. All 23 archives open cleanly in
GDAL/ogr and **every layer's feature count exactly matches the server's WFS count** (0 empty,
0 truncated, 0 corrupt).

- **Geometry mix:** 11 polygon · 7 point · 3 line · 2 3D-line.
- **26 layers excluded** (see [`excluded_layers.json`](excluded_layers.json)): **13** byte-identical
  duplicates (web/mobile/version copies), **11** one-feature pgRouting view stubs, and **2**
  layers that are broken server-side (`adama_rd_network_wgs84_v1`, `road_polygon` — WFS
  `GetFeature` returns *"Schema does not exist"*; their backing tables are gone). The full
  49-layer server inventory is preserved in `wfs_capabilities.xml`.

Most valuable layers for OSM work:

| File | Features | Geom | What it is |
|------|---------:|------|-----------|
| `parcel_web_v7.zip` | 741,888 | polygon | Cadastral parcels |
| `parcel_mobile_v777.zip` | 404,950 | polygon | Cadastral parcels (distinct subset) |
| `das_road_network.zip` | 147,717 | line | DAS road / street network (master) |
| `lulc_v7.zip` | 113,105 | polygon | Land use / land cover |
| `road_network.zip` | 65,973 | line | Road network |
| `building_web_v7.zip` | 64,123 | polygon | Building footprints |
| `road_polygon_web_v7.zip` | 13,724 | polygon | Road polygons |
| `landmark_web_v7.zip` | 10,202 | point | Landmarks / POIs (`landmark_Am_web_v7` = Amharic) |
| `adama_lulc_wgs84_v1.zip` | 9,242 | polygon | Adama LULC |
| `road_network111.zip` | 7,171 | line | Road network (distinct subset) |
| `nsl_sub_city_lulc_wgs84_v1.zip` | 4,160 | polygon | Addis sub-city LULC |
| `nh_aoi_web_v7.zip` | 3,780 | polygon | Areas of interest |
| `sign_pole.zip` | 643 | point | Sign poles |
| `road_signs.zip` | 102 | point | Road signs |
| `cities_web_v7.zip` | 71 | point | City points (`_Am` Amharic, `_Or` Oromo variants kept for names) |

`das_road_network` (147,717) and `road_network` (65,973) are **different datasets**, both kept.
The `cities_Am`/`cities_Or` and `landmark_Am` variants are kept for their **Amharic / Oromo
name fields**.

## Coordinate reference systems

22 of 23 layers are **`EPSG:4326`** (WGS84) — OSM-native, no transform needed. The exception:

| Layer | CRS | Note |
|---|---|---|
| `dukem_bishoftu_lulc` | `EPSG:404000` | A **non-standard CRS** (GeoServer's placeholder code for a custom `.prj`). Reproject via the **`.prj` embedded in the zip**, not the `404000` label. |

```bash
# stage a layer in WGS84 (handles the 404000 layer via its embedded .prj)
ogr2ogr -t_srs EPSG:4326 wgs84/dukem_bishoftu_lulc.shp /vsizip/shapefiles/dukem_bishoftu_lulc.zip
```

## Notes / caveats

- **Large files.** Two zips exceed **GitHub's 100 MB/file limit**: `parcel_web_v7.zip`
  (~113 MB) and `lulc_v7.zip` (~101 MB). They are committed directly (this repo has no GitHub
  remote); a future push to GitHub would need **Git LFS** for these.
- **Curation is reproducible.** `download_shapefiles.py` carries the exclusion decisions in its
  `EXCLUDE` map, so a fresh run reproduces exactly these 23 layers and regenerates
  `excluded_layers.json`. To pull an excluded layer, remove it from `EXCLUDE`.
- **Plain HTTP.** The server is `http://edas.et:8080` (no TLS) on a non-standard port; the
  backend reports an internal address of `196.189.124.150:8080`.
- **Licensing & attribution.** Public-sector data from the **EDAS** platform (`edas.et`),
  redistributed as part of the BedRock database under the **Open Database License (ODbL) v1.0**
  ([`../LICENSE`](../LICENSE)) with full provenance preserved. Attribute EDAS on reuse. ODbL is
  OSM's own license, so the data is license-aligned for conflation — still follow the
  [OSM Import Guidelines](https://wiki.openstreetmap.org/wiki/Import/Guidelines).

## Reproducing / refreshing

```bash
python3 download_shapefiles.py   # WFS SHAPE-ZIP for the 23 curated layers (skips valid zips already present)
python3 verify_shapefiles.py     # re-verify integrity → verification.csv
```

The downloader is idempotent (existing valid zips are skipped), records a SHA-256 per file, and
writes `excluded_layers.json` for the layers it deliberately skips. Requirements: Python 3.12+
(stdlib only), `curl`, and GDAL/OGR 3.8+ (`ogrinfo`, `ogr2ogr`).
