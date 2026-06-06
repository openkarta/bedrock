#!/usr/bin/env python3
"""Stage 4 of cleanup: verify each osm/<source>.osm.pbf — primitive counts, how many primitives
carry a primary OSM feature tag, and name / name:en / name:am coverage among those. Writes
report.csv and prints a summary. Usage: python3 verify_osm.py [source ...]"""
import os, sys, csv, glob
import osmium

HERE = os.path.dirname(os.path.abspath(__file__))
OSM = os.path.join(HERE, "osm")

PRIMARY = {"amenity", "shop", "highway", "building", "landuse", "natural", "place", "office",
           "tourism", "boundary", "leisure", "man_made", "aeroway", "traffic_sign",
           "area:highway", "junction", "government", "waterway", "barrier"}

class Stats(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.nodes = self.ways = self.rels = 0
        self.feat = self.with_name = self.with_en = self.with_am = 0
    def _tagged(self, o):
        t = o.tags
        if any(k in t for k in PRIMARY):
            self.feat += 1
            if "name" in t:    self.with_name += 1
            if "name:en" in t: self.with_en += 1
            if "name:am" in t: self.with_am += 1
    def node(self, o):     self.nodes += 1; self._tagged(o)
    def way(self, o):      self.ways  += 1; self._tagged(o)
    def relation(self, o): self.rels  += 1; self._tagged(o)

def pct(n, d): return f"{100*n//d if d else 0}%"

def main(which):
    skip = {"combined.osm.pbf", "with_osm.osm.pbf"}
    files = [f for f in sorted(glob.glob(os.path.join(OSM, "*.osm.pbf")))
             if os.path.basename(f) not in skip and not f.endswith(".sorted.osm.pbf")
             and os.path.basename(f).split("-")[0] in which]
    rows = []
    for f in files:
        name = os.path.basename(f).replace(".osm.pbf", "")
        s = Stats(); s.apply_file(f)
        row = {"source": name, "nodes": s.nodes, "ways": s.ways, "relations": s.rels,
               "features": s.feat, "with_name": s.with_name,
               "name:en %": pct(s.with_en, s.feat), "name:am %": pct(s.with_am, s.feat)}
        rows.append(row)
        print(f"{name:11} nodes={s.nodes:<8} ways={s.ways:<7} rels={s.rels:<5} "
              f"features={s.feat:<8} name={pct(s.with_name,s.feat):<5} "
              f"en={pct(s.with_en,s.feat):<5} am={pct(s.with_am,s.feat):<5}")
    if rows:
        with open(os.path.join(HERE, "report.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        tot = {k: sum(r[k] for r in rows) for k in ("nodes", "ways", "relations", "features")}
        print(f"\nTOTAL nodes={tot['nodes']:,} ways={tot['ways']:,} relations={tot['relations']:,} "
              f"features={tot['features']:,}")
        print("report.csv written.")

if __name__ == "__main__":
    which = sys.argv[1:] or ["cbebank", "fayda", "edas", "ethionsdi"]
    main(which)
