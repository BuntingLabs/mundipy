import pytest
import re
import json

from mundipy.mundi import Mundi, Map
from mundipy.utils import plot
from shapely.geometry import Point, LineString

def test_plot_context():
    mundi = Mundi(Map({
        'coffeeshops': 'tests/fixtures/la_coffeeshops.geojson',
        }), 'coffeeshops', units='meters')

    def process(coffeeshop):
        plot(coffeeshop.buffer(0), 'coffeeshop')

        return coffeeshop.features

    outs = mundi.plot(process, output_type='geojson')
    # should verify output because it doesn't look right
    assert len(outs) > 2

def test_plot_point():
    mundi = Mundi(Map({
        'coffeeshops': 'tests/fixtures/la_coffeeshops.geojson',
        }), 'coffeeshops', units='meters')

    def process(coffeeshop):
        plot(Point(1, 1), 'coffeeshop')
        plot(LineString([[0, 0], [1, 1], [2, 2]]), 'line')

        return coffeeshop.features

    outs = mundi.plot(process, output_type='geojson', clip_distance=0)
    assert len(json.loads(outs)['features']) == 2

def test_plot_nocontext():
    with pytest.raises(TypeError, match=re.escape('mundipy.utils.plot() called outside of process fn')):
        plot(Point(0, 0), 'point')
