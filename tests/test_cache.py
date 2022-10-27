
from mundipy.pcs import choose_pcs
from mundipy.cache import spatial_cache_footprint, union_spatial_cache
from shapely.geometry import box, Point
import geopandas as gpd
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


def test_union_cache():
    random.seed(a=69)

    random_df = []
    for z in range(5000):
        x, y = 80*random.random()-40, 80*random.random()-40
        random_df.append({ 'geometry': Point(x, y) })
    random_df = gpd.GeoDataFrame(data=random_df, geometry='geometry', crs='EPSG:4326')

    # make sure fn count is right
    i = 0
    @union_spatial_cache
    def fn(geom, pcs='EPSG:4326'):
        nonlocal i

        i += 1
        assert i <= 2

        return random_df[random_df.intersects(geom)]

    def uncached_fn(geom, pcs='EPSG:4326'):
        return random_df[random_df.intersects(geom)]

    assert len(uncached_fn(box(-20, -20, 20, 20))) == 1304
    assert len(uncached_fn(box(-10, -10, 10, 10))) == 346
    assert len(uncached_fn(box(-20, 0, 0, 20))) == 304
    assert len(uncached_fn(box(-20, -10, 20, 20))) == 981
    assert len(uncached_fn(box(-16, -15, 14, 15))) == 722
    assert len(uncached_fn(box(-34, -19, 24, 38))) == 2630

    assert len(fn(box(-20, -20, 20, 20))) == 1304
    assert len(fn(box(-10, -10, 10, 10))) == 346
    assert len(fn(box(-20, 0, 0, 20))) == 304
    assert len(fn(box(-20, -10, 20, 20))) == 981
    assert len(fn(box(-16, -15, 14, 15))) == 722
    assert len(fn(box(-34, -19, 24, 38))) == 2630
