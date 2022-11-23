
import re
import pytest
from mundipy.mundi import Mundi, Map
from mundipy.utils import plot

def test_mundi_q():
    mundi = Mundi(Map({
        'points': 'tests/fixtures/points.geojson',
        'polygon': 'tests/fixtures/polygon.geojson',
        }), 'points', units='feet')

    def process(point, polygon):
        larger = polygon.intersects(point)

        print('should capture')

        return point

    outs = mundi.q(process)
    feats = outs['features']

    assert len(feats) == 3
    assert feats[0]['properties']['_stdout'] == 'should capture\n'
    assert feats[0]['properties']['_id'] == 0

def test_mundi_q_n():
    mundi = Mundi(Map({
        'points': 'tests/fixtures/points.geojson',
        }), 'points', units='feet')

    def process(point):
        return point

    outs = mundi.q(process, n_start=1, n_end=2)

    assert len(outs['features']) == 1

def test_mundi_q_badcolumn():
    mundi = Mundi(Map({
        'points': 'tests/fixtures/points.geojson',
        'polygon': 'tests/fixtures/polygon.geojson',
        }), 'points', units='feet')

    def process_points(center, pointss):
        pass
    def process_polygon(center, polyg0n):
        pass
    def process_nothing(center, n1192823):
        pass

    with pytest.raises(TypeError, match=re.escape('mundi process() function requests dataset \'pointss\', but no dataset was defined on Mundi')):
        mundi.q(process_points)
    with pytest.raises(TypeError, match=re.escape('mundi process() function requests dataset \'polyg0n\', but no dataset was defined on Mundi')):
        mundi.q(process_polygon)
    with pytest.raises(TypeError, match=re.escape('mundi process() function requests dataset \'n1192823\', but no dataset was defined on Mundi')):
        mundi.q(process_nothing)

def test_mundi_q_inspect():
    mundi = Mundi(Map({
        'points': 'tests/fixtures/points.geojson',
        'polygon': 'tests/fixtures/polygon.geojson',
        }), 'points', units='feet')

    def correct_dataset(point, points, polygon):
        return point
    def not_in_mundi(point, not_in_mundi):
        return point

    mundi.q(correct_dataset)

    with pytest.raises(TypeError, match=re.escape('mundi process() function requests dataset \'not_in_mundi\', but no dataset was defined on Mundi')):
        mundi.q(not_in_mundi)

def test_mundi_crs():
    mundi = Mundi(Map({
        'points': 'tests/fixtures/points.geojson',
        'texas': 'tests/fixtures/texas_epsg_2844.geojson',
        }), 'points', units='feet')

    def process_points(point, texas):
        ints = texas.intersects(point)
        if len(ints) > 0:
            plot(ints, 'texas')

        return point

    mundi.plot(process_points)

def test_no_pygeos():
    mundi = Mundi(Map({
        'neighborhoods': 'tests/fixtures/los-angeles.geojson',
        }), 'neighborhoods', units='feet')

    def process_points(neighborhood):
        plot(neighborhood, 'neighborhood')

        return neighborhood

    mundi.plot(process_points)
