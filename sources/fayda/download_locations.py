#!/usr/bin/env python3
"""
Download all Fayda (National ID) registration-center locations from the public
"Fayda Near Me" API (id.gov.et) and emit per-type GeoJSON, plus a manifest.

Source:  GET https://id.gov.et/api/proxy/get/locations  ->  {"data": [ ... ]}
Output:  ./locations_raw.json            (immutable raw API response)
         ./geojson/<location_type>.geojson  (EPSG:4326 FeatureCollection per type)
         ./manifest.json + ./manifest.csv   (per-type index + provenance)

Re-runnable: re-fetches the API each run; if the fetch fails it falls back to the
existing locations_raw.json so the GeoJSON/manifest can still be rebuilt offline.
"""
import json, subprocess, os, re, time, csv, hashlib
from datetime import datetime, timezone

BASE       = "https://id.gov.et"
ENDPOINT   = "/api/proxy/get/locations"
SOURCE_URL = BASE + ENDPOINT
ROOT       = os.path.dirname(os.path.abspath(__file__))
GEOJSON_DIR = os.path.join(ROOT, "geojson")
RAW        = os.path.join(ROOT, "locations_raw.json")
os.makedirs(GEOJSON_DIR, exist_ok=True)

def slug(s):
    """Filesystem-safe slug for a location_type ('palace parking' -> 'palace_parking')."""
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', (s or "").lower()).strip('_')
    return s[:80] or "unknown"

def curl(args, retries=3, timeout=120):
    for i in range(retries):
        p = subprocess.run(["curl", "-sL", "--max-time", str(timeout)] + args,
                           capture_output=True)
        if p.returncode == 0:
            return p
        time.sleep(2 * (i + 1))
    return p

def fetch_raw():
    """Fetch the locations API to locations_raw.json; fall back to the cached copy."""
    p = curl(["-o", RAW, SOURCE_URL])
    try:
        doc = json.load(open(RAW, encoding="utf-8"))
        assert isinstance(doc.get("data"), list) and doc["data"], "no 'data' array"
        print(f"Fetched {SOURCE_URL} -> {len(doc['data'])} records "
              f"({os.path.getsize(RAW):,} bytes)")
        return doc
    except Exception as e:
        print(f"Fetch/parse failed ({e}); falling back to cached {os.path.basename(RAW)}")
        return json.load(open(RAW, encoding="utf-8"))

def feature(rec):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [rec["longitude"], rec["latitude"]]},
        "properties": {
            "name":      rec.get("location_name"),
            "type":      rec.get("location_type"),
            "status":    rec.get("status"),
            "gmaps_url": rec.get("address"),       # source 'address' is a Google Maps link
            "src_id":    rec.get("_id"),
            "created":   rec.get("created_at"),
            "updated":   rec.get("updated_at"),
        },
    }

def main():
    doc = fetch_raw()
    records = doc["data"]
    sha_raw = hashlib.sha256(open(RAW, "rb").read()).hexdigest()
    harvested = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # group records by location_type
    by_type = {}
    for r in records:
        by_type.setdefault(r.get("location_type") or "unknown", []).append(r)

    manifest = []
    # largest layers first, for a readable run log / manifest
    for ltype, recs in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        feats = [feature(r) for r in recs]
        lons = [r["longitude"] for r in recs]
        lats = [r["latitude"] for r in recs]
        bbox = [min(lons), min(lats), max(lons), max(lats)]
        fname = f"{slug(ltype)}.geojson"
        fpath = os.path.join(GEOJSON_DIR, fname)
        fc = {"type": "FeatureCollection", "name": ltype, "bbox": bbox, "features": feats}
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(fc, f, indent=2, ensure_ascii=False)

        sha = hashlib.sha256(open(fpath, "rb").read()).hexdigest()
        active = sum(1 for r in recs if (r.get("status") or "") == "active")
        manifest.append({
            "location_type": ltype,
            "file": f"geojson/{fname}",
            "features": len(feats),
            "active": active,
            "minlon": round(bbox[0], 6), "minlat": round(bbox[1], 6),
            "maxlon": round(bbox[2], 6), "maxlat": round(bbox[3], 6),
            "bytes": os.path.getsize(fpath),
            "sha256": sha,
            "source_url": SOURCE_URL,
            "harvested": harvested,
            "status": "ok",
        })
        print(f"  {ltype:16} {len(feats):>5} features ({active} active)  -> geojson/{fname}")

    json.dump(manifest, open(os.path.join(ROOT, "manifest.json"), "w"), indent=2)
    with open(os.path.join(ROOT, "manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        w.writeheader(); w.writerows(manifest)

    total = sum(m["features"] for m in manifest)
    print(f"\nDONE: {total:,} POIs across {len(manifest)} types. "
          f"raw sha256={sha_raw[:12]}…  manifest.json + manifest.csv written.")

if __name__ == "__main__":
    main()
