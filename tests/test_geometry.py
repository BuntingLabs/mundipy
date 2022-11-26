import pytest

from mundipy.layer import Dataset
from mundipy.geometry import enrich_geom
import mundipy.geometry as geom

from shapely.geometry import Polygon, MultiPolygon
from shapely import from_wkt, GEOSException

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

def test_multi_polygon():
    outer = enrich_geom(Polygon([[25.273428697681624,6.026182562140747],[26.063011790518573,-7.9853706778425675],[30.13724140836942,-8.088943835912445],[30.13782361496999,6.078309828324564],[25.273428697681624,6.026182562140747]]), dict())
    inner = enrich_geom(Polygon([[18.381743157653403,-1.3600556177262746],[18.313380419378433,-4.991685343163752],[39.81788374424539,-5.007774504721652],[39.62298421833077,-0.6253503748207265],[18.381743157653403,-1.3600556177262746]]), dict())

    subbed = outer.difference(inner)

    assert isinstance(subbed, geom.MultiPolygon)

def test_invalid_geometry_ops():
    foo = from_wkt('POLYGON((0 0, 0 1, 2 1, 2 2, 1 2, 1 0, 0 0))')
    bar = from_wkt('POLYGON((0 0, 0 1, 2 1, 2 2, 1 2, 1 0, 0 0))')

    with pytest.raises(GEOSException, match='TopologyException'):
        foo.difference(bar)

    mfoo = enrich_geom(foo, dict())
    mbar = enrich_geom(bar, dict())

    # no error
    res = mfoo.difference(mbar)
    assert res.area == 0.0
