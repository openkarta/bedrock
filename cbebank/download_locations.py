#!/usr/bin/env python3
"""
Download all Commercial Bank of Ethiopia (CBE) ATM locations from the public
"ATM & Branch Locator" Strapi API (combanketh.et) and emit a GeoJSON point
layer plus a manifest.

Source:  GET https://combanketh.et/api/atm-locations?populate=*  (paginated)
Output:  ./atm_locations_raw.json          (immutable raw API records, all pages)
         ./geojson/atm.geojson             (EPSG:4326 FeatureCollection of ATMs)
         ./manifest.json + ./manifest.csv  (inventory + provenance)

Only ATMs are geolocated by this source. The companion /api/branches endpoint
(1,934 branches) carries NO coordinates, so branches are out of scope here.

Re-runnable: re-fetches every page each run; if the fetch fails it falls back
to the existing atm_locations_raw.json so the GeoJSON/manifest can be rebuilt.
"""
import json, subprocess, os, time, csv, hashlib
from datetime import datetime, timezone

BASE       = "https://combanketh.et"
ENDPOINT   = "/api/atm-locations"
SOURCE_URL = BASE + ENDPOINT + "?populate=*"
PAGE_SIZE  = 200
ROOT       = os.path.dirname(os.path.abspath(__file__))
GEOJSON_DIR = os.path.join(ROOT, "geojson")
RAW        = os.path.join(ROOT, "atm_locations_raw.json")
os.makedirs(GEOJSON_DIR, exist_ok=True)

def curl(url, retries=3, timeout=120):
    # -g/--globoff is REQUIRED: the Strapi pagination[...] brackets would
    # otherwise be parsed as curl URL globs.
    for i in range(retries):
        p = subprocess.run(["curl", "-gsL", "--max-time", str(timeout), url],
                           capture_output=True)
        if p.returncode == 0 and p.stdout:
            return p.stdout
        time.sleep(2 * (i + 1))
    return p.stdout if p.returncode == 0 else None

def fetch_all():
    """Page through /api/atm-locations; return (records, pagination) or fall back to cache."""
    records, page, pages, total = [], 1, None, None
    while True:
        url = f"{BASE}{ENDPOINT}?populate=*&pagination[page]={page}&pagination[pageSize]={PAGE_SIZE}"
        body = curl(url)
        if body is None:
            raise RuntimeError(f"fetch failed at page {page}")
        doc = json.loads(body)
        records.extend(doc["data"])
        pag = doc["meta"]["pagination"]
        pages, total = pag["pageCount"], pag["total"]
        print(f"  page {page}/{pages}  (+{len(doc['data'])} -> {len(records)}/{total})")
        if page >= pages:
            break
        page += 1
    return records, {"total": total, "pageSize": PAGE_SIZE, "pageCount": pages}

def norm(rec):
    # Strapi v5 returns flat records; v4 would nest under .attributes.
    return rec["attributes"] if "attributes" in rec else rec

def feature(rec):
    r = norm(rec)
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
        "properties": {
            "name":        r.get("atmName"),
            "terminal_id": r.get("terminalId"),
            "branch":      r.get("branch"),       # parent branch / district grouping
            "district":    r.get("district"),
            "venue":       r.get("locationTypeDesc"),   # venue the ATM sits in
            "venue_code":  r.get("locationType"),
            "city":        r.get("city"),
            "telephone":   r.get("telephone"),
            "src_id":      r.get("documentId"),
        },
    }

def main():
    try:
        records, pagination = fetch_all()
        raw = {"source": SOURCE_URL,
               "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
               "pagination": pagination, "data": records}
        with open(RAW, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False)
    except Exception as e:
        print(f"Fetch failed ({e}); falling back to cached {os.path.basename(RAW)}")
        raw = json.load(open(RAW, encoding="utf-8"))
        records = raw["data"]
    sha_raw = hashlib.sha256(open(RAW, "rb").read()).hexdigest()
    harvested = raw.get("fetched") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # build ATM point layer (skip any record missing coordinates)
    feats, skipped = [], 0
    for rec in records:
        r = norm(rec)
        if r.get("lat") is None or r.get("lon") is None:
            skipped += 1
            continue
        feats.append(feature(rec))
    lons = [f["geometry"]["coordinates"][0] for f in feats]
    lats = [f["geometry"]["coordinates"][1] for f in feats]
    bbox = [min(lons), min(lats), max(lons), max(lats)]

    fpath = os.path.join(GEOJSON_DIR, "atm.geojson")
    fc = {"type": "FeatureCollection", "name": "CBE ATMs", "bbox": bbox, "features": feats}
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(fc, f, indent=2, ensure_ascii=False)
    sha = hashlib.sha256(open(fpath, "rb").read()).hexdigest()

    manifest = [{
        "layer": "atm",
        "file": "geojson/atm.geojson",
        "features": len(feats),
        "skipped_no_coords": skipped,
        "minlon": round(bbox[0], 6), "minlat": round(bbox[1], 6),
        "maxlon": round(bbox[2], 6), "maxlat": round(bbox[3], 6),
        "bytes": os.path.getsize(fpath),
        "sha256": sha,
        "source_url": SOURCE_URL,
        "harvested": harvested,
        "status": "ok",
    }]
    json.dump(manifest, open(os.path.join(ROOT, "manifest.json"), "w"), indent=2)
    with open(os.path.join(ROOT, "manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        w.writeheader(); w.writerows(manifest)

    print(f"\nDONE: {len(feats):,} ATM points "
          f"({skipped} skipped for missing coords). raw sha256={sha_raw[:12]}…  "
          f"geojson/atm.geojson + manifest written.")

if __name__ == "__main__":
    main()
