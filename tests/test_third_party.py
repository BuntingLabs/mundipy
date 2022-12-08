import pytest

from mundipy.api import isochrone
from mundipy.geometry import Point

def test_isochrone():
    with pytest.raises(ValueError, match='called without Mapbox accessToken'):
        isochrone(Point((0, 0), 'EPSG:4326', dict()), 50., 'minutes')
    with pytest.raises(TypeError, match='expects pt to be mundipy.geometry.Point'):
        isochrone(False, 30., 'meters', accessToken='test')
    with pytest.raises(TypeError, match='unknown unit "feet" passed'):
        isochrone(Point((0, 0), 'EPSG:4326', dict()), 30., 'feet', accessToken='test')
