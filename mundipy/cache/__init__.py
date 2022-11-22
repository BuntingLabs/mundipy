"""
mundipy.cache provides spatial caches as function decorators.
"""

from functools import lru_cache
from shapely.geometry.base import BaseGeometry
import pyproj
import inspect

@lru_cache(maxsize=64)
def pyproj_transform(from_crs, to_crs):
    """ Returns a pyproj transform() function between two CRS, in 'EPSG:xxxx' format."""
    return pyproj.Transformer.from_crs(pyproj.CRS(from_crs),
        pyproj.CRS(to_crs), always_xy=True).transform

def union_spatial_cache(fn, maxsize=128):
	"""
	This decorator caches a function based on area containment calculations.
	For example, if a function returns geometries of objects that are
	contained by an area, adding @union_spatial_cache will cache the results
	based on area and PCS. Subsequent calls will use the cache to reduce
	the area the function must be called on, and the decorator will join
	the arrays.

	The function's last positional argument must be
	either a shapely.geometry or None.

	The function must return an array of mundipy geometries.
	"""

	# ((shape, pcs), df)
	cache = []

	def check_cache_first(*args, **kwargs):
		nonlocal cache

		if len(args) == 0:
			raise TypeError('union_spatial_cache fn must be passed >= 1 argument')
		geom = args[-1]

		# if no geometry, pass through
		if geom is None:
			return fn(*args, **kwargs)

		if not isinstance(geom, BaseGeometry):
			raise TypeError('last argument to union_spatial_cache fn is neither None nor shapely.geometry')

		# get pcs
		pcs = kwargs['pcs'] if 'pcs' in kwargs else 'EPSG:4326'

		# get all cache items that intersect and have same pcs
		# by default they will be sorted by area
		cached_dfs = filter(lambda c: c[0][1] == pcs and c[0][0].intersects(geom), cache)

		# find remaining area
		remaining_area = geom
		all_dfs = []
		for details, df in cached_dfs:
			cached_geom, _ = details

			# if remaining_area covers cached_geom, we can put the entire DF
			# in, saving intersection calculations
			# get intersection
			if remaining_area.covers(cached_geom):
				all_dfs.append(df)
			else:
				# fraction of df will be relevant in intersected area
				intersecting_area = cached_geom.intersection(remaining_area)
				# skip if intersecting_area is negligible
				if intersecting_area.area == 0.0:
					continue

				# get df in this area
				# some returned points from the function might be mundipy geometries
				intersecting_df = list(filter(lambda g: (g._geo if not isinstance(g, BaseGeometry) else g).intersects(intersecting_area), df))

				all_dfs.append(intersecting_df)

			# subtract from remaining
			remaining_area = remaining_area.difference(cached_geom)

			# quit early if no area left
			if remaining_area.area == 0.0:
				break

		# add most recent result if necessary
		if remaining_area.area > 0.0:
			result = fn(*args[:-1], remaining_area, **kwargs)

			all_dfs.append(result)

			# re-order cache list to include the new hit
			# sort by area so largest area is first
			cache = sorted([((geom, pcs), result)] + cache[:maxsize-1], reverse=True, key=lambda c: c[0][0].area)

		# TODO drop duplicates
		return [item for sublist in all_dfs for item in sublist]

	return check_cache_first

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

	# https://stackoverflow.com/questions/218616/how-to-get-method-parameter-names
	fn_is_method = inspect.getfullargspec(fn)[0][0] == 'self'

	def check_cache_first(*args, **kwargs):
		nonlocal cache

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
