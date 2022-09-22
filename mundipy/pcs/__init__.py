"""
mundipy.pcs automatically chooses a projected coordinate reference system
that wholly contains a given bounding box.

This is especially useful for performing operations (like distance or area)
that geographic coordinate systems are unreliable for.

The most common way this library is used is when performing operations
on unknown objects in <Latitude, Longitude> format (WGS84) with the need
to do geometric operations like distance, area, or buffering.
"""

import os

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
import fiona

CRS_DATASET = os.path.join(os.path.dirname(__file__), 'crs_simple.fgb')

def choose_pcs(box, units='meters'):
	"""Choose a projected coordinate system from a shapely geometry with specified units for the axes."""

	if not isinstance(box, BaseGeometry):
		raise TypeError('box passed to projectedcrs.choose_pcs() is not a shapely BaseGeometry, instead got \'%s\'' % type(box))
	if units not in ['feet', 'meters']:
		raise TypeError('units passed to projectedcrs.choose_pcs() is neither feet nor meters')

	suggestions = suggest_pcs(box, units=units)
	if len(suggestions) == 0:
		raise ValueError('choose_pcs(box) had zero suggested CRS (hint: is your box in WGS84 format?)')

	return suggestions[0]

def suggest_pcs(box, units='meters', n=3):
	"""Suggest multiple projected coordinate systems from a shapely geometry with specified units for the axes."""

	if not isinstance(box, BaseGeometry):
		raise TypeError('box passed to projectedcrs.choose_pcs() is not a shapely BaseGeometry, instead got \'%s\'' % type(box))
	if units not in ['feet', 'meters']:
		raise TypeError('units passed to projectedcrs.suggest_pcs() is neither feet nor meters')

	with fiona.open(CRS_DATASET, 'r') as epsg:
		intersects_box = [geo for i, geo in epsg.items(bbox=box.bounds) if geo['geometry'] is not None]

		# filter for proprety
		has_unit = filter(lambda geo: geo['properties']['axis_unit'] == units, intersects_box)

		# filter for where items contain box
		contains_box = filter(lambda geo: shape(geo['geometry']).buffer(0).contains(box), has_unit)

		# sort by area
		satisfactory = list(map(transform_epsg, sorted(contains_box, key=lambda geo: shape(geo['geometry']).area)))

		return satisfactory[:n]

def transform_epsg(geojson):
	return {
		'name': geojson['properties']['name'],
		'epsg': geojson['properties']['EPSG'],
		'crs': 'EPSG:%d' % geojson['properties']['EPSG'],
		'units': geojson['properties']['axis_unit']
	}
