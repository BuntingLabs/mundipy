import pytest
import re

from mundipy.mundi import Mundi, Map
from mundipy.utils import plot
from shapely.geometry import Point

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

def test_plot_nocontext():
    with pytest.raises(TypeError, match=re.escape('mundipy.utils.plot() called outside of process fn')):
        plot(Point(0, 0), 'point')
