# [![mundi.py](docs/logo/light.svg)](https://docs.mundi.ai)

[![PyPI version](https://badge.fury.io/py/mundipy.svg)](https://pypi.org/project/mundipy/) ![GitHub issues](https://img.shields.io/github/issues/BuntingLabs/mundipy) ![PyPI - License](https://img.shields.io/pypi/l/mundipy)

mundipy is a Python framework for spatial data manipulation. Built on top of
[geopandas](https://geopandas.org/en/stable/), [GDAL](https://gdal.org/),
and [shapely](https://shapely.readthedocs.io/en/stable/manual.html), mundi.py
provides a useful abstraction to eliminate the hassles of spatial data.

# Features

- [Spatial caching](https://docs.mundi.ai/spatial-lru-cache)
- [Automatically projection management](https://docs.mundi.ai/projected-coordinate-systems)
- [Layer management](https://docs.mundi.ai/layer-management)
- Automatic spatial indexing for lookups
- Automatic spatial joins

# Project Roadmap

- Jupyter notebook native (\_repr\_html\_) that doesn't explode with massive data
- Nearest neighbor/distance queries
- Dissolving into h3/s2

## License

Mundi.py is MIT licensed.
