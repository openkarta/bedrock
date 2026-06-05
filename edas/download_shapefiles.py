#!/usr/bin/env python3
"""
Download every published VECTOR layer from the EDAS GeoServer
(edas.et:8080/geoserver) as a shapefile, via WFS GetFeature SHAPE-ZIP.

The layer list + per-layer metadata come straight from WFS GetCapabilities
(this is a plain GeoServer, with no GeoNode catalog API). WFS only serves
vector data, so every served layer is in scope.

Output: ./shapefiles/<name>.zip + ./metadata/<name>.json + manifests
Re-runnable: existing valid zips are skipped (resumable).
"""
import json, subprocess, time, os, re, csv, hashlib, html, urllib.parse

BASE = "http://edas.et:8080/geoserver"
WFS  = BASE + "/wfs"
ROOT = os.path.dirname(os.path.abspath(__file__))
SHP_DIR  = os.path.join(ROOT, "shapefiles")
META_DIR = os.path.join(ROOT, "metadata")
CAPS     = os.path.join(ROOT, "wfs_capabilities.xml")
DELAY    = 0.5          # politeness delay between layers (seconds)
os.makedirs(SHP_DIR, exist_ok=True)
os.makedirs(META_DIR, exist_ok=True)

# Layers present on the GeoServer but deliberately NOT downloaded, keyed by slug.
# Curated to one canonical layer per dataset (the server publishes many byte-identical
# web/mobile/version copies), dropping 1-feature pgRouting view stubs and the two layers
# whose backing table is missing server-side. Recorded in excluded_layers.json.
EXCLUDE = {
    # exact duplicates -> keep the canonical layer named in the reason
    "road_close":            "duplicate of road_network (65,973 features)",
    "road_network111111":    "duplicate of road_network (65,973 features)",
    "road_network222":       "duplicate of road_network (65,973 features)",
    "road_network_adama":    "duplicate of road_network (65,973 features)",
    "road_network_mobile":   "duplicate of road_network (65,973 features)",
    "road_network_mobile11": "duplicate of road_network (65,973 features)",
    "parcel_mobile_v7":      "duplicate of parcel_web_v7 (741,888 features)",
    "lulc_v711":             "duplicate of lulc_v7 (113,105 features)",
    "building_mobile_v7":    "duplicate of building_web_v7 (64,123 features)",
    "landmark":              "duplicate of landmark_web_v7 (10,202 features)",
    "landmark__mobile_v7":   "duplicate of landmark_web_v7 (10,202 features)",
    "nh_aoi_v7":             "duplicate of nh_aoi_web_v7 (3,780 features)",
    "road_signs_mobile":     "duplicate of road_signs (102 features)",
    # 1-feature pgRouting view stubs (parametric routing endpoints, not real data)
    "pgr_ksp": "1-feature pgRouting stub", "pgr_ksp11": "1-feature pgRouting stub",
    "pgr_ksp33": "1-feature pgRouting stub", "pgr_ksp_adama": "1-feature pgRouting stub",
    "pgr_ksp_special": "1-feature pgRouting stub",
    "routing": "1-feature pgRouting stub", "routing11": "1-feature pgRouting stub",
    "route_guidance": "1-feature pgRouting stub", "route_guidance00": "1-feature pgRouting stub",
    "route_guidance11": "1-feature pgRouting stub", "route_guidance33": "1-feature pgRouting stub",
    # published but unusable: WFS GetFeature fails ("Schema does not exist" — backing table gone)
    "adama_rd_network_wgs84_v1": "server schema error: WFS GetFeature fails (backing table missing)",
    "road_polygon":              "server schema error: WFS GetFeature fails (backing table missing)",
}

def slug(name):
    s = re.sub(r'^[^:]+:', '', name or '')          # strip 'geoserver:' workspace prefix
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', s).strip('_')
    return s[:80] or "layer"

def curl(args, retries=3, timeout=900):
    for i in range(retries):
        p = subprocess.run(["curl", "-s", "--max-time", str(timeout)] + args,
                           capture_output=True)
        if p.returncode == 0:
            return p
        time.sleep(2 * (i + 1))
    return p

