# [![mundi.py](docs/logo/light.svg)](https://docs.mundi.ai)

[![PyPI version](https://badge.fury.io/py/mundipy.svg)](https://pypi.org/project/mundipy/) ![GitHub issues](https://img.shields.io/github/issues/BuntingLabs/mundipy) ![PyPI - License](https://img.shields.io/pypi/l/mundipy)

mundipy is a Python framework for spatial data manipulation. Built on top of
[geopandas](https://geopandas.org/en/stable/), [GDAL](https://gdal.org/),
and [shapely](https://shapely.readthedocs.io/en/stable/manual.html), mundi.py
provides a useful abstraction to eliminate the hassles of spatial data.

## Projected Coordinate Systems

Automatically suggests a projected coordinate system to use, given a shapely
geometry in WGS84.

This prioritizes coordinate systems that:
1. totally contain the given geometry
2. have minimal area (probably less distortion)
3. are not deprecated

```py
>>> from mundipy.pcs import choose_pcs
>>> from shapely.geometry import Point

>>> choose_pcs(Point(-118.24, 34.052), units='feet')
{
    'name': 'NAD27 / California zone VII',
    'epsg': 26799,
    'crs': 'EPSG:26799',
    'units': 'feet'
}
```

## Project Roadmap

- No projections needed: automatically chooses and selects a relevant CRS when doing operations
- Automatic spatial indexing
- Jupyter notebook native (\_repr\_html\_) that doesn't explode with massive data
- Nearest neighbor/distance queries
- Spatial joins
- Dissolving into h3/s2

## License

Mundi.py is MIT licensed.
