
from .dataset import Dataset

"""Map represents multiple Datasets of data, intended to be combined."""
class Map:

	def __init__(self, items):
		"""Create a map from multiple named datasetss."""
		self.collections = dict()

		for name, item in items.items():
			self.collections[name] = Dataset(item)
