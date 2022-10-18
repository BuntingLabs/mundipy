
import geopandas as gpd
from mundipy.geometry import from_dataframe

def test_geometry():
    gdf = gpd.read_file('tests/fixtures/polygon.geojson')

    geom = from_dataframe(gdf)

    assert len(geom) == 1
    assert geom[0].area > 800 and geom[0].area < 900
    assert geom[0]['name'] == 'example_property'

    geom[0]['name'] = 'new_name'
    assert geom[0]['name'] == 'new_name'
