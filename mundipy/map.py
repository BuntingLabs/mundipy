
from .layer import Layer

"""Map represents multiple Layers of data, intended to be combined."""
class Map:

	def __init__(self, items):
		"""Create a map from multiple named layers."""
		self.collections = dict()

		for name, item in items.items():
			self.collections[name] = Layer(item)
