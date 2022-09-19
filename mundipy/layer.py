
import geopandas as gpd

"""A Layer represents a group of spatial data."""
class Layer:

	def __init__(self, data):
		""" Initialize a Layer from a data source. """
		self.projections = dict()

		if isinstance(data, gpd.GeoDataFrame):
			self.filename = None
			self._dataframe = data
		elif isinstance(data, str):
			self.filename = data
			self._dataframe = None
		else:
			raise TypeError('data for Layer() is neither filename nor GeoDataFrame')

	@property
	def dataframe(self):
		"""Load an entire Layer as a dataframe."""
		if self._dataframe is not None:
			return self._dataframe

		return gpd.read_file(self.filename)

	"""Read into a Layer at a specific geometry (WGS84)."""
	def inside_bbox(self, bbox):
		if not isinstance(bbox, tuple) or len(bbox) != 4:
			raise TypeError('inside_bbox expected bbox to be a 4-tuple')

		if self._dataframe is not None:
			return self._dataframe
		elif self.filename is not None:
			return gpd.read_file(self.filename, bbox=bbox)
