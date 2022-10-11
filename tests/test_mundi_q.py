
from mundipy.mundi import Mundi, Map

def test_mundi_q():
    mundi = Mundi(Map({
        'points': 'tests/fixtures/points.geojson',
        'polygon': 'tests/fixtures/polygon.geojson',
        }), 'points', units='feet')

    def process(Q):
        # Q('points')
        larger = Q('polygon').intersects()

        return {
            'center': larger
        }

    outs = mundi.q(process)

    assert len(outs) == 3
