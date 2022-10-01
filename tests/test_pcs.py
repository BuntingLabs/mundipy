
from mundipy.pcs import choose_pcs
from shapely.geometry import box

def test_choose_pcs_bench(benchmark):
    bbox = (-118.843683, 34.052235, -118.143683, 34.552235)
    polygon = box(*bbox, ccw=True)

    def wrapper():
        return choose_pcs(polygon)

    # benchmark something
    result = benchmark(wrapper)

    assert result == {
        'name': 'NAD83 / California zone 5',
        'epsg': 26945,
        'crs': 'EPSG:26945',
        'units': 'meters'
    }

def test_choose_pcs():
    # https://gist.github.com/graydon/11198540
    assert choose_pcs(box(3.31497114423, 50.803721015, 7.09205325687, 53.5104033474, ccw=True)) == {
        'name': 'ED50 / SPBA LCC',
        'epsg': 5643,
        'crs': 'EPSG:5643',
        'units': 'meters'
    }

    assert choose_pcs(box(45.2541870461, -18.6014344215, 46.4765368996, -17.0405567359, ccw=True)) == {
        'name': 'Tananarive (Paris) / Laborde Grid',
        'epsg': 29701,
        'crs': 'EPSG:29701',
        'units': 'meters'
    }

    assert choose_pcs(box(-71.857247, 44.19699, -71.610621, 44.305476, ccw=True), units='feet') == {
        'name': 'NAD83(HARN) / New Hampshire (ftUS)',
        'epsg': 3445,
        'crs': 'EPSG:3445',
        'units': 'feet'
    }

    assert choose_pcs(box(116.383331, 39.916668, 116.783331, 39.116668, ccw=True)) == {
        'name': 'New Beijing / 3-degree Gauss-Kruger CM 117E',
        'epsg': 4796,
        'crs': 'EPSG:4796',
        'units': 'meters'
    }
