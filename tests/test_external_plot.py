import pytest
import re
import json

from mundipy.mundi import Mundi, Map
from mundipy.utils import plot
from mundipy.geometry import enrich_geom
from shapely.geometry import Point, LineString

def test_plot_context():
    mundi = Mundi(Map({
        'coffeeshops': 'tests/fixtures/la_coffeeshops.geojson',
        }), 'coffeeshops', units='meters')

    def process(coffeeshop):
        plot(coffeeshop, 'coffeeshop')

        return coffeeshop.features

    outs = mundi.plot(process)
    assert isinstance(outs, str)

    plotted = json.loads(outs)

    assert len(plotted['geometries']) == 1
    assert plotted['geometries'][0]['coordinates'] == [-118.3443726, 34.1689253]
    assert plotted['geometries'][0]['type'] == 'Point'

def test_plot_point():
    mundi = Mundi(Map({
        'coffeeshops': 'tests/fixtures/la_coffeeshops.geojson',
        }), 'coffeeshops', units='meters')

    def process(coffeeshop):
        plot(enrich_geom(Point(1, 1), dict()), 'coffeeshop')
        plot(enrich_geom(LineString([[0, 0], [1, 1], [2, 2]]), dict()), 'line')

        return coffeeshop.features

    outs = mundi.plot(process)

    plotted = json.loads(outs)

    assert len(plotted['geometries']) == 2

def test_plot_nocontext():
    with pytest.raises(TypeError, match=re.escape('mundipy.utils.plot() called outside of process fn')):
        plot(Point(0, 0), 'point')
