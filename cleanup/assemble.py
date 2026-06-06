#!/usr/bin/env python3
"""Stage 3 of cleanup: combine the per-layer pbfs into one sorted combined pbf.

`osmium cat` concatenates all per-layer files (no ordering requirement), then a single
`osmium sort` produces the canonical node<way<relation, id-ascending order. IDs are disjoint
negative blocks per file (set in to_osm.py), so nothing collides; negative ids are kept so the
data reads as "new" and never clashes with OSM's positive ids.

Usage:
  python3 assemble.py                          # -> osm/combined.osm.pbf
  python3 assemble.py /path/ethiopia.osm.pbf   # also -> osm/with_osm.osm.pbf (union, no dedup)
"""
import os, sys, subprocess, glob

HERE = os.path.dirname(os.path.abspath(__file__))
OSM = os.path.join(HERE, "osm")
DERIVED = {"combined.osm.pbf", "with_osm.osm.pbf", "combined.unsorted.osm.pbf"}

def run(*cmd):
    print("  $ osmium", " ".join(os.path.basename(c) if c.startswith(OSM) else c for c in cmd[1:]))
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print("    ERR:", (p.stderr or p.stdout).strip()[:200])
    return p.returncode == 0

def main(ethiopia_pbf=None):
    layers = [f for f in sorted(glob.glob(os.path.join(OSM, "*.osm.pbf")))
              if os.path.basename(f) not in DERIVED]
    print(f"combining {len(layers)} per-layer files:")
    for f in layers:
        print("   ", os.path.basename(f))
    combined = os.path.join(OSM, "combined.osm.pbf")
    unsorted = os.path.join(OSM, "combined.unsorted.osm.pbf")
    if not run("osmium", "cat", *layers, "-O", "-o", unsorted):
        return
    print("\nsort -> combined.osm.pbf:")
    run("osmium", "sort", unsorted, "-O", "-o", combined)
    os.path.exists(unsorted) and os.remove(unsorted)
    run("osmium", "fileinfo", "-e", combined)
    if ethiopia_pbf:
        print(f"\nunion with {ethiopia_pbf} (no dedup) -> with_osm.osm.pbf:")
        if os.path.exists(ethiopia_pbf):
            run("osmium", "merge", combined, ethiopia_pbf, "-O", "-o", os.path.join(OSM, "with_osm.osm.pbf"))
        else:
            print("    (ethiopia pbf not found — skipped)")
    print("\nDONE.")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
