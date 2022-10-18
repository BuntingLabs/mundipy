
from mundipy.mundi import Mundi, Map

def test_coffeeshops():
    mundi = Mundi(Map({
        'neighborhoods': 'tests/fixtures/los-angeles.geojson',
        'coffeeshops': 'tests/fixtures/la_coffeeshops.geojson',
        }), 'coffeeshops', units='feet')

    def process(Q, coffeeshop, neighborhoods):
        coffeeshop['neighborhood_name'] = 'none'

        for neighborhood in neighborhoods:
            if coffeeshop.intersects(neighborhood):
                coffeeshop['neighborhood_name'] = neighborhood['name']

        return coffeeshop.features

    outs = mundi.q(process)

    assert len(outs) == 12
    assert len(outs[outs['neighborhood_name'] == 'North Hollywood']) == 2
    assert len(outs[outs['name'] == 'Philz Coffee']) == 1
