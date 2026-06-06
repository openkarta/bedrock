#!/usr/bin/env python3
"""Stage 1 of cleanup: reproject every in-scope source layer to EPSG:4326 GeoJSON under
normalized/<source>/<layer>.geojson. Applies datum shifts (EDAS 404000, EthioSDI Adindan)
via each layer's embedded CRS. Usage: python3 normalize.py [source ...]   (default: all)."""
import os, sys, subprocess, glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.dirname(HERE)
SRC  = os.path.join(REPO, "sources")
NORM = os.path.join(HERE, "normalized")
from tagging import cbebank, fayda, edas        # for in-scope LAYERS lists

FORCE = "--force" in sys.argv

def ogr(out, src, oo=()):
    """Reproject `src` to EPSG:4326 GeoJSON at `out`. `oo` = extra open options (shapefiles use
    -oo ENCODING=CP1252 — their .dbf is CP1252, and a garbage .cpg makes GDAL mis-transcode)."""
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out) and os.path.getsize(out) > 50 and not FORCE:
        print(f"  skip {os.path.relpath(out, HERE):42} (exists)")
        return True
    oo = list(oo)
    # -spat ... -spat_srs EPSG:4326 drops features outside the world (some layers carry a garbage
    # +/-1.79e308 coordinate that otherwise makes PROJ hang); spat_srs makes the filter work for
    # any source CRS and excludes the bad feature BEFORE reprojection.
    def attempt(extra):
        if os.path.exists(out):
            os.remove(out)               # GeoJSON has no DeleteLayer; -overwrite fails -> write fresh
        try:
            p = subprocess.run(["ogr2ogr", "-f", "GeoJSON"] + oo + extra + [out, src],
                               capture_output=True, text=True, timeout=240)
            return (p.returncode == 0 and os.path.exists(out)), p.stderr
        except subprocess.TimeoutExpired:
            return False, "timed out (likely garbage coordinate)"
    # primary: reproject to WGS84 (handles Adindan / proper projected CRS via the .prj)
    ok, _ = attempt(["-lco", "RFC7946=YES", "-t_srs", "EPSG:4326",
                     "-spat", "-180", "-90", "180", "90", "-spat_srs", "EPSG:4326"])
    if ok:
        print(f"  ok  {os.path.relpath(out, HERE):42}")
        return True
    # fallback: coords already lon/lat but the CRS is bogus (EPSG:404000 LOCAL_CS). Relabel as
    # 4326 with NO reprojection (RFC7946/-t_srs would force a failing transform).
    ok, err = attempt(["-a_srs", "EPSG:4326", "-skipfailures"])
    print(f"  {'ok* ' if ok else 'ERR'} {os.path.relpath(out, HERE):42} "
          f"{'(assigned 4326, no reproject)' if ok else (err or '').strip()[:80]}")
    return ok

def do_geojson_dir(source, layers):
    n = 0
    for lyr in layers:
        src = os.path.join(SRC, source, "geojson", f"{lyr}.geojson")
        if os.path.exists(src) and ogr(os.path.join(NORM, source, f"{lyr}.geojson"), src):
            n += 1
    return n

SHP_OO = ["-oo", "ENCODING=CP1252"]    # shapefile .dbf is CP1252; .cpg is garbage

def do_shapefile_layers(source, layers):
    n = 0
    for lyr in layers:
        zp = os.path.join(SRC, source, "shapefiles", f"{lyr}.zip")
        if os.path.exists(zp) and ogr(os.path.join(NORM, source, f"{lyr}.geojson"), "/vsizip/" + zp, SHP_OO):
            n += 1
    return n

def do_all_shapefiles(source):
    n = 0
    for zp in sorted(glob.glob(os.path.join(SRC, source, "shapefiles", "*.zip"))):
        lyr = os.path.basename(zp)[:-4]
        if ogr(os.path.join(NORM, source, f"{lyr}.geojson"), "/vsizip/" + zp, SHP_OO):
            n += 1
    return n

def main(which):
    if "cbebank" in which:
        print("cbebank:");   print(f"  -> {do_geojson_dir('cbebank', cbebank.LAYERS)} layers")
    if "fayda" in which:
        print("fayda:");     print(f"  -> {do_geojson_dir('fayda', fayda.LAYERS)} layers")
    if "edas" in which:
        print("edas:");      print(f"  -> {do_shapefile_layers('edas', edas.LAYERS)} layers")
    if "ethionsdi" in which:
        print("ethionsdi:"); print(f"  -> {do_all_shapefiles('ethionsdi')} layers")

if __name__ == "__main__":
    sources = [a for a in sys.argv[1:] if not a.startswith("--")] or \
              ["cbebank", "fayda", "edas", "ethionsdi"]
    main(sources)
    print("\nDONE: normalized/ written (EPSG:4326 GeoJSON).")
