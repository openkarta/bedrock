# EthioSDI vector data harvest

> **Open Karta Project › BedRock › data source #1.** Repo overview: [`../README.md`](../README.md).

Vector layers scraped from the Ethiopian Spatial Data Infrastructure portal
(**https://ethionsdi.gov.et**, a GeoNode instance), for cleanup and merging with
OpenStreetMap data. **Raster / satellite / imagery / elevation layers were
deliberately excluded** per request — only vector data that can become shapefiles
was collected.

- **Harvested:** 2026-06-05
- **Source platform:** GeoNode + GeoServer (Django REST API at `/api/v2/`, OGC WFS at `/geoserver/wfs`)
- **Method:** GeoServer WFS `GetFeature` with `outputFormat=SHAPE-ZIP` (native CRS preserved, `.prj` included)

## What's here

| Path | Contents |
|------|----------|
| `shapefiles/` | One zipped shapefile per layer (`<pk>_<name>.zip` → `.shp/.shx/.dbf/.prj`) |
| `metadata/` | Per-layer GeoNode metadata JSON (title, abstract, category, keywords, bbox, CRS, dates) |
| `manifest.csv` / `manifest.json` | Index: layer, file, feature count, CRS, SHA-256, byte size, status, abstract |
| `metadata_full_catalog.json` | Full GeoNode catalog dump (all 129 datasets, vector + raster) for reference |
| `restricted_layers.json` | The 20 vector layers that require a login to download (see below) |
| `wfs_downloadable_layers.txt` | Authoritative list of WFS-exposed layer names |
| `download_shapefiles.py` | The downloader (re-runnable; skips already-downloaded files) |

## Inventory summary

The portal holds **129 datasets** (85 vector + 44 raster) plus 15 documents (all images,
no spatial data).

- **Raster (44):** excluded — DEMs, slope/landslide rasters, aerial/satellite imagery.
- **Vector (85):**
  - **69 downloaded & verified** here as shapefiles (publicly served via WFS).
  - **20 access-restricted** — present in the catalog and viewable as map images (WMS),
    but GeoServer hides them from WFS for anonymous users and the file-download API
    returns HTTP 403. These need an authenticated EthioSDI account to export. They are
    listed in `restricted_layers.json` and include some of the most OSM-relevant layers
    (land use, ERA roads, health facilities, hospitals, bus stops, contours, Addis Ababa
    street network, market centres). See "Restricted layers" below for how to obtain them.

### Verification (`verify_shapefiles.py` → `verification.csv`)

All 69 archives open cleanly in GDAL/ogr. **Total: 216,263 features** — 61 point layers,
5 polygon, 2 line, 1 multipoint. **Every layer's feature count exactly matches the server's
WFS count**, so no features were truncated.

Most valuable layers for OSM work:

| File | Features | Geom | What it is |
|------|---------:|------|-----------|
| `58_road_2.zip` | 67,689 | line | Dense road / street network |
| `x_rural_schools.zip` | 42,741 | point | Rural schools |
| `x_gazetteer_50k_data.zip` | 23,105 | point | 1:50k gazetteer — place names |
| `x_urban_schools.zip` | 21,064 | point | Urban schools |
| `109_all_place_markes_final.zip` | 15,715 | point | Place markers |
| `x_cultural_features.zip` | 8,992 | point | Cultural / POI features |
| `41_store_and_place_marks.zip` | 9,289 | point | Stores + place marks |
| `87_foodstore_safetenet.zip` | 7,168 | point | Food stores (safety net) |
| `120_addis_ababa_low_income_blocks.zip` | 6,385 | point | Addis low-income blocks |
| `105_eth_roads.zip` | 1,650 | line | National roads |
| `80_eth_woreda_2013.zip` | 789 | polygon | Woreda (district) boundaries |
| `126_addis_ababa_woreda_1.zip` | 116 | polygon | Addis woreda boundaries |

(`x_…` = the 4 layers GeoServer serves via WFS but that are hidden from the REST catalog.)

## Coordinate reference systems

Layers were exported in their **native CRS** (preserved exactly, with `.prj`). The set mixes
four CRSs: `EPSG:4326` (WGS84, most layers), `EPSG:4201` (**Adindan** — the old Ethiopian
geographic datum), `EPSG:3857` (Web Mercator — the `x_…` layers), and `EPSG:32637`
(Adindan/WGS UTM 37N — woreda boundaries). For OSM merging, reproject everything to WGS84:

```bash
for z in shapefiles/*.zip; do
  n=$(basename "$z" .zip)
  ogr2ogr -t_srs EPSG:4326 "wgs84/$n.shp" "/vsizip/$z"
done
```

⚠️ The `EPSG:4201` (Adindan) layers need a **datum shift** to align with OSM/WGS84 — a plain
coordinate copy will be offset by ~100–200 m. `ogr2ogr -t_srs EPSG:4326` applies the shift
correctly; don't just relabel the `.prj`.

## Notes / caveats

- The portal uses a self-signed TLS certificate; requests were made with verification
  relaxed (`curl -k`). The host is genuine `ethionsdi.gov.et`.
- One catalog record (pk 72, `second_order_gcp`) crashes GeoNode's API serializer; it is
  also one of the 20 restricted layers, so it isn't downloaded here.
- WFS `GetFeature` returns all features by default (no row cap observed); `manifest` records
  the WFS `numberMatched` per layer so you can confirm completeness against each `.dbf`.
- Data is © the Ethiopian Geospatial Information Institute / EthioSDI. Check each layer's
  license/constraints in its metadata JSON before redistribution or merging into OSM
  (OSM requires a compatible license / explicit permission for imports).

## Restricted layers

To collect the remaining 20 vector layers, an EthioSDI login with download permission is
required. Once you have credentials, re-running is straightforward — authenticate to get a
session cookie, then the same WFS `SHAPE-ZIP` request works (or use the GeoNode "Download
Layer" button per dataset). Ask and I can wire credential-based auth into the downloader.
