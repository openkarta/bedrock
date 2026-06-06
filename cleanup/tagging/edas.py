#!/usr/bin/env python3
"""EDAS GeoServer layers -> OSM tags, dispatched per layer.

Conventions: raw EDAS class codes are preserved on roads (edas:functional/type/structural) since
the highway mapping is provisional. The _Am/_Or city/landmark variants and parcels/aux are NOT
in LAYERS (identical Latin duplicates / not OSM-appropriate)."""
import json, os
from lib import names

_LK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lookups")
ROAD  = json.load(open(os.path.join(_LK, "edas_road_class.json"), encoding="utf-8"))
LULC  = json.load(open(os.path.join(_LK, "edas_lulc.json"), encoding="utf-8"))
FUN   = json.load(open(os.path.join(_LK, "landmark_funtype.json"), encoding="utf-8"))

# in-scope layers (geojson stems). Excludes parcels, driving_direction (aux), the coarse
# eth_aoi/bishoftu_aoi extents, and the _Am/_Or duplicate variants.
LAYERS = ["das_road_network", "road_network", "road_network111", "road_polygon_web_v7",
          "building_web_v7", "lulc_v7", "adama_lulc_wgs84_v1", "nsl_sub_city_lulc_wgs84_v1",
          "dukem_bishoftu_lulc", "cities_web_v7", "landmark_web_v7", "nh_aoi_web_v7",
          "road_signs", "sign_pole"]

# group the in-scope layers into logical themed output files -> edas-<theme>.osm.pbf
_THEME = {
    "das_road_network": "roads", "road_network": "roads", "road_network111": "roads",
    "road_polygon_web_v7": "roads",
    "building_web_v7": "buildings",
    "lulc_v7": "landuse", "adama_lulc_wgs84_v1": "landuse",
    "nsl_sub_city_lulc_wgs84_v1": "landuse", "dukem_bishoftu_lulc": "landuse",
    "cities_web_v7": "places", "nh_aoi_web_v7": "places",
    "landmark_web_v7": "pois", "road_signs": "pois", "sign_pole": "pois",
}

def group(layer, tags):
    return _THEME.get(layer, "pois")

SIGN = {"Traffic Light": {"highway": "traffic_signals"}, "Stop": {"highway": "stop"},
        "Speed Limit": {"traffic_sign": "maxspeed"}, "Height Limit": {"traffic_sign": "maxheight"},
        "Load Limit": {"traffic_sign": "maxweight"}, "No parking": {"traffic_sign": "no_parking"},
        "No Stop": {"traffic_sign": "no_stopping"}, "Bus station": {"amenity": "bus_station"},
        "Bus Station": {"amenity": "bus_station"}, "Taxi Station": {"amenity": "taxi"},
        "Bajaji Station": {"amenity": "taxi"}, "Cart Station": {"amenity": "taxi"},
        "Parking": {"amenity": "parking"}, "Square/ Roundabout": {"junction": "roundabout"},
        "Major Junction": {"junction": "yes"}}

def _code(v):
    """'2.000000000000000' -> '2'; '' -> ''."""
    s = str(v or "").strip()
    if not s:
        return ""
    try:
        return str(int(float(s)))
    except ValueError:
        return s

def _roads(p):
    t = {}
    fc = _code(p.get("functional"))
    t["highway"] = ROAD["functional"].get(fc, ROAD["_default"])
    for raw in ("functional", "type", "structural"):
        c = _code(p.get(raw))
        if c:
            t["edas:" + raw] = c
    if _code(p.get("oneway")) == "1" or str(p.get("oneway")).strip().lower() in ("yes", "true"):
        t["oneway"] = "yes"
    lc = _code(p.get("lane_count"))
    if lc and lc != "0":
        t["lanes"] = lc
    ms = _code(p.get("max_speed"))
    if ms and ms != "0":
        t["maxspeed"] = ms
    nm = (p.get("name") or "").strip()
    if nm:
        am, _ = names.translate_am(nm)
        t.update(names.names_for(en=nm, am=am, primary="en"))
    return t

def _lulc(p):
    lt = (p.get("lulc_type") or p.get("lulc") or p.get("lu_type") or p.get("class") or "").strip()
    return dict(LULC.get(lt) or {}) or None     # None -> skip unmapped

def _landmark(p):
    ft = (p.get("fun_type") or "").strip()
    t = dict(FUN.get(ft) or {})
    if not t and ft and ft.lower() != "other":
        t["edas:fun_type"] = ft               # preserve unmapped type on a named node
    en = (p.get("name_eng") or "").strip()
    am = (p.get("legal_name") or "").strip()  # native Amharic
    om = (p.get("legal_na_2") or "").strip()  # Oromo
    if en and not am:
        am, _ = names.translate_am(en)
    t.update(names.names_for(en=en, am=am, om=om, primary="am"))
    if not t.get("name") and not any(k for k in t if k not in ("edas:fun_type",)):
        return None                            # nothing useful -> skip
    return t

def _city(p):
    t = {"place": "town"}
    nm = (p.get("town_name") or p.get("name") or "").strip()
    if nm:
        am, _ = names.translate_am(nm)
        t.update(names.names_for(en=nm, am=am, primary="en"))
    if p.get("region"):
        t["is_in:region"] = p["region"]
    return t

def tags(p, layer=None):
    if layer in ("das_road_network", "road_network", "road_network111"):
        return _roads(p)
    if layer == "road_polygon_web_v7":
        return {"area:highway": "road"}
    if layer == "building_web_v7":
        t = {"building": "yes"}
        nm = (p.get("bldg_name") or "").strip()
        if nm:
            t["name:en"] = nm
        return t
    if layer in ("lulc_v7", "adama_lulc_wgs84_v1", "nsl_sub_city_lulc_wgs84_v1", "dukem_bishoftu_lulc"):
        return _lulc(p)
    if layer == "landmark_web_v7":
        return _landmark(p)
    if layer == "cities_web_v7":
        return _city(p)
    if layer == "nh_aoi_web_v7":
        t = {"place": "neighbourhood"}
        if p.get("nh_code"):
            t["ref"] = p["nh_code"]
        return t
    if layer == "road_signs":
        st = (p.get("sign_type") or "").strip()
        return dict(SIGN.get(st) or {"traffic_sign": "yes"})
    if layer == "sign_pole":
        return {"man_made": "pole"}
    return None