def get_capabilities():
    """Fetch + parse WFS GetCapabilities into a list of layer metadata dicts."""
    p = curl(["-o", CAPS, f"{WFS}?service=WFS&version=2.0.0&request=GetCapabilities"])
    xml = open(CAPS, encoding="utf-8", errors="ignore").read()
    def g(block, tag):
        m = re.search(rf'<{tag}\b[^>]*>(.*?)</{tag}>', block, re.S)
        return html.unescape(m.group(1).strip()) if m else ""
    layers = []
    for b in re.findall(r'<FeatureType\b[^>]*>(.*?)</FeatureType>', xml, re.S):
        name = g(b, "Name")
        crs  = g(b, "DefaultCRS") or g(b, "DefaultSRS")
        em   = re.search(r'(\d{4,6})\s*$', crs)
        lc   = g(b, "ows:LowerCorner") or g(b, "LowerCorner")
        uc   = g(b, "ows:UpperCorner") or g(b, "UpperCorner")
        bbox = None
        if lc and uc:
            lo = [float(x) for x in lc.split()]; up = [float(x) for x in uc.split()]
            bbox = [lo[0], lo[1], up[0], up[1]]      # minlon, minlat, maxlon, maxlat
        kw = re.findall(r'<(?:ows:)?Keyword>([^<]+)</', b)
        layers.append({
            "name": name, "title": g(b, "Title"), "abstract": g(b, "Abstract"),
            "srid": f"EPSG:{em.group(1)}" if em else crs, "wgs84_bbox": bbox,
            "keywords": [html.unescape(k) for k in kw],
            "source": f"{WFS}?request=GetFeature&typeName={name}",
        })
    return layers

def wfs_hits(typename):
    """Return feature count via WFS resultType=hits, or None."""
    url = (f"{WFS}?service=WFS&version=2.0.0&request=GetFeature"
           f"&typeNames={urllib.parse.quote(typename)}&resultType=hits")
    p = curl([url], timeout=180)
    txt = p.stdout.decode("utf-8", "ignore")
    m = (re.search(r'numberMatched=["\'](\d+)', txt) or
         re.search(r'numberOfFeatures=["\'](\d+)', txt))
    return int(m.group(1)) if m else None

def main():
    layers = get_capabilities()
    print(f"WFS GetCapabilities: {len(layers)} vector layers\n")

    manifest, excluded = [], []
    for i, lyr in enumerate(layers, 1):
        name = lyr["name"]
        base = slug(name)

        if base in EXCLUDE:                      # curated out — record but do not download
            excluded.append({"name": name, "title": lyr["title"], "srid": lyr["srid"],
                             "features": wfs_hits(name), "reason": EXCLUDE[base]})
            print(f"[{i:>2}/{len(layers)}] exclude {base:40} ({EXCLUDE[base]})")
            time.sleep(DELAY)
            continue

        fname = f"{base}.zip"
        fpath = os.path.join(SHP_DIR, fname)
        json.dump(lyr, open(os.path.join(META_DIR, f"{base}.json"), "w"), indent=2)

        valid = (os.path.exists(fpath) and os.path.getsize(fpath) > 200
                 and open(fpath, "rb").read(2) == b"PK")
        if valid:
            print(f"[{i:>2}/{len(layers)}] skip (exists) {fname}")
            status = "exists"
        else:
            url = (f"{WFS}?service=WFS&version=1.0.0&request=GetFeature"
                   f"&typeName={urllib.parse.quote(name)}&outputFormat=SHAPE-ZIP")
            curl(["-o", fpath, url])
            ok = (os.path.exists(fpath) and os.path.getsize(fpath) > 200
                  and open(fpath, "rb").read(2) == b"PK")
            status = "ok" if ok else "FAILED"
            sz = os.path.getsize(fpath) if os.path.exists(fpath) else 0
            print(f"[{i:>2}/{len(layers)}] {status:6} {fname:40} {sz:>11,}b  {lyr['title'][:32]}")
            if not ok and os.path.exists(fpath):
                os.rename(fpath, fpath + ".error.txt")   # keep server error body

        hits = wfs_hits(name)
        sha  = (hashlib.sha256(open(fpath, "rb").read()).hexdigest()
                if os.path.exists(fpath) else None)
        manifest.append({
            "name": name, "title": lyr["title"], "file": fname,
            "srid": lyr["srid"], "features": hits, "status": status,
            "bytes": os.path.getsize(fpath) if os.path.exists(fpath) else 0,
            "sha256": sha, "source_url": lyr["source"],
        })
        time.sleep(DELAY)

    json.dump(manifest, open(os.path.join(ROOT, "manifest.json"), "w"), indent=2)
    with open(os.path.join(ROOT, "manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        w.writeheader(); w.writerows(manifest)

    json.dump({
        "note": ("Layers published by the EDAS GeoServer but deliberately not downloaded "
                 "(duplicates, 1-feature routing stubs, and layers broken server-side). "
                 "The full server inventory is in wfs_capabilities.xml."),
        "count": len(excluded),
        "layers": excluded,
    }, open(os.path.join(ROOT, "excluded_layers.json"), "w"), indent=2)

    okc = sum(1 for m in manifest if m["status"] in ("ok", "exists"))
    tot = sum(m["features"] or 0 for m in manifest if m["status"] in ("ok", "exists"))
    print(f"\nDONE: {okc}/{len(manifest)} layers downloaded, ~{tot:,} features; "
          f"{len(excluded)} excluded. manifest.* + excluded_layers.json written.")

if __name__ == "__main__":
    main()
