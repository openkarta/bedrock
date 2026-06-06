#!/usr/bin/env python3
"""Turn GeoJSON geometries + OSM tag dicts into a .osm.pbf via pyosmium.

  Point/MultiPoint     -> node(s)
  LineString/MultiLine -> way(s)
  Polygon (1 ring)     -> closed way (area)
  Polygon (with holes) / MultiPolygon -> type=multipolygon relation (outer/inner ways)

IDs are NEGATIVE (new, never-uploaded features) in a per-source disjoint block, so several
sources can later be merged without id collisions. Nodes are streamed to the writer as they
are created; ways/relations are buffered and flushed afterwards, so the file is ordered
nodes -> ways -> relations and memory stays bounded (only ways/relations are held).
"""
import osmium
from osmium.osm.mutable import Node, Way, Relation

BLOCK = 2_000_000_000      # id space reserved per source (per primitive type)

class OsmBuilder:
    def __init__(self, path, source_block=0):
        self.w = osmium.SimpleWriter(path)
        self.off = source_block * BLOCK
        self._n = self._wy = self._r = 0
        self._ways, self._rels = [], []
        self.counts = {"node": 0, "way": 0, "relation": 0}

    # --- id allocators (negative, disjoint per source) ---
    def _nid(self): self._n += 1;  return -(self.off + self._n)
    def _wid(self): self._wy += 1; return -(self.off + self._wy)
    def _rid(self): self._r += 1;  return -(self.off + self._r)

    @staticmethod
    def _tags(d):
        return {str(k): str(v) for k, v in (d or {}).items()
                if v is not None and str(v).strip() != ""}

    def _node(self, lon, lat, tags=None):
        nid = self._nid()
        self.w.add_node(Node(id=nid, location=(float(lon), float(lat)), tags=self._tags(tags)))
        self.counts["node"] += 1
        return nid

    def _way_from_ring(self, ring, tags=None, closed=True):
        """Create nodes for a ring/line and buffer a way; returns way id."""
        coords = ring[:-1] if (closed and len(ring) > 1 and ring[0] == ring[-1]) else ring
        refs = [self._node(lon, lat) for lon, lat in coords]
        if closed and refs:
            refs.append(refs[0])               # close the ring on the same node
        wid = self._wid()
        self._ways.append(Way(id=wid, nodes=refs, tags=self._tags(tags)))
        self.counts["way"] += 1
        return wid

    # --- public geometry entry points (tags applied to the feature primitive) ---
    def add_point(self, lon, lat, tags):
        self._node(lon, lat, tags)

    def add_line(self, coords, tags):
        refs = [self._node(lon, lat) for lon, lat in coords]
        wid = self._wid()
        self._ways.append(Way(id=wid, nodes=refs, tags=self._tags(tags)))
        self.counts["way"] += 1

    def add_polygon(self, rings, tags):
        """rings = [outer, hole1, ...] (each a coord list). 1 ring -> closed way; else relation."""
        if len(rings) == 1:
            self._way_from_ring(rings[0], tags=tags, closed=True)
        else:
            self._multipolygon([rings], tags)

    def add_multipolygon(self, polygons, tags):
        """polygons = [[outer, *holes], ...]. Always a multipolygon relation."""
        if len(polygons) == 1 and len(polygons[0]) == 1:
            self._way_from_ring(polygons[0][0], tags=tags, closed=True)
        else:
            self._multipolygon(polygons, tags)

    def _multipolygon(self, polygons, tags):
        members = []
        for poly in polygons:
            for i, ring in enumerate(poly):
                wid = self._way_from_ring(ring, tags=None, closed=True)
                members.append(("w", wid, "outer" if i == 0 else "inner"))
        rid = self._rid()
        t = self._tags(tags); t["type"] = "multipolygon"
        self._rels.append(Relation(id=rid, members=members, tags=t))
        self.counts["relation"] += 1

    def flush(self):
        for wobj in self._ways:
            self.w.add_way(wobj)
        for robj in self._rels:
            self.w.add_relation(robj)
        self.w.close()
        return self.counts


def add_geometry(builder, geom, tags):
    """Dispatch a GeoJSON geometry dict to the right builder call."""
    if not geom:
        return
    t, c = geom.get("type"), geom.get("coordinates")
    if c is None:
        return
    if t == "Point":
        builder.add_point(c[0], c[1], tags)
    elif t == "MultiPoint":
        for p in c:
            builder.add_point(p[0], p[1], tags)
    elif t == "LineString":
        builder.add_line(c, tags)
    elif t == "MultiLineString":
        for ls in c:
            builder.add_line(ls, tags)
    elif t == "Polygon":
        builder.add_polygon(c, tags)             # c = [outer, *holes]
    elif t == "MultiPolygon":
        builder.add_multipolygon(c, tags)        # c = [[outer,*holes], ...]
