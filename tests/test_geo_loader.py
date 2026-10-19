from geo_loader import topojson_to_gdf


def test_topojson_polygon_preserves_properties():
    topology = {
        "type": "Topology",
        "transform": {"scale": [1, 1], "translate": [0, 0]},
        "arcs": [[[0, 0], [0, 10], [10, 0], [0, -10], [-10, 0]]],
        "objects": {
            "lgus": {
                "type": "GeometryCollection",
                "geometries": [
                    {
                        "type": "Polygon",
                        "arcs": [[0]],
                        "properties": {"adm2_en": "Muñoz", "adm1_en": "Nueva Ecija"},
                    }
                ],
            }
        },
    }
    gdf = topojson_to_gdf(topology)
    assert len(gdf) == 1
    assert gdf.iloc[0]["adm2_en"] == "Muñoz"
    assert gdf.iloc[0]["adm1_en"] == "Nueva Ecija"
    assert gdf.geometry.iloc[0] is not None
    assert not gdf.geometry.iloc[0].is_empty
