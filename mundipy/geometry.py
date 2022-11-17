import json
from functools import partial, lru_cache

import shapely.geometry as geom
from shapely.geometry import shape, box
from shapely.ops import transform
import geopandas as gpd
import pandas as pd

from mundipy.cache import pyproj_transform
from mundipy.pcs import choose_pcs

class BaseGeometry():

	parent_class = None

	def __init__(self, geo, features: dict):
		self.features = features
		self._geo = geo

	def __getitem__(self, item):
		return self.features[item]

	def __setitem__(self, item, value):
		self.features[item] = value

	def __getattr__(self, name):
		# potentially intercept on behalf of shapely
		parent_methods = [f for f in dir(self.parent_class)]
		#  if callable(getattr(self.parent_class, f))

		if name in parent_methods:
			target = getattr(self.parent_class, name)

			# bind to self if callable
			if callable(target):
				def wrapper(*args, **kwargs):
					# wrap in appropriate PCS
					# get total bounds (minx, miny, maxx, maxy)
					total_bounds = [ obj.bounds for obj in args if isinstance(obj, BaseGeometry) ] + [ self.bounds ]
					total_bounds = ( min(map(lambda b: b[0], total_bounds)), min(map(lambda b: b[1], total_bounds)),
									 max(map(lambda b: b[2], total_bounds)), max(map(lambda b: b[3], total_bounds)) )

					projection = choose_pcs(box(*total_bounds), units='meters')['crs']

					custom_args = [self, *args]

					# convert to projections and raw shapely objects
					# pass through if floats, other types, etc
					# beware of double projecting, which is why we do shapely first, then mundipy geometries
					transformer = pyproj_transform('EPSG:4326', projection)
					custom_args = [ transform(transformer, x) if isinstance(x, geom.base.BaseGeometry) else x for x in custom_args ]

					custom_args = [ x.transform('EPSG:4326', projection)._geo if isinstance(x, BaseGeometry) else x for x in custom_args ]

					ret = target(*custom_args, **kwargs)

					# no conversion needed
					if not isinstance(ret, geom.base.BaseGeometry):
						return ret

					# return to our normal coordinate system
					return enrich_geom(ret, self.features).transform(projection, 'EPSG:4326')

				return wrapper
			elif isinstance(target, property):
				return target.fget(self._geo)
			else:
				return target
		else:
			raise AttributeError('"%s" has no attribute "%s"' % (str(type(self)), name))

	@lru_cache(maxsize=4)
	def transform(self, from_crs, to_crs):
		transformer = pyproj_transform(from_crs, to_crs)
		return enrich_geom(transform(transformer, self._geo), self.features)

class Point(BaseGeometry):

	parent_class = geom.Point

	def __init__(self, geo: geom.Point, features: dict):
		super().__init__(geo, features)

class LineString(BaseGeometry):

	parent_class = geom.LineString

	def __init__(self, geo: geom.LineString, features: dict):
		super().__init__(geo, features)


class Polygon(BaseGeometry):

	parent_class = geom.Polygon

	def __init__(self, geo: geom.Polygon, features: dict):
		super().__init__(geo, features)

class MultiPolygon(BaseGeometry):

	parent_class = geom.MultiPolygon

	def __init__(self, geo: geom.MultiPolygon, features: dict):
		super().__init__(geo, features)

def from_geojson(geojson: dict):
	if geojson['type'] != 'FeatureCollection':
		raise TypeError('expected FeatureCollection as top type')

	features = []

	for feature in geojson['features']:
		if feature['type'] != 'Feature':
			raise TypeError('expected Feature in features')

		if feature['geometry']['type'] == 'Point':
			features.append(Point(shape(feature['geometry']), feature['properties']))
		elif feature['geometry']['type'] == 'LineString':
			features.append(LineString(shape(feature['geometry']), feature['properties']))
		elif feature['geometry']['type'] == 'Polygon':
			features.append(Polygon(shape(feature['geometry']), feature['properties']))
		elif feature['geometry']['type'] == 'MultiPolygon':
			features.append(MultiPolygon(shape(feature['geometry']), feature['properties']))
		else:
			raise TypeError('geometry type was %s, expected Point/LineString/Polygon/MultiPolygon' % feature['geometry']['type'])

	return features

def from_row_series(row: pd.Series):
	features = dict(row)
	geo = row.geometry
	del features['geometry']

	if isinstance(geo, geom.Point):
		return Point(geo, features)
	elif isinstance(geo, geom.LineString):
		return LineString(geo, features)
	elif isinstance(geo, geom.Polygon):
		return Polygon(geo, features)
	elif isinstance(geo, geom.MultiPolygon):
		return MultiPolygon(geo, features)
	else:
		raise TypeError('from_row_series got %s, expected Point/LineString/Polygon/MultiPolygon' % str(type(geo)))

def from_dataframe(gdf: gpd.GeoDataFrame):
	return from_geojson(gdf.__geo_interface__)

def enrich_geom(geo, features):
	"""Enrich a shapely geometry with old features"""
	if isinstance(geo, geom.Point):
		return Point(geo, features)
	elif isinstance(geo, geom.LineString):
		return LineString(geo, features)
	elif isinstance(geo, geom.Polygon):
		return Polygon(geo, features)
	elif isinstance(geo, geom.MultiPolygon):
		return MultiPolygon(geo, features)
	else:
		raise TypeError('enrich_geom got %s, expected Point/LineString/Polygon/MultiPolygon' % str(type(geo)))
