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
# Note: the <5-decimal precision cleanup is now applied globally in to_osm.py (every source).

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
