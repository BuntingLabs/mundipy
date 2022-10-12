
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
