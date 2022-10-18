
import geopandas as gpd
from mundipy.geometry import from_dataframe, from_row_series

def test_geometry():
    gdf = gpd.read_file('tests/fixtures/polygon.geojson')

    geom = from_dataframe(gdf)

    assert len(geom) == 1
    assert geom[0].area > 800 and geom[0].area < 900
    assert geom[0]['name'] == 'example_property'

    geom[0]['name'] = 'new_name'
    assert geom[0]['name'] == 'new_name'

def test_geometry_from_row():
    gdf = gpd.read_file('tests/fixtures/polygon.geojson')

    geom = from_row_series(gdf.iloc[0])
    assert geom.area > 800 and geom.area < 900
    assert geom['name'] == 'example_property'

    geom['name'] = 'new_name'
    assert geom['name'] == 'new_name'
