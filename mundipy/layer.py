from shapely.geometry.base import BaseGeometry
from shapely.geometry import box, Point, Polygon, MultiPolygon
import shapely.wkt
import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine
from functools import lru_cache, partial
import s2sphere

from mundipy.cache import spatial_cache_footprint

r = s2sphere.RegionCoverer()

def tile_bbox(polygon):
	bbox = polygon.bounds

	p1 = s2sphere.LatLng.from_degrees(bbox[3], bbox[0])
	p2 = s2sphere.LatLng.from_degrees(bbox[1], bbox[2])

	rect = s2sphere.LatLngRect.from_point_pair(p1, p2)

	# 14 is ~0.3km2 and 600m edge length
	return r.get_simple_covering(rect, p1.to_point(), 14)

"""A Layer represents a group of spatial data."""
class Layer:

	def __init__(self, data):
		self.filename = None
		self._dataframe = None
		self._db_url = None
		self._db_table = None

		self._conn = None

		""" Initialize a Layer from a data source. """
		if isinstance(data, gpd.GeoDataFrame):
			self._dataframe = data
		elif isinstance(data, dict):
			self._db_url = data['url']
			self._db_table = data['table']
		elif isinstance(data, str):
			self.filename = data
		else:
			raise TypeError('data for Layer() is not filename, GeoDataFrame or dict with PostgreSQL details')

	@spatial_cache_footprint
	def _load(self, bbox, pcs='EPSG:4326'):
		"""
		Load part or the entire Layer as a dataframe.

		Takes bbox as a 4-tuple of WGS84 coordinates (lon, lat). bbox can be
		None to load the entire dataset.

		Returns the dataset in PCS coordinates.
		"""
		if self._dataframe is not None:
			return (self._dataframe, None)

		if self._db_url is not None:
			# load from PostGIS
			self._conn = create_engine(self._db_url)

			# no bbox
			if bbox is None:
				# build the query
				query = "SELECT * FROM %s" % self._db_table

				gdf = gpd.GeoDataFrame.from_postgis(query, self._conn, geom_col='geometry', crs='EPSG:4326')
				self._conn = None
				return (gdf.to_crs(pcs), None)

			cell_ids = list(tile_bbox(bbox))

			tiles = [self._load_tile(cellid, pcs) for cellid in cell_ids]
			together = pd.concat(tiles)
			together_geo = gpd.GeoDataFrame(data=together, geometry='geometry', crs=pcs)

			self._conn = None

			# build footprint from cell_ids
			# needs 5 points to have a box polygon
			polygons = [[s2sphere.LatLng.from_point(s2sphere.Cell(cellid).get_vertex(v)) for v in [0, 1, 2, 3, 0]] for cellid in cell_ids]
			polygons = [Polygon([Point(v.lng().degrees, v.lat().degrees) for v in polygon]) for polygon in polygons]

			return (together_geo, MultiPolygon(polygons).buffer(0))

		if bbox is None:
			return (gpd.read_file(self.filename).to_crs(pcs), None)
		else:
			return (gpd.read_file(self.filename, bbox=bbox).to_crs(pcs), None)

	@lru_cache(maxsize=512)
	def _load_tile(self, cellid, pcs):
		vertices = [s2sphere.LatLng.from_point(s2sphere.Cell(cellid).get_vertex(v)) for v in range(4)]

		wkt = "POLYGON ((%f %f, %f %f, %f %f, %f %f, %f %f))" % (
			vertices[0].lng().degrees, vertices[0].lat().degrees,
			vertices[1].lng().degrees, vertices[1].lat().degrees,
			vertices[2].lng().degrees, vertices[2].lat().degrees,
			vertices[3].lng().degrees, vertices[3].lat().degrees,
			vertices[0].lng().degrees, vertices[0].lat().degrees,
		)
		# shapely.wkt.loads(wkt)

		query = "SELECT * FROM %s WHERE geometry && ST_GeomFromEWKT('SRID=4326;%s')" % (self._db_table, wkt)

		gdf = gpd.GeoDataFrame.from_postgis(query, self._conn, geom_col='geometry', crs='EPSG:4326')
		return gdf.to_crs(pcs)

	@property
	def dataframe(self):
		"""Load an entire Layer as a dataframe."""
		return self._load(None)

	@lru_cache(maxsize=8)
	def local_dataframe(self, pcs):
		return self.dataframe.to_crs(pcs)

	"""Read into a Layer at a specific geometry (WGS84)."""
	def inside_bbox(self, bbox, pcs='EPSG:4326'):
		if not isinstance(bbox, tuple) or len(bbox) != 4:
			raise TypeError('inside_bbox expected bbox to be a 4-tuple')

		return self._load(box(*bbox), pcs=pcs)


"""VisibleLayer represents Layer data, as seen from a geometry."""
class VisibleLayer:
	# Center needs to be projected to the local CRS already
	def __init__(self, layer, bbox, center, pcs=None):
		# do local calculations in a projected CRS, which is 2D and has
		# typical distance units
		if not isinstance(pcs, str):
			raise TypeError('pcs passed to VisibleLayer() was not a string')
		self.pcs = pcs

		if not isinstance(layer, Layer):
			raise TypeError('mapdata passed to VisibleLayer() was not a mundipy.Map')
		# results come as projected coordinate system
		self.local_collection = layer.inside_bbox(bbox, pcs=pcs)

		if not isinstance(center, BaseGeometry):
			raise TypeError('center passed to VisibleLayer was not shapely.geometry.BaseGeometry')
		self.center = center

	def intersects(self):
		"""Give a list of members that intersect with the center geometry."""
		possible_matches_index = list(self.local_collection.sindex.intersection(self.center.bounds))

		# indexing into dataframes is expensive, compute a new list of actual matches
		# .iloc only takes integer locations, even for columns
		geometry_col_loc = self.local_collection.columns.get_loc('geometry')
		actual_matches_index = [match for match in possible_matches_index if self.local_collection.iloc[match, geometry_col_loc].intersects(self.center)]

		return self.local_collection.iloc[actual_matches_index]

	def nearest(self):
		"""Give the closest member to the center geometry."""
		spatial_index = self.local_collection.sindex

		idx = spatial_index.nearest(self.center.centroid)
		return self.local_collection.iloc[idx[1][0]]

	def buffer(self, distance):
		"""Buffer the geometry by some distance."""

		return self.local_collection.geometry.buffer(distance)
