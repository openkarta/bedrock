#!/usr/bin/env python3
"""EthioSDI (GeoNode/GeoServer) layers -> OSM tags.

69 heterogeneous layers. Explicit rules cover the high-value ones; everything else falls back
to a keyword heuristic on the layer name, and is SKIPPED (returns None) when no confident tag
can be inferred — better to drop than mis-tag. Names are picked from the first plausible field
and machine-translated to Amharic.
"""
from lib import names

LAYERS = None     # None => to_osm.py processes every normalized layer; tags() skips with None

# name fields seen across EthioSDI layers, in priority order; "Aeria Name" is a junk placeholder
_NAME_FIELDS = ["name", "name_en", "name_eng", "town_name", "sc_name", "cn_name",
                "feature_or", "woredaname", "woreda_nam", "place_name"]
_JUNK = {"aeria name", "area name", "0", "null", "none"}

def _name(p):
    for f in _NAME_FIELDS:
        v = (p.get(f) or "").strip()
        if v and v.lower() not in _JUNK:
            return v
    return ""

def _with_name(p, base):
    en = _name(p)
    if en:
        am, _ = names.translate_am(en)
        base.update(names.names_for(en=en, am=am, primary="en"))
    return base

# 109_all_place_markes_final.type values are already OSM-ish -> route to the right key
_PLACE_AMENITY = {"bank", "restaurant", "cafe", "pharmacy", "fuel", "hospital", "clinic",
                  "school", "police", "marketplace", "place_of_worship", "fast_food",
                  "bar", "fuel", "cinema", "library", "college", "university", "post_office",
                  "bus_station", "townhall", "courthouse", "fire_station", "atm"}
_PLACE_SHOP = {"store", "supermarket", "bakery", "kiosk", "convenience", "mall", "hairdresser"}
_PLACE_HW = {"bus_stop", "crossing", "traffic_signals"}
_PLACE_TOUR = {"hotel", "guest_house", "motel", "attraction", "museum"}

def _place_mark(p):
    typ = (p.get("type") or "").strip().lower().replace(" ", "_")
    if not typ or typ == "low_income_block":
        return None
    if typ in _PLACE_AMENITY:  base = {"amenity": typ}
    elif typ in _PLACE_SHOP:   base = {"shop": typ}
    elif typ in _PLACE_HW:     base = {"highway": typ}
    elif typ in _PLACE_TOUR:   base = {"tourism": typ}
    elif typ == "apartment":   base = {"building": "apartments"}
    elif typ == "tower":       base = {"man_made": "tower"}
    else:                      return None
    return _with_name(p, base)

_CULTURAL = {"police post": {"amenity": "police"}, "police station": {"amenity": "police"},
             "market center": {"amenity": "marketplace"}, "hotel": {"tourism": "hotel"},
             "bank": {"amenity": "bank"}}

def _admin(p, level):
    base = {"boundary": "administrative", "admin_level": str(level)}
    return _with_name(p, base)

# explicit per-layer slug rules
def _rule(slug, p):
    if slug == "58_road_2":
        hw = (p.get("highway") or "").strip()
        return _with_name(p, {"highway": hw}) if hw else None
    if slug == "105_eth_roads":
        return _with_name(p, {"highway": "road"})
    if slug in ("x_rural_schools", "x_urban_schools"):
        return _with_name(p, {"amenity": "school"})
    if slug == "80_eth_woreda_2013":
        return _admin(p, 6)
    if slug == "126_addis_ababa_woreda_1":
        return _admin(p, 8)
    if slug == "x_gazetteer_50k_data":
        return _with_name(p, {"place": "locality"})
    if slug == "109_all_place_markes_final":
        return _place_mark(p)
    if slug == "x_cultural_features":
        base = dict(_CULTURAL.get((p.get("cn_type_1") or "").strip().lower()) or {})
        return _with_name(p, base) if base else None
    if slug in ("51_major_cities1", "90_ethio_towns"):
        return _with_name(p, {"place": "town"})
    return False    # no explicit rule

def _heuristic(slug, p):
    s = slug.lower()
    if "school" in s:                              return _with_name(p, {"amenity": "school"})
    if "hospital" in s:                            return _with_name(p, {"amenity": "hospital"})
    if "health" in s or "clinic" in s:             return _with_name(p, {"amenity": "clinic"})
    if "pharmac" in s:                             return _with_name(p, {"amenity": "pharmacy"})
    if "police" in s:                              return _with_name(p, {"amenity": "police"})
    if "market" in s:                              return _with_name(p, {"amenity": "marketplace"})
    if "woreda" in s:                              return _admin(p, 6)
    if "zone" in s:                                return _admin(p, 5)
    if "region" in s or "_adm1" in s:              return _admin(p, 4)
    if "kebele" in s:                              return _admin(p, 7)
    if "road" in s or "street" in s or "_rd" in s: return _with_name(p, {"highway": "road"})
    if "town" in s or "cities" in s or "city" in s or "place" in s: return _with_name(p, {"place": "town"})
    return None     # skip

def tags(p, layer=None):
    r = _rule(layer, p)
    if r is not False:        # explicit rule fired (may be a tag dict or None=skip)
        return r
    return _heuristic(layer, p)
