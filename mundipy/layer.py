from shapely.geometry.base import BaseGeometry
import geopandas as gpd
from sqlalchemy import create_engine

"""A Layer represents a group of spatial data."""
class Layer:

	def __init__(self, data):
		self.filename = None
		self._dataframe = None
		self._db_url = None
		self._db_table = None

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
			con = create_engine(self._db_url)

			# build the query
			query = "SELECT * FROM %s" % self._db_table
			if bbox is not None:
				query = "SELECT * FROM %s WHERE geometry && ST_MakeEnvelope(%f, %f, %f, %f, 4326)" % ((self._db_table,) + bbox)

			# assume it's WGS84
			return gpd.GeoDataFrame.from_postgis(query, con, geom_col='geometry', crs='EPSG:4326')

		if bbox is None:
			return gpd.read_file(self.filename)
		else:
			return gpd.read_file(self.filename, bbox=bbox)

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
