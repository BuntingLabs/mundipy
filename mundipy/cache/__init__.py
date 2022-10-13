"""
mundipy.cache provides spatial caches as function decorators.
"""

from functools import lru_cache
import geopandas as gpd
from shapely.geometry.base import BaseGeometry
import pyproj
import inspect

@lru_cache(maxsize=64)
def pyproj_transform(from_crs, to_crs):
    """ Returns a pyproj transform() function between two CRS, in 'EPSG:xxxx' format."""
    return pyproj.Transformer.from_crs(pyproj.CRS(from_crs),
        pyproj.CRS(to_crs), always_xy=True).transform

def spatial_cache_footprint(fn, maxsize=128):
	"""
	Cache this function for all geometries that fit within the returned
	shape, which is this function's footprint.

	The returned value must be valid for all geometries inside the
	footprint.

	Will cache up to maxsize items in an LRU cache.

	Function must return (result, footprint). If footprint is None,
	the result will not be cached.
	"""
	# list of (shape, result)
	cache = []

	cache_info = {
		'hits': 0,
		'misses': 0
	}

	def check_cache_first(*args, **kwargs):
		nonlocal cache

		# https://stackoverflow.com/questions/218616/how-to-get-method-parameter-names
		fn_is_method = inspect.getfullargspec(fn)[0][0] == 'self'

		if not fn_is_method and len(args) < 1:
			raise TypeError('zero args passed to function expecting one (spatial_cache_footprint)')
		elif not fn_is_method and (args[0] is not None and not isinstance(args[0], BaseGeometry)):
			raise TypeError('first arg passed to spatial_cache_footprint is not a shapely BaseGeometry, or None')
		if fn_is_method and len(args) < 2:
			raise TypeError('zero args passed to function expecting one (spatial_cache_footprint)')
		elif fn_is_method and (args[1] is not None and not isinstance(args[1], BaseGeometry)):
			raise TypeError('first arg passed to spatial_cache_footprint is not a shapely BaseGeometry, or None')

		shape = args[1 if fn_is_method else 0]
		# only check cache if shape is not None
		if shape is not None:
			for cache_item in cache:
				# cache hit
				if cache_item[1].contains(shape):
					cache_info['hits'] += 1
					return cache_item[0]

		# cache miss
		cache_info['misses'] += 1
		out = fn(*args, **kwargs)
		if out is None:
			return None

		res, footprint = out

		if footprint is not None:
			# re-order cache list to include the new hit
			cache = [(res, footprint)] + cache[:maxsize-1]

		return res

	check_cache_first.cache_info = cache_info

	return check_cache_first
