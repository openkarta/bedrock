#!/usr/bin/env python3
"""
Download all VECTOR datasets from the Ethiopian SDI GeoNode (ethionsdi.gov.et)
as shapefiles, via GeoServer WFS SHAPE-ZIP. Rasters / imagery are skipped.

Self-contained — no external inputs. The download set comes from WFS
GetCapabilities and the rich metadata from the GeoNode /api/v2/ catalog;
both are cached IN PLACE (wfs_downloadable_layers.txt, metadata_full_catalog.json)
and reused on re-runs. Delete either file to refetch it from the server.

Output: ./shapefiles/<pk>_<name>.zip + ./metadata/<pk>_<name>.json + manifests
"""
import json, subprocess, time, os, re, sys, csv, hashlib

BASE = "https://ethionsdi.gov.et"
ROOT = os.path.dirname(os.path.abspath(__file__))
SHP_DIR    = os.path.join(ROOT, "shapefiles")
META_DIR   = os.path.join(ROOT, "metadata")
CATALOG    = os.path.join(ROOT, "metadata_full_catalog.json")   # GeoNode catalog dump
WFS_LAYERS = os.path.join(ROOT, "wfs_downloadable_layers.txt")  # WFS-served layer names
DELAY      = 1.0          # politeness delay between layers (seconds)
os.makedirs(SHP_DIR, exist_ok=True)
os.makedirs(META_DIR, exist_ok=True)

def slug(s):
    s = re.sub(r'^geonode:', '', s or '')
    s = re.sub(r'_[0-9a-f]{32}$', '', s)          # strip GeoNode hash suffix
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', s).strip('_')
    return s[:80] or "layer"

def curl(args, retries=3, timeout=300):
    for i in range(retries):
        p = subprocess.run(["curl","-ks","--max-time",str(timeout)]+args,
                           capture_output=True)
        if p.returncode == 0:
            return p
        time.sleep(2*(i+1))
    return p

def wfs_hits(typename):
    """Return feature count via WFS resultType=hits, or None."""
    url = (f"{BASE}/geoserver/wfs?service=WFS&version=2.0.0&request=GetFeature"
           f"&typeNames={typename}&resultType=hits")
    p = curl([url], timeout=120)
    txt = p.stdout.decode("utf-8","ignore")
    m = re.search(r'numberMatched=["\'](\d+)["\']', txt) or \
        re.search(r'numberOfFeatures=["\'](\d+)["\']', txt)
    return int(m.group(1)) if m else None

