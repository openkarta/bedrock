#!/usr/bin/env python3
"""Verify the ATM GeoJSON with ogrinfo (GDAL). Reports geometry type, feature
count, and CRS, cross-checks the count against atm_locations_raw.json, and
sanity-checks coordinates against Ethiopia's bounding box. A handful of stray
out-of-bbox points are reported as a note; a wholesale miss is flagged.
Writes verification.csv."""
import json, os, re, subprocess, glob, csv

ROOT = os.path.dirname(os.path.abspath(__file__))
GEOJSON_DIR = os.path.join(ROOT, "geojson")
RAW = os.path.join(ROOT, "atm_locations_raw.json")

# Ethiopia bounding box (generous), for a coordinate sanity check.
LON_MIN, LON_MAX = 32.9, 48.0
LAT_MIN, LAT_MAX = 3.3, 15.0

raw = json.load(open(RAW, encoding="utf-8"))
raw_records = raw["data"]
raw_with_coords = sum(1 for r in raw_records
                      if (r.get("attributes") or r).get("lat") is not None
                      and (r.get("attributes") or r).get("lon") is not None)

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

def bbox_scan(path):
    """Return (in_bbox, out_of_bbox, out_samples) for the layer's points."""
    fc = json.load(open(path, encoding="utf-8"))
    inb = outb = 0
    samples = []
    for ft in fc.get("features", []):
        lon, lat = ft["geometry"]["coordinates"]
        if LON_MIN <= lon <= LON_MAX and LAT_MIN <= lat <= LAT_MAX:
            inb += 1
        else:
            outb += 1
            if len(samples) < 8:
                p = ft["properties"]
                samples.append(f"{p.get('terminal_id')}@({lat},{lon})")
    return inb, outb, samples

rows = []
files = sorted(glob.glob(os.path.join(GEOJSON_DIR, "*.geojson")))
print(f"Verifying {len(files)} GeoJSON layer(s)...\n")
for path in files:
    fname = os.path.basename(path)
    geom, nf, epsg, note = ogr_summary(path)
    inbb = outbb = None
    out_samples = []
    if note == "ok":
        inbb, outbb, out_samples = bbox_scan(path)

    flag = ""
    if note != "ok":                                  flag = "BADFILE"
    elif nf == 0:                                      flag = "EMPTY"
    elif nf != raw_with_coords:                        flag = "COUNT_MISMATCH"
    elif epsg not in ("4326", "CRS84"):               flag = "BAD_CRS"
    elif inbb == 0:                                    flag = "OUT_OF_BBOX"     # systemic
    if not flag and outbb:                            note = f"{outbb} pt(s) outside ETH bbox"

    rows.append({"file": f"geojson/{fname}", "geometry": geom, "features": nf,
                 "epsg": epsg, "raw_features": raw_with_coords,
                 "in_bbox": inbb, "out_bbox": outbb, "flag": flag, "note": note})
    match = "=" if nf == raw_with_coords else f"≠raw({raw_with_coords})"
    print(f"  {fname:16} {str(geom):8} {str(nf):>6} feats  EPSG:{str(epsg):6} "
          f"in_bbox={inbb} out={outbb} {match:12} {flag or note}")
    if out_samples:
        print(f"      out-of-bbox: {', '.join(out_samples)}")

with open(os.path.join(ROOT, "verification.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

flagged = [r for r in rows if r["flag"]]
total_feats = sum(r["features"] or 0 for r in rows)
print(f"\n=== SUMMARY ===")
print(f"layers:          {len(rows)}")
print(f"total features:  {total_feats:,}  (raw records with coords: {raw_with_coords:,}; "
      f"raw total: {len(raw_records):,})")
print(f"hard-flagged:    {len(flagged)}")
for r in flagged:
    print(f"   {r['flag']}: {r['file']} ({r['note']})")
print("\nverification.csv written.")
