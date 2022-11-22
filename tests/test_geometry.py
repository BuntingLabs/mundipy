
from mundipy.layer import Dataset

def test_geometry():
    df = Dataset('tests/fixtures/polygon.geojson')

    geom = list(df)

    assert len(geom) == 1
    assert geom[0].area > 800 and geom[0].area < 900
    assert geom[0]['name'] == 'example_property'

    geom[0]['name'] = 'new_name'
    assert geom[0]['name'] == 'new_name'

def test_geometry_from_row():
    df = Dataset('tests/fixtures/polygon.geojson')

    geom = list(df)[0]
    assert geom.area > 800 and geom.area < 900
    assert geom['name'] == 'example_property'

    geom['name'] = 'new_name'
    assert geom['name'] == 'new_name'
