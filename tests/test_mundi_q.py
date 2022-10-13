
import re
import pytest
from mundipy.mundi import Mundi, Map

def test_mundi_q():
    mundi = Mundi(Map({
        'points': 'tests/fixtures/points.geojson',
        'polygon': 'tests/fixtures/polygon.geojson',
        }), 'points', units='feet')

    def process(Q):
        larger = Q('polygon').intersects()

        return {
            'center': larger
        }

    outs = mundi.q(process)

    assert len(outs) == 3

def test_mundi_q_n():
    mundi = Mundi(Map({
        'points': 'tests/fixtures/points.geojson',
        }), 'points', units='feet')

    def process(Q):
        return {
            'center': 3.14
        }

    outs = mundi.q(process, n_start=1, n_end=2)

    assert len(outs) == 1

def test_mundi_q_badcolumn():
    mundi = Mundi(Map({
        'points': 'tests/fixtures/points.geojson',
        'polygon': 'tests/fixtures/polygon.geojson',
        }), 'points', units='feet')

    def process_points(Q):
        Q('pointss')
    def process_polygon(Q):
        Q('polyg0n')
    def process_nothing(Q):
        Q('1192823')

    with pytest.raises(TypeError, match=re.escape('Unknown dataset name pointss was passed to Q(), did you mean points?')):
        mundi.q(process_points)
    with pytest.raises(TypeError, match=re.escape('Unknown dataset name polyg0n was passed to Q(), did you mean points?')):
        mundi.q(process_polygon)
    with pytest.raises(TypeError, match=re.escape('Unknown dataset name 1192823 was passed to Q()')):
        mundi.q(process_nothing)

def test_mundi_q_inspect():
    mundi = Mundi(Map({
        'points': 'tests/fixtures/points.geojson',
        'polygon': 'tests/fixtures/polygon.geojson',
        }), 'points', units='feet')

    def correct_dataset(Q, points, polygon):
        return dict()
    def not_in_mundi(Q, not_in_mundi):
        return dict()

    mundi.q(correct_dataset)

    with pytest.raises(TypeError, match=re.escape('mundi process() function requests dataset \'not_in_mundi\', but no dataset was defined on Mundi')):
        mundi.q(not_in_mundi)

def test_mundi_crs():
    mundi = Mundi(Map({
        'points': 'tests/fixtures/points.geojson',
        'texas': 'tests/fixtures/texas_epsg_2844.geojson',
        }), 'points', units='feet')

    def process_points(Q):
        Q.plot(Q('texas').intersects(), 'texas')

        return dict()

    mundi.plot(process_points, output_type='geojson')

def test_no_pygeos():
    mundi = Mundi(Map({
        'neighborhoods': 'tests/fixtures/los-angeles.geojson',
        }), 'neighborhoods', units='feet')

    def process_points(Q):
        Q.plot(Q(), 'neighborhood')

        return dict()

    mundi.plot(process_points, output_type='geojson')
