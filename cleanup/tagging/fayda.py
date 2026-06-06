#!/usr/bin/env python3
"""Fayda (National ID) registration centers -> OSM tags.

Each point is a government ID-registration service hosted at a venue (telecom shop, bank,
post office, tax/MoR office, DARS, etc.). Tagged office=government + government=register_office,
with the venue kept in fayda:venue. Names are bilingual in the source -> split to name:en/name:am.
"""
from lib import names

LAYERS = ["tele", "bank", "crrsa", "post_office", "dars", "mor", "palace_parking"]

def group(layer, tags):
    """Keep the per-venue split in the output -> fayda-<venue>.osm.pbf."""
    return layer

MIN_DECIMALS = 5   # drop rounded/low-precision source points

def _decimals(v):
    s = repr(float(v))
    if "e" in s or "E" in s:        # tiny/huge -> treat as no precision
        return 0
    return len(s.split(".")[1]) if "." in s else 0

def accept(geom, props, layer):
    """Reject low-precision points: keep only if BOTH lon and lat have >= MIN_DECIMALS decimal
    places. Some Fayda source coordinates are rounded (~<=3 decimals, ~100 m+); those are
    dropped. A venue left with no points produces no file (e.g. palace_parking)."""
    if not geom or geom.get("type") != "Point":
        return True
    lon, lat = geom["coordinates"][0], geom["coordinates"][1]
    return min(_decimals(lon), _decimals(lat)) >= MIN_DECIMALS

OPERATOR_EN = "National ID Program (Fayda)"
OPERATOR_AM = "ብሔራዊ መታወቂያ ፕሮግራም"

def tags(p, layer=None):
    t = {
        "office": "government",
        "government": "register_office",
        "operator": OPERATOR_EN,
        "operator:am": OPERATOR_AM,
        "description": "Fayda Digital ID registration center",
    }
    parts = names.split_bilingual(p.get("name") or "")
    en, am = parts["en"], parts["am"]
    if en and not am:                      # only English present -> machine Amharic
        am, _ = names.translate_am(en)
    t.update(names.names_for(en=en, am=am, primary="en"))
    venue = (p.get("type") or layer or "").strip()
    if venue:
        t["fayda:venue"] = venue
    if (p.get("status") or "").strip().lower() == "active":
        t["operational_status"] = "operational"
    return t
