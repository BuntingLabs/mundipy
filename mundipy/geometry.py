import json

import shapely.geometry as geom
from shapely.geometry import shape
import geopandas as gpd
import pandas as pd

class Point(geom.Point):

	def __init__(self, geo: geom.Point, features: dict):
		super().__init__(geo)

		self.features = features

	def __getitem__(self, item):
		return self.features[item]

	def __setitem__(self, item, value):
		self.features[item] = value

class LineString(geom.LineString):

	def __init__(self, geo: geom.LineString, features: dict):
		super().__init__(geo)

		self.features = features

	def __getitem__(self, item):
		return self.features[item]

	def __setitem__(self, item, value):
		self.features[item] = value

class Polygon(geom.Polygon):

	def __init__(self, geo: geom.Polygon, features: dict):
		super().__init__(geo)

		self.features = features

	def __getitem__(self, item):
		return self.features[item]

	def __setitem__(self, item, value):
		self.features[item] = value

class MultiPolygon(geom.MultiPolygon):

	def __init__(self, geo: geom.MultiPolygon, features: dict):
		super().__init__(geo)

		self.features = features

	def __getitem__(self, item):
		return self.features[item]

	def __setitem__(self, item, value):
		self.features[item] = value

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
