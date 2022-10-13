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

from mundipy.cache import spatial_cache_footprint

CRS_DATASET = os.path.join(os.path.dirname(__file__), 'crs_enhanced.fgb')

class NoProjectionFoundError(Exception):
	pass

@spatial_cache_footprint
def choose_pcs(box, units='meters'):
	"""Choose a projected coordinate system from a shapely geometry with specified units for the axes."""

	if not isinstance(box, BaseGeometry):
		raise TypeError('box passed to projectedcrs.choose_pcs() is not a shapely BaseGeometry, instead got \'%s\'' % type(box))
	if units not in ['feet', 'meters']:
		raise TypeError('units passed to projectedcrs.choose_pcs() is neither feet nor meters')

	with fiona.open(CRS_DATASET, 'r') as epsg:
		intersects_box = epsg.values(bbox=box.bounds)

		# filter for proprety
		has_unit = filter(lambda geo: geo['geometry'] is not None and geo['properties']['axis_unit'] == units, intersects_box)

		# sort by area
		by_area = sorted(has_unit, key=lambda geo: geo['properties']['area'])

		# incrementally make list of suggestions, adding if contains
		suggestions = []

		for potential_pcs in by_area:
			geo = shape(potential_pcs['geometry']).buffer(0)
			if not geo.contains(box):
				continue

			return (transform_epsg(potential_pcs), geo)

	# no projection found, if we're here
	if units == 'meters':
		return ({
			'name': 'World Mollweide',
			'crs': 'ESRI:54009',
			'units': 'meters'
		}, None)
	else:
		raise NoProjectionFoundError

def suggest_pcs(box, units='meters', n=3):
	"""Suggest multiple projected coordinate systems from a shapely geometry with specified units for the axes."""

	if not isinstance(box, BaseGeometry):
		raise TypeError('box passed to projectedcrs.choose_pcs() is not a shapely BaseGeometry, instead got \'%s\'' % type(box))
	if units not in ['feet', 'meters']:
		raise TypeError('units passed to projectedcrs.suggest_pcs() is neither feet nor meters')

	with fiona.open(CRS_DATASET, 'r') as epsg:
		intersects_box = epsg.values(bbox=box.bounds)

		# filter for proprety
		has_unit = filter(lambda geo: geo['geometry'] is not None and geo['properties']['axis_unit'] == units, intersects_box)

		# sort by area
		by_area = sorted(has_unit, key=lambda geo: geo['properties']['area'])

		# incrementally make list of suggestions, adding if contains
		suggestions = []

		for potential_pcs in by_area:
			if not shape(potential_pcs['geometry']).buffer(0).contains(box):
				continue

			suggestions.append(potential_pcs)

			if len(suggestions) >= n:
				break

		return list(map(transform_epsg, suggestions))

def transform_epsg(geojson):
	return {
		'name': geojson['properties']['name'],
		'epsg': geojson['properties']['EPSG'],
		'crs': 'EPSG:%d' % geojson['properties']['EPSG'],
		'units': geojson['properties']['axis_unit']
	}
