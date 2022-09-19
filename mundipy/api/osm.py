import overpy
from shapely.ops import polygonize
from shapely.geometry import shape, LineString, Point, Polygon, MultiPolygon
import geopandas as gpd

def grab_from_osm(tups=[], bbox=None):
	if not isinstance(bbox, str):
		raise TypeError('bbox is not string')

	api = overpy.Overpass()

	# tups is ['highway=residential']
	# convert to [('node', ..), ('way', ..), ('relation', ..)]
	tups = map(lambda tag: [(osmt, tag) for osmt in ['node', 'way', 'relation']], tups)
	tups = [item for sublist in tups for item in sublist]

	overpass_center = '\n'.join(list(map(lambda t: "%s[%s](%s);" % (t[0], t[1], bbox), tups)))

	result = api.query("[out:json];(%s); out body; >; out skel qt;" % overpass_center)

	return result_to_gdf(result)

def node_to_shape(n):
	return Point(n.lon, n.lat)

def way_to_shape(w):
	if len(w.get_nodes()) > 2:
		return Polygon([Point(node.lon, node.lat) for node in w.get_nodes()])
	elif len(w.get_nodes()) == 2:
		return LineString([Point(node.lon, node.lat) for node in w.get_nodes()])
	else:
		raise TypeError('way_to_shape() called on way with 1 or 0 nodes')

def result_to_gdf(results):
	nodes = results.get_elements(overpy.Node)
	node_series = map(lambda n: (node_to_shape(n),), nodes)

	ways = results.get_elements(overpy.Way)
	way_series = map(lambda w: (way_to_shape(w),), ways)

	return gpd.GeoDataFrame(data=list(node_series) + list(way_series),
		geometry='geometry', crs='EPSG:4326', columns=['geometry'])
