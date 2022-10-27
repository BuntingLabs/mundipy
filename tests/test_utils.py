import math

from mundipy.utils import sanitize_geo

def test_geometry_from_row():
    assert sanitize_geo({ 'x': math.nan })['x'] == None
