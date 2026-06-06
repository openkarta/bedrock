#!/usr/bin/env python3
"""Stage 2 of cleanup: apply per-source OSM tagging to the normalized GeoJSON and write one
.osm.pbf PER LOGICAL LAYER, named osm/<source>-<group>.osm.pbf.

Grouping: a source's tagging module may define group(layer, tags); otherwise features are
routed by their primary OSM key (roads/buildings/landuse/places/boundaries/pois). This merges
many small source layers into a few logical layers and splits large sources into multiple files.
Each output file gets a disjoint NEGATIVE id block so everything merges cleanly later.

Usage: python3 to_osm.py [source ...]   (default: all)."""
import os, sys, json, glob, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
NORM = os.path.join(HERE, "normalized")
OSM  = os.path.join(HERE, "osm")
from lib.geojson_osm import OsmBuilder, add_geometry
from tagging import cbebank, fayda, edas, ethionsdi

SOURCES = [("cbebank", cbebank), ("fayda", fayda), ("edas", edas), ("ethionsdi", ethionsdi)]

# route a feature to a logical layer by its primary OSM key (fallback when no module.group)
def category(t):
    if any(k in t for k in ("highway", "area:highway", "junction", "traffic_sign")): return "roads"
    if "building" in t:                                                              return "buildings"
    if any(k in t for k in ("landuse", "natural", "leisure", "waterway")):           return "landuse"
    if "place" in t:                                                                 return "places"
    if "boundary" in t:                                                              return "boundaries"
    return "pois"

def _block(name):
    """Deterministic negative-id block per output file (run-order independent), so partial
    regenerations never collide with already-committed layers and unchanged layers stay
    byte-identical. 1e9 buckets x 2e9 ids each fits comfortably in int64."""
    return int(hashlib.md5(name.encode()).hexdigest()[:9], 16) % 1_000_000_000

# --- precision cleanup (applies to every source, every geometry) ---
MIN_DECIMALS = 5   # drop a feature whose coordinates are ALL coarser than this (rounded source)

def _dec(v):
    s = repr(float(v))
    return 0 if ("e" in s or "E" in s) else (len(s.split(".")[1]) if "." in s else 0)

def _pairs(c):
    """Yield (lon, lat) pairs from any GeoJSON coordinates nesting."""
    if c and isinstance(c[0], (int, float)):
        yield c[0], c[1]
    else:
        for x in c:
            yield from _pairs(x)

def precise_enough(geom):
    """Keep the feature iff at least one vertex has >= MIN_DECIMALS decimals on BOTH lon & lat.
    Points: their single coordinate must qualify. Lines/polygons: kept unless every vertex is
    coarse (uniformly low-precision)."""
    c = (geom or {}).get("coordinates")
    if not c:
        return True
    for lon, lat in _pairs(c):
        if min(_dec(lon), _dec(lat)) >= MIN_DECIMALS:
            return True
    return False

def layer_files(source, module):
    d = os.path.join(NORM, source)
    if getattr(module, "LAYERS", None):
        return [(l, os.path.join(d, f"{l}.geojson")) for l in module.LAYERS
                if os.path.exists(os.path.join(d, f"{l}.geojson"))]
    return [(os.path.basename(f)[:-8], f) for f in sorted(glob.glob(os.path.join(d, "*.geojson")))]

def convert(source, module):
    os.makedirs(OSM, exist_ok=True)
    grouper = getattr(module, "group", None)
    builders, feats, tagged = {}, 0, 0
    def get(g):
        if g not in builders:
            name = f"{source}-{g}"
            builders[g] = OsmBuilder(os.path.join(OSM, f"{name}.osm.pbf"), source_block=_block(name))
        return builders[g]
    for layer, path in layer_files(source, module):
        fc = json.load(open(path, encoding="utf-8"))
        nlt = nt = 0
        for ft in fc.get("features", []):
            nlt += 1
            props, geom = ft.get("properties") or {}, ft.get("geometry")
            if not precise_enough(geom):          # global <5-decimal precision cleanup
                continue
            t = module.tags(props, layer)
            if not t:
                continue
            g = grouper(layer, t) if grouper else category(t)
            add_geometry(get(g), geom, t)
            nt += 1
        feats += nlt; tagged += nt
        print(f"  {layer:34} {nt:>7}/{nlt:<7} tagged")
    out = {}
    for g, b in builders.items():
        out[f"{source}-{g}"] = b.flush()
    print(f"=> {source}: tagged {tagged}/{feats} into {len(builders)} file(s):")
    for name, c in out.items():
        print(f"     {name+'.osm.pbf':32} {c}")
    print()

def main(which):
    for source, module in SOURCES:
        if source in which:
            print(f"### {source} ###")
            convert(source, module)

if __name__ == "__main__":
    sources = sys.argv[1:] or [s for s, _ in SOURCES]
    main(sources)
    print("DONE: osm/<source>-<group>.osm.pbf written.")
