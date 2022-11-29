"""
The `Dataset` forms the core abstraction in mundipy.

A Dataset comprises any source for vector data. Instantiating a
Dataset declares its accessibility, but does not automatically
load features, as all features are lazily loaded.

Dataset implements the iterable interface, making it easy to iterate
over features in a dataset.
"""

from shapely.geometry.base import BaseGeometry
from shapely.geometry import box, shape, Point, Polygon, MultiPolygon
import shapely.wkt
import shapely.wkb
from shapely.ops import transform
from functools import lru_cache, partial
import psycopg
import fiona
from psycopg_pool import ConnectionPool

from mundipy.cache import (spatial_cache_footprint, pyproj_transform,
	union_spatial_cache)
from mundipy.geometry import enrich_geom
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
		elif isinstance(data, str):
			self.filename = data
		else:
			raise TypeError('data for Dataset() is neither filename nor dict with PostgreSQL details')

	@property
	def _pool(self):
		# 3 second timeout
		return ConnectionPool(self._db_url, timeout=3.0, min_size=1, max_size=1)

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

		f = fiona.open(self.filename)

		if geom is None:
			items = f.values()
		else:
			items = f.values(bbox=geom.bounds)

		return [ enrich_geom(shape(item['geometry']), dict(item['properties'])) for item in items ]

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

	def __len__(self):
		if self.filename is None:
			raise NotImplementedError('Dataset.__len__ not implemented for PostGIS tables')

		return len(fiona.open(self.filename))

	@property
	def bounds(self):
		if self.filename is None:
			raise NotImplementedError('Dataset.bounds not implemented for PostGIS table')

		return fiona.open(self.filename).bounds

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

	def within(self, radius, geom):
		"""
		Returns an `Iterator` of mundipy geometries that are
		no farther than the given radius from geom.
		"""
		if not isinstance(geom, mgeom.BaseGeometry):
			raise TypeError('geom is not mundipy.geometry')
		if not isinstance(radius, float) and not isinstance(radius, int):
			raise TypeError('radius passed to within() is neither float nor int')

		# buffer to create intersection zone
		zone = geom.buffer(radius)

		return self.intersects(zone)

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

	def _repr_svg_(self):
		# Inspiration from https://github.com/shapely/shapely/blob/34136cd3104a197c3b47c97d44914197fb00879a/shapely/geometry/base.py#L263
		# Some of the below code is licensed as shapely is

		# Establish SVG canvas that will fit all the data + small space
		total_bounds = [ obj.bounds for obj in iter(self) ]
		total_bounds = ( min(map(lambda b: b[0], total_bounds)), min(map(lambda b: b[1], total_bounds)),
						 max(map(lambda b: b[2], total_bounds)), max(map(lambda b: b[3], total_bounds)) )

		xmin, ymin, xmax, ymax = total_bounds

		# Expand bounds by a fraction of the data ranges
		expand = 0.04  # or 4%, same as R plots
		widest_part = max([xmax - xmin, ymax - ymin])
		expand_amount = widest_part * expand
		xmin -= expand_amount
		ymin -= expand_amount
		xmax += expand_amount
		ymax += expand_amount

		dx = xmax - xmin
		dy = ymax - ymin
		width = min([max([300.0, dx]), 500])
		height = min([max([300.0, dy]), 500])
		try:
			scale_factor = max([dx, dy]) / max([width, height])
		except ZeroDivisionError:
			scale_factor = 1.0

		view_box = f"{xmin} {ymin} {dx} {dy}"
		transform = f"matrix(1,0,0,-1,0,{ymax + ymin})"

		svg_content = ''.join(['<g transform="{0}">{1}</g>'.format(transform, child.svg(scale_factor)) for child in iter(self) ])

		return (
			'<svg xmlns="http://www.w3.org/2000/svg" '
			'xmlns:xlink="http://www.w3.org/1999/xlink" '
			'width="{1}" height="{2}" viewBox="{0}" '
			'preserveAspectRatio="xMinYMin meet">'
			'{3}</svg>'
		).format(view_box, width, height, svg_content)


