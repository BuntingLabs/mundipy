# mundi.py

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
