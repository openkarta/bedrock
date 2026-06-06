#!/usr/bin/env python3
"""Verify every downloaded shapefile zip with ogrinfo (via GDAL /vsizip/).
Reports geometry type, feature count, CRS, and cross-checks against the WFS
feature count recorded in manifest.json. Flags empty or mismatched layers."""
import json, os, re, subprocess, glob, csv

ROOT = os.path.dirname(os.path.abspath(__file__))
SHP_DIR = os.path.join(ROOT, "shapefiles")
manifest = {m["file"]: m for m in json.load(open(os.path.join(ROOT, "manifest.json")))}

def ogr_summary(zippath):
    """Return (layer, geomtype, nfeatures, crs) using ogrinfo -so."""
    # find the .shp inside the zip
    lst = subprocess.run(["unzip","-Z1",zippath], capture_output=True, text=True).stdout
    shp = next((l for l in lst.splitlines() if l.lower().endswith(".shp")), None)
    if not shp:
        return (None, None, None, None, "no .shp in zip")
    vsi = f"/vsizip/{zippath}/{shp}"
    p = subprocess.run(["ogrinfo","-so","-al", vsi], capture_output=True, text=True)
    out = p.stdout
    if p.returncode != 0 or "Feature Count" not in out:
        return (shp, None, None, None, (p.stderr or out)[:80].strip())
    geom = (re.search(r"Geometry:\s*(.+)", out) or [None,"?"])[1].strip()
    nf   = int((re.search(r"Feature Count:\s*(\d+)", out) or [0,0])[1])
    crs  = (re.search(r'ID\["EPSG",(\d+)\]\]\s*$', out, re.M) or
            re.search(r'"EPSG",(\d+)', out) or [None,"?"])[1]
    return (shp, geom, nf, crs, "ok")

rows, total_feats = [], 0
geom_counts = {}
zips = sorted(glob.glob(os.path.join(SHP_DIR, "*.zip")))
print(f"Verifying {len(zips)} shapefile archives...\n")
for z in zips:
    fname = os.path.basename(z)
    shp, geom, nf, crs, note = ogr_summary(z)
    m = manifest.get(fname, {})
    wfs = m.get("features")
    match = "" if (wfs is None or nf is None) else ("=" if wfs == nf else f"≠WFS({wfs})")
    flag = ""
    if note != "ok": flag = "BADZIP"
    elif nf == 0:    flag = "EMPTY"
    elif match.startswith("≠"): flag = "COUNT_MISMATCH"
    if nf: total_feats += nf
    geom_counts[geom] = geom_counts.get(geom, 0) + 1
    rows.append({"file": fname, "geometry": geom, "features": nf, "epsg": crs,
                 "wfs_features": wfs, "flag": flag, "note": note})
    print(f"  {fname:52} {str(geom):14} {str(nf):>7} feats  EPSG:{str(crs):6} {match:10} {flag}")

# write verification report
with open(os.path.join(ROOT, "verification.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

bad   = [r for r in rows if r["flag"] == "BADZIP"]
empty = [r for r in rows if r["flag"] == "EMPTY"]
mism  = [r for r in rows if r["flag"] == "COUNT_MISMATCH"]
print(f"\n=== SUMMARY ===")
print(f"archives:        {len(rows)}")
print(f"total features:  {total_feats:,}")
print(f"geometry types:  {geom_counts}")
print(f"bad/empty/mismatch: {len(bad)} bad, {len(empty)} empty, {len(mism)} count-mismatch")
for label, lst in [("BAD", bad), ("EMPTY", empty), ("MISMATCH", mism)]:
    for r in lst: print(f"   {label}: {r['file']} ({r['note']}, wfs={r['wfs_features']}, got={r['features']})")
print("\nverification.csv written.")
