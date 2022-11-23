
from mundipy.mundi import Mundi, Map

def test_coffeeshops():
    mundi = Mundi(Map({
        'neighborhoods': 'tests/fixtures/los-angeles.geojson',
        'coffeeshops': 'tests/fixtures/la_coffeeshops.geojson',
        }), 'coffeeshops', units='feet')

    def process(coffeeshop, neighborhoods):
        coffeeshop['neighborhood_name'] = 'none'

        for neighborhood in neighborhoods:
            if coffeeshop.intersects(neighborhood):
                coffeeshop['neighborhood_name'] = neighborhood['name']

        nearest_neighborhood = neighborhoods.nearest(coffeeshop)
        assert isinstance(nearest_neighborhood['name'], str)

        return coffeeshop

    outs = mundi.q(process)
    feats = outs['features']

    assert len(feats) == 12
    assert len([ f for f in feats if f['properties']['neighborhood_name'] == 'North Hollywood' ]) == 2
    assert len([ f for f in feats if f['properties']['name'] == 'Philz Coffee' ]) == 1
