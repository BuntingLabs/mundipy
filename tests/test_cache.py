
from mundipy.pcs import choose_pcs
from mundipy.cache import spatial_cache_footprint, union_spatial_cache
from shapely.geometry import box, Point
import random

def test_cache_choose():
    bbox = (-118.843683, 34.052235, -118.143683, 34.552235)
    polygon = box(*bbox, ccw=True)

    res_first = choose_pcs(polygon)
    res_second = choose_pcs(polygon)

    assert res_first == res_second

def test_cache_none():
    @spatial_cache_footprint
    def fn(arg):
        return None

    assert fn(box(-118.843683, 34.052235, -118.143683, 34.552235)) == None

# TODO put test_union_cache here
