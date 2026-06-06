#!/usr/bin/env python3
"""CBE ATMs -> OSM tags. Single layer (atm). amenity=atm at a bank-operated machine."""
from lib import names

# in-scope normalized layers for this source (geojson stem -> nothing extra needed)
LAYERS = ["atm"]

OPERATOR_EN = "Commercial Bank of Ethiopia"
OPERATOR_AM = "የኢትዮጵያ ንግድ ባንክ"

def tags(p, layer=None):
    t = {
        "amenity": "atm",
        "operator": OPERATOR_EN,
        "operator:en": OPERATOR_EN,
        "operator:am": OPERATOR_AM,
        "brand": OPERATOR_EN,
        "network": OPERATOR_EN,
        # The CBE source rounds coordinates to ~0.01 deg (~1 km) and stacks many ATMs on one
        # point, so positions are unreliable. Flag every ATM for verification before OSM upload.
        "fixme": "Approximate location (~1 km): source coordinates are rounded and many ATMs "
                 "share a point. Verify and reposition before any OSM use.",
        "source:position": "approximate",
    }
    if p.get("terminal_id"):
        t["ref"] = p["terminal_id"]
    nm = (p.get("name") or "").strip()
    if nm:
        am, _src = names.translate_am(nm)
        t.update(names.names_for(en=nm, am=am, primary="en"))   # ATM labels are English on the ground
    if p.get("city"):
        t["addr:city"] = p["city"]
    if p.get("telephone"):
        t["phone"] = p["telephone"]
    return t
