"""
The `Dataset` forms the core abstraction in mundipy.

A Dataset comprises any source for vector data. Instantiating a
Dataset declares its accessibility, but does not automatically
load features, as all features are lazily loaded.

Dataset implements the iterable interface, making it easy to iterate
over features in a dataset.
"""

from shapely.geometry.base import BaseGeometry
from shapely.geometry import box, Point, Polygon, MultiPolygon
import shapely.wkt
import shapely.wkb
import geopandas as gpd
from shapely.ops import transform
from functools import lru_cache, partial
from cached_property import cached_property_with_ttl
import psycopg
from psycopg_pool import ConnectionPool

from mundipy.cache import (spatial_cache_footprint, pyproj_transform,
	union_spatial_cache)
from mundipy.geometry import from_dataframe, from_row_series, enrich_geom
import mundipy.geometry as mgeom

def elements_from_cursor(cur):
	# get column names
	colnames = [desc[0] for desc in cur.description]

	return [ element_from_tuple(tup, colnames) for tup in cur.fetchall() ]

def element_from_tuple(tup, colnames):
	features = dict()
	geom = None

	for i, val in enumerate(tup):
		# comes as WKB encoded
		if colnames[i] == 'geometry':
			geom = shapely.wkb.loads(bytes.fromhex(val))
		else:
			features[colnames[i]] = val

	return enrich_geom(geom, features)

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

			# 3 second timeout
			self._pool = ConnectionPool(self._db_url, timeout=3.0)
		elif isinstance(data, str):
			self.filename = data
		else:
			raise TypeError('data for Dataset() is neither filename nor dict with PostgreSQL details')

	@union_spatial_cache
	def _load(self, geom):
		"""
		Load part or the entire Dataset as a list of mundipy geometries.

		Takes geom as a shapely.geometry, or None to load the
		entire dataset.

		Returns the dataset in WGS84.
		"""

		if self._db_url is not None:
			with self._pool.connection() as conn:
				cur = conn.execute("SELECT * FROM %s" % self._db_table)

				# no geom
				if geom is None:
					# build the query
					query = "SELECT * FROM %s" % self._db_table
				else:
					# load entire geometry
					query = "SELECT * FROM %s WHERE geometry && ST_GeomFromEWKT('SRID=4326;%s')" % (self._db_table, geom.wkt)

				return elements_from_cursor(conn.execute(query))

		if geom is None:
			gdf = gpd.read_file(self.filename)
		else:
			gdf = gpd.read_file(self.filename, bbox=geom)

		return from_dataframe(gdf)

	@lru_cache(maxsize=8)
	def geometry_collection(self):
		return self._load(None)

	"""Read into a Dataset at a specific geometry (WGS84)."""
	def inside_bbox(self, bbox):
		if not isinstance(bbox, tuple) or len(bbox) != 4:
			raise TypeError('inside_bbox expected bbox to be a 4-tuple')

		return self._load(box(*bbox))

	def __iter__(self):
		"""
		Iterate through all items of the dataset.
		"""
		yield from self.geometry_collection()

	def intersects(self, geom):
		"""
		Returns an `Iterator` of mundipy geometries that intersect
		with `geom`.

		`geom` - inherits from `shapely.geometry`

		from mundipy.utils import plot

		for feat in layer.intersects(Point(-37.0, 42.1)):
			plot(feat)
		"""
		if not isinstance(geom, BaseGeometry) and not isinstance(geom, mgeom.BaseGeometry):
			raise TypeError('geom is neither shapely.geometry nor mundipy.geometry')

		# buffer by an ~inch to prevent point
		bbox = (geom.buffer(1e-3) if isinstance(geom, Point) or isinstance(geom, mgeom.Point) else geom).bounds

		potentially_intersecting = self.inside_bbox(bbox)
		return list(filter(lambda g: g.intersects(geom), potentially_intersecting))

	def nearest(self, geom):
		"""
		Returns the nearest feature in this collection to the passed
		geometry.

		Returns `None` if the dataset has no features.

		`geom`: inherits from `shapely.geometry`
		"""
		if not isinstance(geom, BaseGeometry) and not isinstance(geom, mgeom.BaseGeometry):
			raise TypeError('geom is neither shapely.geometry nor mundipy.geometry')

		# increasing look outside of this bbox for the nearest item
		buffer_distances = [1e3, 1e4, 1e5, 1e6, 1e7, 1e8]
		for buffer_size in buffer_distances:
			# buffer geom.bbox
			bbox = geom.buffer(buffer_size).bounds

			items = self.inside_bbox(bbox)
			if len(items) > 0:
				return min(items, key=lambda geo: geom.distance(geo))

		# fuck it, check the whole dataframe
		items = self.geometry_collection()
		if len(items) > 0:
			return min(items, key=lambda geo: geom.distance(geo))

		return None
