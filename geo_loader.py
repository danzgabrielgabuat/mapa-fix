"""Load GeoJSON and TopoJSON reference files into a GeoDataFrame."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any

import geopandas as gpd
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry


def load_geodata(uploaded_file) -> gpd.GeoDataFrame:
    """
    Read a Streamlit UploadedFile, path, or file-like object as GeoJSON or TopoJSON.

    GeoPandas can read many TopoJSON files, but some topologies fail or silently
    drop properties. If the JSON root is a Topology object, decode it explicitly.
    """
    raw, filename = _read_bytes(uploaded_file)

    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _read_with_geopandas(raw, filename)

    if isinstance(data, dict) and data.get("type") == "Topology":
        return topojson_to_gdf(data)

    return _read_with_geopandas(raw, filename)


def _read_bytes(uploaded_file) -> tuple[bytes, str]:
    filename = getattr(uploaded_file, "name", "reference.json")
    if hasattr(uploaded_file, "getbuffer"):
        uploaded_file.seek(0)
        return uploaded_file.getbuffer().tobytes(), filename
    if hasattr(uploaded_file, "read"):
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        data = uploaded_file.read()
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        if isinstance(data, str):
            data = data.encode("utf-8")
        return data, filename
    with open(uploaded_file, "rb") as handle:
        return handle.read(), str(uploaded_file)


def _read_with_geopandas(raw: bytes, filename: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(BytesIO(raw))
    if gdf.empty:
        raise ValueError(f"No features were read from {filename}.")
    return gdf


def topojson_to_gdf(topology: dict[str, Any]) -> gpd.GeoDataFrame:
    decoded_arcs = _decode_arcs(topology.get("arcs", []), topology.get("transform"))
    features = []
    objects = topology.get("objects") or {}
    if not objects:
        raise ValueError("TopoJSON file has no objects to convert.")

    for object_name, obj in objects.items():
        for feature in _object_to_features(obj, decoded_arcs, object_name):
            features.append(feature)

    if not features:
        raise ValueError("TopoJSON file did not contain any convertible geometries.")

    return gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")


def _decode_arcs(arcs: list, transform: dict | None) -> list[list[list[float]]]:
    scale = (1.0, 1.0)
    translate = (0.0, 0.0)
    if transform:
        scale = tuple(transform.get("scale", scale))
        translate = tuple(transform.get("translate", translate))

    decoded = []
    for arc in arcs:
        x = y = 0.0
        line = []
        for point in arc:
            dx, dy = point[:2]
            x += dx
            y += dy
            line.append([x * scale[0] + translate[0], y * scale[1] + translate[1]])
        decoded.append(line)
    return decoded


def _arc_coordinates(decoded_arcs: list[list[list[float]]], index: int) -> list[list[float]]:
    if index >= 0:
        return decoded_arcs[index]
    reversed_arc = decoded_arcs[~index]
    return list(reversed(reversed_arc))


def _ring_from_arcs(decoded_arcs: list[list[list[float]]], arc_indexes: list[int]) -> list[list[float]]:
    ring = []
    for index in arc_indexes:
        coords = _arc_coordinates(decoded_arcs, index)
        if not coords:
            continue
        if ring and ring[-1] == coords[0]:
            ring.extend(coords[1:])
        else:
            ring.extend(coords)
    return ring


def _geometry_from_topo(geom: dict[str, Any], decoded_arcs: list[list[list[float]]]) -> dict[str, Any] | None:
    geom_type = geom.get("type")
    if geom_type is None or geom_type == "GeometryCollection":
        return None
    if geom_type == "Point":
        return {"type": "Point", "coordinates": geom.get("coordinates")}
    if geom_type == "MultiPoint":
        return {"type": "MultiPoint", "coordinates": geom.get("coordinates")}
    if "arcs" not in geom:
        return None

    arcs = geom["arcs"]
    if geom_type == "LineString":
        coordinates = _ring_from_arcs(decoded_arcs, arcs)
        return {"type": "LineString", "coordinates": coordinates}
    if geom_type == "MultiLineString":
        coordinates = [_ring_from_arcs(decoded_arcs, part) for part in arcs]
        return {"type": "MultiLineString", "coordinates": coordinates}
    if geom_type == "Polygon":
        coordinates = [_ring_from_arcs(decoded_arcs, ring) for ring in arcs]
        return {"type": "Polygon", "coordinates": coordinates}
    if geom_type == "MultiPolygon":
        coordinates = [
            [_ring_from_arcs(decoded_arcs, ring) for ring in polygon] for polygon in arcs
        ]
        return {"type": "MultiPolygon", "coordinates": coordinates}
    return None


def _valid_geojson_geometry(geojson_geom: dict[str, Any]) -> dict[str, Any] | None:
    try:
        geom: BaseGeometry = shape(geojson_geom)
    except Exception:
        return None
    if geom.is_empty:
        return None
    if not geom.is_valid:
        geom = geom.buffer(0)
        if geom.is_empty:
            return None
    return mapping(geom)


def _object_to_features(obj: dict[str, Any], decoded_arcs: list, object_name: str) -> list[dict]:
    features = []
    obj_type = obj.get("type")
    geometries: list[dict[str, Any]]
    if obj_type == "GeometryCollection":
        geometries = obj.get("geometries") or []
    else:
        geometries = [obj]

    for geom in geometries:
        if geom.get("type") == "GeometryCollection":
            features.extend(_object_to_features(geom, decoded_arcs, object_name))
            continue
        geojson_geom = _geometry_from_topo(geom, decoded_arcs)
        if not geojson_geom:
            continue
        valid_geom = _valid_geojson_geometry(geojson_geom)
        if not valid_geom:
            continue
        properties = dict(geom.get("properties") or {})
        if "id" in geom and "id" not in properties:
            properties["id"] = geom["id"]
        properties.setdefault("topojson_object", object_name)
        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": valid_geom,
            }
        )
    return features
