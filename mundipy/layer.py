from shapely.geometry.base import BaseGeometry
import shapely.wkt
import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine
from functools import lru_cache
import s2sphere

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

	def _load(self, bbox=None):
		"""Load part or the entire Layer as a dataframe."""
		if self._dataframe is not None:
			return self._dataframe

		if self._db_url is not None:
			# load from PostGIS
			self._conn = create_engine(self._db_url)

			# no bbox
			if bbox is None:
				# build the query
				query = "SELECT * FROM %s" % self._db_table

				# assume it's WGS84
				gdf = gpd.GeoDataFrame.from_postgis(query, self._conn, geom_col='geometry', crs='EPSG:4326')
				self._conn = None
				return gdf

			# tile the area
			r = s2sphere.RegionCoverer()
			# cell level 20 = typical edge length of 7-10m or 30ft
			r.max_level = 20

			p1 = s2sphere.LatLng.from_degrees(bbox[3], bbox[0])
			p2 = s2sphere.LatLng.from_degrees(bbox[1], bbox[2])

			cell_ids = r.get_covering(s2sphere.LatLngRect.from_point_pair(p1, p2))

			tiles = [self._load_tile(cellid) for cellid in cell_ids]
			together = pd.concat(tiles)
			together_geo = gpd.GeoDataFrame(data=together, geometry='geometry', crs='EPSG:4326')

			self._conn = None

			return together_geo

		if bbox is None:
			return gpd.read_file(self.filename)
		else:
			return gpd.read_file(self.filename, bbox=bbox)

	@lru_cache(maxsize=512)
	def _load_tile(self, cellid):
		vertices = [s2sphere.LatLng.from_point(s2sphere.Cell(cellid).get_vertex(v)) for v in range(4)]

		wkt = "POLYGON ((%f %f, %f %f, %f %f, %f %f, %f %f))" % (
			vertices[0].lng().degrees, vertices[0].lat().degrees,
			vertices[1].lng().degrees, vertices[1].lat().degrees,
			vertices[2].lng().degrees, vertices[2].lat().degrees,
			vertices[3].lng().degrees, vertices[3].lat().degrees,
			vertices[0].lng().degrees, vertices[0].lat().degrees,
		)
		# shapely.wkt.loads(wkt)

		# assume it's WGS84
		query = "SELECT * FROM %s WHERE geometry && ST_GeomFromEWKT('SRID=4326;%s')" % (self._db_table, wkt)

		return gpd.GeoDataFrame.from_postgis(query, self._conn, geom_col='geometry', crs='EPSG:4326')

	@property
	def dataframe(self):
		"""Load an entire Layer as a dataframe."""
		return self._load()

	"""Read into a Layer at a specific geometry (WGS84)."""
	def inside_bbox(self, bbox):
		if not isinstance(bbox, tuple) or len(bbox) != 4:
			raise TypeError('inside_bbox expected bbox to be a 4-tuple')

		return self._load(bbox=bbox)


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
		self.local_collection = layer.inside_bbox(bbox).to_crs(crs=pcs)

		if not isinstance(center, BaseGeometry):
			raise TypeError('center passed to VisibleLayer was not shapely.geometry.BaseGeometry')
		self.center = center

	def intersects(self):
		"""Give a list of members that intersect with the center geometry."""
		spatial_index = self.local_collection.sindex
		possible_matches_index = list(spatial_index.intersection(self.center.bounds))
		possible_matches = self.local_collection.iloc[possible_matches_index]

		return possible_matches[possible_matches.intersects(self.center)]

	def nearest(self):
		"""Give the closest member to the center geometry."""
		spatial_index = self.local_collection.sindex

		idx = spatial_index.nearest(self.center.centroid)
		return self.local_collection.iloc[idx[1][0]]

	def buffer(self, distance):
		"""Buffer the geometry by some distance."""

		return self.local_collection.geometry.buffer(distance)
