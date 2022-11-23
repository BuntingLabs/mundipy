import json
from functools import lru_cache, cached_property

import shapely.geometry as geom
from shapely.geometry import shape, box
from shapely import transform
import numpy as np

from mundipy.cache import pyproj_transform
from mundipy.pcs import choose_pcs

# Set bit = yes
# Must we transform any coordinates at all to do this operation?
TRANSFORM_INPUT = 1 << 0
# Does this operation return a shapely base geometry?
# this implies we transform the result back
RETURN_GEO = 1 << 1

SHAPELY_METHODS = {
	'__and__': 0,
	'__array_interface__': 0,
	'__bool__': 0,
	'__class__': 0,
	'__del__': 0,
	'__delattr__': 0,
	'__dict__': 0,
	'__dir__': 0,
	'__doc__': 0,
	'__eq__': 0,
	'__format__': 0,
	'__ge__': 0,
	'__geo_interface__': 0,
	'__geom__': 0,
	'__getattribute__': 0,
	'__getstate__': 0,
	'__gt__': 0,
	'__hash__': 0,
	'__init__': 0,
	'__init_subclass__': 0,
	'__le__': 0,
	'__lt__': 0,
	'__module__': 0,
	'__ne__': 0,
	'__new__': 0,
	'__nonzero__': 0,
	'__or__': 0,
	'__p__': 0,
	'__reduce__': 0,
	'__reduce_ex__': 0,
	'__repr__': 0,
	'__setattr__': 0,
	'__setstate__': 0,
	'__sizeof__': 0,
	'__str__': 0,
	'__sub__': 0,
	'__subclasshook__': 0,
	'__weakref__': 0,
	'__xor__': 0,
	'_array_interface_base': 0,
	'_crs': 0,
	'_ctypes': 0,
	'_ctypes_data': 0,
	'_empty': 0,
	'_geom': 0,
	'_get_coords': 0,
	'_is_empty': 0,
	'_lgeos': 0,
	'_ndim': 0,
	'_other_owned': 0,
	'_repr_svg_': 0,
	'_set_coords': 0,
	'_set_geom': 0,
	# Should be spatially invariant
	'almost_equals': 0,
	# Depends on the transformation but returns a float
	'area': TRANSFORM_INPUT,
	'array_interface_base': 0,
	# Don't think this needs to be projected
	'boundary': 0,
	'bounds': 0,
	# Does need projection because of units and distortion
	'buffer': TRANSFORM_INPUT | RETURN_GEO,
	# Centroid changes depending on location on the earth
	'centroid': TRANSFORM_INPUT | RETURN_GEO,
	# needs everything probably
	'convex_hull': TRANSFORM_INPUT | RETURN_GEO,
	# just give straight coordinates
	'coords': 0,
	# boolean ops
	# straight line on earth != projected straight line
	'contains': TRANSFORM_INPUT,
	'covered_by': TRANSFORM_INPUT,
	'covers': TRANSFORM_INPUT,
	'crosses': TRANSFORM_INPUT,
	'disjoint': TRANSFORM_INPUT,
	'intersects': TRANSFORM_INPUT,
	'overlaps': TRANSFORM_INPUT,
	'touches': TRANSFORM_INPUT,
	# idk
	'ctypes': 0,
	# needs all
	'difference': TRANSFORM_INPUT | RETURN_GEO,
	# needs projection returns float
	'distance': TRANSFORM_INPUT,
	# bool property
	'empty': 0,
	# needs all
	'envelope': TRANSFORM_INPUT | RETURN_GEO,
	# none needed because pointwise
	'equals': 0,
	'equals_exact': 0,
	'geom_type': 0,
	'geometryType': 0,
	'has_z': 0,
	# much like .distance()
	'hausdorff_distance': TRANSFORM_INPUT,
	# idk
	'impl': 0,
	# adds more points within a line, definitely needs this
	'interpolate': TRANSFORM_INPUT | RETURN_GEO,
	# needs all
	'intersection': TRANSFORM_INPUT | RETURN_GEO,
	# bool unnecessary
	'is_closed': 0,
	'is_empty': 0,
	'is_ring': 0,
	'is_simple': 0,
	'is_valid': 0,
	# projection to units
	'length': TRANSFORM_INPUT,
	# needs units
	'minimum_clearance': TRANSFORM_INPUT,
	# gives a polygon
	'minimum_rotated_rectangle': TRANSFORM_INPUT | RETURN_GEO,
	# internal method that re-orders points
	'normalize': 0,
	# distance calculation
	'project': TRANSFORM_INPUT,
	# complex; this might be wrong
	'relate': TRANSFORM_INPUT,
	'relate_pattern': TRANSFORM_INPUT,
	# does not matter as long as it's inside
	'representative_point': 0,
	# tolerance should be in units
	'simplify': TRANSFORM_INPUT | RETURN_GEO,
	# ??
	'svg': 0,
	# needs all
	'symmetric_difference': TRANSFORM_INPUT | RETURN_GEO,
	# don't think this is geometric
	'type': 0,
	# needs all
	'union': TRANSFORM_INPUT | RETURN_GEO,
	# same as .contains
	'within': TRANSFORM_INPUT | RETURN_GEO,
	'wkb': 0,
	'wkb_hex': 0,
	'wkt': 0,
	# no transform needed
	'xy': 0
}