def fetch_catalog():
    """Pull the full GeoNode catalog from /api/v2/datasets/ into CATALOG (in place).
    Paginated with a small page size so the one serializer-crashing record (pk 72)
    only breaks its own page, which is skipped."""
    print("metadata_full_catalog.json missing — fetching GeoNode catalog from /api/v2/ ...")
    ps = 10
    first = json.loads(curl([f"{BASE}/api/v2/datasets/?page=1&page_size={ps}"]).stdout
                       .decode("utf-8", "ignore"))
    total = first.get("total", 0)
    pages = max(1, (total + ps - 1) // ps)
    out, skipped = list(first.get("datasets") or []), 0
    for pg in range(2, pages + 1):
        body = curl([f"{BASE}/api/v2/datasets/?page={pg}&page_size={ps}"]).stdout.decode("utf-8", "ignore")
        try:
            out.extend(json.loads(body).get("datasets") or [])
        except Exception:
            skipped += 1
            print(f"  page {pg}/{pages} did not parse (serializer crash) — skipped")
        time.sleep(0.3)
    json.dump(out, open(CATALOG, "w"), indent=2)
    print(f"  catalog: {len(out)} datasets ({skipped} page(s) skipped) -> {os.path.basename(CATALOG)}")
    return out

def fetch_wfs_layers():
    """Derive the WFS-served layer list from GetCapabilities into WFS_LAYERS (in place)."""
    print("wfs_downloadable_layers.txt missing — deriving from WFS GetCapabilities ...")
    xml = curl([f"{BASE}/geoserver/wfs?service=WFS&version=2.0.0&request=GetCapabilities"]).stdout \
            .decode("utf-8", "ignore")
    names = sorted({m for m in re.findall(r'<Name>([^<]+)</Name>', xml) if m.startswith("geonode:")})
    with open(WFS_LAYERS, "w") as f:
        f.write("\n".join(names) + "\n")
    print(f"  WFS layers: {len(names)} -> {os.path.basename(WFS_LAYERS)}")
    return names

def load_catalog():
    return json.load(open(CATALOG)) if os.path.exists(CATALOG) else fetch_catalog()

def load_wfs_layers():
    if os.path.exists(WFS_LAYERS):
        return sorted(l.strip() for l in open(WFS_LAYERS) if l.strip().startswith("geonode:"))
    return fetch_wfs_layers()

def main():
    ds = load_catalog()
    by_alt = {x["alternate"]: x for x in ds}

    # Authoritative download set = layers GeoServer actually serves via WFS
    # GetCapabilities. (Anonymous-restricted vector layers are absent there.)
    wfs_layers = load_wfs_layers()
    print(f"Catalog datasets: {len(ds)} | WFS-downloadable layers: {len(wfs_layers)}\n")

    manifest = []
    for i, alt in enumerate(wfs_layers, 1):
        x     = by_alt.get(alt, {})       # metadata if present in API catalog
        pk    = x.get("pk") or "x"        # 'x' = WFS-only (not in API catalog)
        name  = slug(alt)
        fname = f"{pk}_{name}.zip"
        fpath = os.path.join(SHP_DIR, fname)
        title = (x.get("title") or "").strip()

        # save per-dataset metadata
        json.dump(x, open(os.path.join(META_DIR, f"{pk}_{name}.json"), "w"), indent=2)

        if os.path.exists(fpath) and os.path.getsize(fpath) > 200:
            print(f"[{i:>3}/{len(wfs_layers)}] skip (exists) {fname}")
            status = "exists"
        else:
            url = (f"{BASE}/geoserver/wfs?service=WFS&version=1.0.0&request=GetFeature"
                   f"&typeName={alt}&outputFormat=SHAPE-ZIP")
            p = curl(["-o", fpath, url])
            ok = (os.path.exists(fpath) and os.path.getsize(fpath) > 200
                  and open(fpath,"rb").read(2) == b"PK")
            status = "ok" if ok else "FAILED"
            sz = os.path.getsize(fpath) if os.path.exists(fpath) else 0
            print(f"[{i:>3}/{len(wfs_layers)}] {status:6} {fname:55} {sz:>9}b  {title[:40]}")
            if not ok:
                # keep the error body for diagnosis
                if os.path.exists(fpath):
                    os.rename(fpath, fpath + ".error.txt")

        hits = wfs_hits(alt)
        sha  = (hashlib.sha256(open(fpath,"rb").read()).hexdigest()
                if os.path.exists(fpath) else None)
        manifest.append({
            "pk": pk, "title": title, "alternate": alt, "file": fname,
            "srid": x.get("srid"), "category": (x.get("category") or {}).get("identifier")
                    if isinstance(x.get("category"), dict) else x.get("category"),
            "features": hits, "status": status,
            "bytes": os.path.getsize(fpath) if os.path.exists(fpath) else 0,
            "sha256": sha,
            "abstract": (x.get("raw_abstract") or x.get("abstract") or "")[:500],
            "detail_url": f"{BASE}/catalogue/#/dataset/{pk}",
        })
        time.sleep(DELAY)

    json.dump(manifest, open(os.path.join(ROOT,"manifest.json"),"w"), indent=2)
    with open(os.path.join(ROOT,"manifest.csv"),"w",newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        w.writeheader(); w.writerows(manifest)

    okc = sum(1 for m in manifest if m["status"] in ("ok","exists"))
    print(f"\nDONE: {okc}/{len(manifest)} shapefiles present. "
          f"manifest.json + manifest.csv written.")

if __name__ == "__main__":
    main()
