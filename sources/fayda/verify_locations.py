#!/usr/bin/env python3
"""Verify every per-type GeoJSON with ogrinfo (GDAL). Reports geometry type,
feature count, and CRS, cross-checks the count against locations_raw.json, and
sanity-checks that every point falls inside Ethiopia's bounding box. Flags any
empty, mis-counted, wrong-CRS, or out-of-bounds layer -> verification.csv."""
import json, os, re, subprocess, glob, csv

ROOT = os.path.dirname(os.path.abspath(__file__))
GEOJSON_DIR = os.path.join(ROOT, "geojson")
RAW = os.path.join(ROOT, "locations_raw.json")

# Ethiopia bounding box (generous), for a coordinate sanity check.
LON_MIN, LON_MAX = 32.9, 48.0
LAT_MIN, LAT_MAX = 3.3, 15.0

# expected feature count per location_type, straight from the raw source
raw = json.load(open(RAW, encoding="utf-8"))["data"]
raw_counts = {}
for r in raw:
    t = r.get("location_type") or "unknown"
    raw_counts[t] = raw_counts.get(t, 0) + 1

def ogr_summary(path):
    """Return (geomtype, nfeatures, epsg, note) via ogrinfo -so."""
    p = subprocess.run(["ogrinfo", "-so", "-al", path], capture_output=True, text=True)
    out = p.stdout
    if p.returncode != 0 or "Feature Count" not in out:
        return (None, None, None, (p.stderr or out)[:80].strip())
    geom = (re.search(r"Geometry:\s*(.+)", out) or [None, "?"])[1].strip()
    nf   = int((re.search(r"Feature Count:\s*(\d+)", out) or [0, 0])[1])
    m = re.search(r'ID\["EPSG",(\d+)\]\]\s*$', out, re.M) or re.search(r'"EPSG",(\d+)', out)
    epsg = m.group(1) if m else ("CRS84" if "CRS84" in out else "?")
    return (geom, nf, epsg, "ok")

def in_bbox_count(path):
    """Count features whose point lies inside the Ethiopia bbox."""
    fc = json.load(open(path, encoding="utf-8"))
    n = 0
    for ft in fc.get("features", []):
        lon, lat = ft["geometry"]["coordinates"]
        if LON_MIN <= lon <= LON_MAX and LAT_MIN <= lat <= LAT_MAX:
            n += 1
    return n

rows, total_feats = [], 0
geom_counts = {}
files = sorted(glob.glob(os.path.join(GEOJSON_DIR, "*.geojson")))
print(f"Verifying {len(files)} GeoJSON layers...\n")
for path in files:
    fname = os.path.basename(path)
    ltype = re.sub(r"\.geojson$", "", fname)
    geom, nf, epsg, note = ogr_summary(path)
    inbb = in_bbox_count(path) if note == "ok" else None
    raw_n = raw_counts.get(ltype)
    # type slug may differ from raw type label (e.g. 'palace parking'); match by count fallback
    if raw_n is None:
        raw_n = next((c for t, c in raw_counts.items()
                      if re.sub(r'[^a-z0-9]+', '_', t.lower()).strip('_') == ltype), None)

    flag = ""
    if note != "ok":                              flag = "BADFILE"
    elif nf == 0:                                 flag = "EMPTY"
    elif raw_n is not None and nf != raw_n:       flag = "COUNT_MISMATCH"
    elif epsg not in ("4326", "CRS84"):           flag = "BAD_CRS"
    elif inbb is not None and inbb != nf:         flag = "OUT_OF_BBOX"

    if nf:
        total_feats += nf
    geom_counts[geom] = geom_counts.get(geom, 0) + 1
    rows.append({"file": f"geojson/{fname}", "geometry": geom, "features": nf,
                 "epsg": epsg, "raw_features": raw_n, "in_bbox": inbb,
                 "flag": flag, "note": note})
    match = "=" if (raw_n is not None and nf == raw_n) else f"≠raw({raw_n})"
    print(f"  {fname:24} {str(geom):8} {str(nf):>5} feats  EPSG:{str(epsg):6} "
          f"in_bbox={str(inbb):>5} {match:10} {flag}")

with open(os.path.join(ROOT, "verification.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

flagged = [r for r in rows if r["flag"]]
print(f"\n=== SUMMARY ===")
print(f"layers:          {len(rows)}")
print(f"total features:  {total_feats:,}  (raw total: {len(raw):,})")
print(f"geometry types:  {geom_counts}")
print(f"flagged layers:  {len(flagged)}")
for r in flagged:
    print(f"   {r['flag']}: {r['file']} ({r['note']}, raw={r['raw_features']}, got={r['features']})")
print("\nverification.csv written.")