# dir() is expensive, so cache by type
@lru_cache(maxsize=8)
def parent_methods(parent_class):
	return [f for f in dir(parent_class)]

class BaseGeometry():

	parent_class = None

	def __init__(self, geo, crs: str, features: dict):
		self.features = features
		self.crs = crs
		# could be a function, could be a value
		self._geo_val = geo

	@property
	def _geo(self):
		if callable(self._geo_val):
			self._geo_val = self._geo_val()

		return self._geo_val

	@lru_cache(maxsize=4)
	def transform(self, to_crs):
		# no transform needed
		if to_crs == self.crs:
			return self

		transformer = pyproj_transform(self.crs, to_crs)
		def np_transform(pts):
			fx, fy = transformer(pts[:, 0], pts[:, 1])
			return np.dstack([fx, fy])[0]

		newpoly = transform(self._geo, np_transform)
		return enrich_geom(newpoly, self.features, pcs=to_crs)

	def __getitem__(self, item):
		return self.features[item]

	def __setitem__(self, item, value):
		self.features[item] = value

	@property
	def fast_bounds(self):
		return self.transform('EPSG:4326')._geo.bounds

	@property
	def __geo_interface__(self):
		"""Get a GeoJSON representation in EPSG:4326"""
		return {
			'type': 'Feature',
			'geometry': self.transform('EPSG:4326')._geo.__geo_interface__,
			'properties': self.features
		}

	def __getattr__(self, name):
		if name in parent_methods(self.parent_class):
			target = getattr(self.parent_class, name)

			# bind to self if callable
			if callable(target):
				# get attribute flags
				attr_flags = SHAPELY_METHODS[name]

				def projection_wrapper(*args, **kwargs):
					# wrapper function for any method that could require
					# projecting to a cartesian coordinate plane
					custom_args = [self, *args]

					# many methods require that we transform the self and other
					# arguments to a local projection before executing the op
					if attr_flags & TRANSFORM_INPUT:
						# wrap in appropriate PCS
						# get total bounds (minx, miny, maxx, maxy)
						total_bounds = [ obj.fast_bounds for obj in args if isinstance(obj, BaseGeometry) ] + [ self.fast_bounds ]
						total_bounds = ( min(map(lambda b: b[0], total_bounds)), min(map(lambda b: b[1], total_bounds)),
										 max(map(lambda b: b[2], total_bounds)), max(map(lambda b: b[3], total_bounds)) )

						projection = choose_pcs(box(*total_bounds), units='meters')['crs']

						# convert to projections and raw shapely objects
						# pass through if floats, other types, etc
						# beware of double projecting, which is why we do shapely first, then mundipy geometries
						transformer = pyproj_transform('EPSG:4326', projection)
						custom_args = [ transform(transformer, x) if isinstance(x, geom.base.BaseGeometry) else x for x in custom_args ]

						custom_args = [ x.transform(projection)._geo if isinstance(x, BaseGeometry) else x for x in custom_args ]

					# if we don't return a geometric object, we immediately
					# execute and return
					if not attr_flags & RETURN_GEO:
						return target(*custom_args, **kwargs)

					# If we do return a geometry, there's a chance we need to
					# reproject into the geographic coordinate system, but also
					# a chance that we want to keep in the local projection.
					# Because of this, we create the geometry from local, and
					# will lazily transform to geographic if needed.
					ret = target(*custom_args, **kwargs)
					return enrich_geom(ret, self.features, pcs=projection)

				return projection_wrapper
			elif isinstance(target, property):
				# properties are calculated in EPSG:4326
				return target.fget(self.transform('EPSG:4326')._geo)
			else:
				return target
		else:
			raise AttributeError('"%s" has no attribute "%s"' % (str(type(self)), name))

class Point(BaseGeometry):

	parent_class = geom.Point

	def __init__(self, geo: geom.Point, crs: str, features: dict):
		super().__init__(geo, crs, features)

class LineString(BaseGeometry):

	parent_class = geom.LineString

	def __init__(self, geo: geom.LineString, crs: str, features: dict):
		super().__init__(geo, crs, features)


class Polygon(BaseGeometry):

	parent_class = geom.Polygon

	def __init__(self, geo: geom.Polygon, crs: str, features: dict):
		super().__init__(geo, crs, features)

class MultiPolygon(BaseGeometry):

	parent_class = geom.MultiPolygon

	def __init__(self, geo: geom.MultiPolygon, crs: str, features: dict):
		super().__init__(geo, crs, features)

def enrich_geom(geo, features, pcs='EPSG:4326'):
	"""Enrich a shapely geometry with old features"""
	if isinstance(geo, geom.Point):
		return Point(geo, pcs, features)
	elif isinstance(geo, geom.LineString):
		return LineString(geo, pcs, features)
	elif isinstance(geo, geom.Polygon):
		return Polygon(geo, pcs, features)
	elif isinstance(geo, geom.MultiPolygon):
		return MultiPolygon(geo, pcs, features)
	else:
		raise TypeError('enrich_geom got %s, expected Point/LineString/Polygon/MultiPolygon' % str(type(geo)))
