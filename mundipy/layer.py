"""
`Dataset`s and `LayerView`s form the core abstractions in mundipy.

`Dataset` comprises any source for vector data. Instantiating a
`Dataset` declares its accessibility, but does not automatically
load features, as all features are lazily loaded.

`LayerView` represents a collection of vector features, typically
a subset from a `Dataset`. This makes queries like intersection
and nearest much faster because only a subset of the `Dataset`
must be loaded.
"""

from shapely.geometry.base import BaseGeometry
from shapely.geometry import box, Point, Polygon, MultiPolygon
import shapely.wkt
from shapely.ops import transform
import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine
from functools import lru_cache, partial
from cached_property import cached_property_with_ttl

from mundipy.cache import (spatial_cache_footprint, pyproj_transform,
	union_spatial_cache)
from mundipy.geometry import from_dataframe, from_row_series

class Dataset:
	"""
	A Dataset represents a source of vector features.

	from mundipy.layer import Dataset

	src = Dataset({
 		'url': 'postgresql://postgres@localhost:5432/postgres',
		'table': 'table_name'
	})

	"""

	def __init__(self, data):
		""" Initialize a Dataset from a data source. """

		self.filename = None
		self._db_url = None
		self._db_table = None

		if isinstance(data, dict):
			self._db_url = data['url']
			self._db_table = data['table']
		elif isinstance(data, str):
			self.filename = data
		else:
			raise TypeError('data for Dataset() is neither filename nor dict with PostgreSQL details')

	@cached_property_with_ttl(ttl=10)
	def _conn(self):
		"""SQLAlchemy connection to the database, if _db_url is set"""

		if self._db_url is None:
			raise TypeError('Dataset._conn called when no _db_url was set')

		return create_engine(self._db_url)

	@union_spatial_cache
	def _load(self, geom, pcs='EPSG:4326'):
		"""
		Load part or the entire Dataset as a dataframe.

		Takes geom as a shapely.geometry, or None to load the
		entire dataset.

		Returns the dataset in PCS coordinates.
		"""

		# convert from WGS84 to local PCS
		transformer = partial(transform, pyproj_transform('EPSG:4326', pcs))

		if self._db_url is not None:
			# no geom
			if geom is None:
				# build the query
				query = "SELECT * FROM %s" % self._db_table

				gdf = gpd.GeoDataFrame.from_postgis(query, self._conn, geom_col='geometry', crs='EPSG:4326')
				gdf.set_geometry(gdf.geometry.apply(transformer), inplace=True, crs=pcs)
				return gdf

			# load entire geometry
			query = "SELECT * FROM %s WHERE geometry && ST_GeomFromEWKT('SRID=4326;%s')" % (self._db_table, geom.wkt)

			gdf = gpd.GeoDataFrame.from_postgis(query, self._conn, geom_col='geometry', crs='EPSG:4326')
			gdf.set_geometry(gdf.geometry.apply(transformer), inplace=True, crs=pcs)
			return gdf

		if geom is None:
			gdf = gpd.read_file(self.filename)
		else:
			gdf = gpd.read_file(self.filename, bbox=geom)

		gdf.set_geometry(gdf.geometry.apply(transformer), inplace=True, crs=pcs)
		return gdf

	@property
	def dataframe(self):
		"""Load an entire Dataset as a dataframe."""
		return self._load(None)

	@lru_cache(maxsize=8)
	def local_dataframe(self, pcs):
		return self._load(None, pcs=pcs)

	@lru_cache(maxsize=8)
	def geometry_collection(self, pcs):
		return from_dataframe(self.local_dataframe(pcs))

	"""Read into a Dataset at a specific geometry (WGS84)."""
	def inside_bbox(self, bbox, pcs='EPSG:4326'):
		if not isinstance(bbox, tuple) or len(bbox) != 4:
			raise TypeError('inside_bbox expected bbox to be a 4-tuple')

		return self._load(box(*bbox), pcs=pcs)

class LayerView:
	"""
	`LayerView` represents a collection of vector features in
	a single dataset. It implements an `Iterable` interface,
	allowing for one to loop through all features in the dataset,
	or smart filtering without loading the entire dataset into
	memory.
	"""

	def __init__(self, layer, pcs):
		self.layer = layer
		self.pcs = pcs

	def __iter__(self):
		"""
		Iterate through all items of the dataset.
		"""
		yield from self.layer.geometry_collection(self.pcs)

	def intersects(self, geom):
		"""
		Returns an `Iterator` of mundipy geometries that intersect
		with `geom`.

		`geom` - inherits from `shapely.geometry`

        from mundipy.utils import plot

        for feat in layer.intersects(Point(-37.0, 42.1)):
            plot(feat)
		"""
		if not isinstance(self.layer, Dataset):
			raise TypeError('intersects() on not Dataset undefined')
		if not isinstance(geom, BaseGeometry):
			raise TypeError('geom is not a shapely.geometry')

		# convert geom to EPSG:4326
		to_wgs = pyproj_transform(self.pcs, 'EPSG:4326')
		# buffer a little bit to prevent point
		bbox = transform(to_wgs, geom.buffer(1e-8)).bounds

		potentially_intersecting_gdf = self.layer.inside_bbox(bbox, self.pcs)
		return from_dataframe(potentially_intersecting_gdf[potentially_intersecting_gdf.intersects(geom)])

	def nearest(self, geom):
		"""
		Returns the nearest feature in this collection to the passed
		geometry.

		Returns `None` if the dataset has no features.

		`geom`: inherits from `shapely.geometry`
		"""
		if not isinstance(self.layer, Dataset):
			raise TypeError('intersects() on not Dataset undefined')
		if not isinstance(geom, BaseGeometry):
			raise TypeError('geom is not a shapely.geometry')

		to_wgs = pyproj_transform(self.pcs, 'EPSG:4326')

		# increasing look outside of this bbox for the nearest item
		buffer_distances = [1e3, 1e4, 1e5, 1e6, 1e7, 1e8]
		for buffer_size in buffer_distances:
			# buffer geom.bbox
			bbox = transform(to_wgs, geom.buffer(buffer_size)).bounds

			gdf = self.layer.inside_bbox(bbox, self.pcs)
			if len(gdf) > 0:
				res = min(gdf.iterrows(), key=lambda row: geom.distance(row[1].geometry))

				return from_row_series(res[1])

		# fuck it, check the whole dataframe
		gdf = self.layer.local_dataframe(self.pcs)
		if len(gdf) > 0:
			res = min(gdf.iterrows(), key=lambda row: geom.distance(row[1].geometry))

			return from_row_series(res[1])

		return None
