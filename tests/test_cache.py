
from mundipy.pcs import choose_pcs
from mundipy.cache import spatial_cache_footprint, union_spatial_cache
from shapely.geometry import box, Point
import geopandas as gpd

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
    @union_spatial_cache
    def fn(geom):
        # give geopandas with dataframe commensurate to geom.area
        data = []
        for i in range(int(geom.area)):
            data.append({ 'geometry': Point(0, 0) })

        return gpd.GeoDataFrame(data=data, geometry='geometry', crs='EPSG:4326')

    assert len(fn(box(-20, -20, 20, 20))) == 1600
    assert len(fn(box(-10, -10, 10, 10))) == 400
    assert len(fn(box(-20, 0, 0, 20))) == 400
    assert len(fn(box(-20, -10, 20, 20))) == 1200
    assert len(fn(box(-16, -15, 14, 15))) == 900
    assert len(fn(box(-34, -19, 24, 38))) == 3306
