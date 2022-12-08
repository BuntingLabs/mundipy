import urllib.request
import urllib.parse
import json

from mundipy.geometry import loads, Point, dumps

def isochrone(pt, radius: float, units: str, accessToken=None):
	""" Calculate an isochrone via the Mapbox API. """
	if accessToken is None:
		raise ValueError('mundipy.api.isochrone called without Mapbox accessToken')
	if not isinstance(pt, Point):
		raise TypeError('mundipy.api.isochrone expects pt to be mundipy.geometry.Point, got %s' % type(pt))

	url = "https://api.mapbox.com/isochrone/v1/mapbox/driving/%f%%2C%f" % (pt.x, pt.y)
	params = {
		"polygons": "true",
		"denoise": 1,
		"access_token": accessToken
	}

	if units == 'minutes':
		params['contours_minutes'] = radius
	elif units == 'meters':
		params['contours_meters'] = radius
	else:
		raise TypeError('unknown unit "%s" passed to mundipy.api.isochrone (need minutes or meters)' % units)

	response = urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params))
	response_data = response.read().decode('utf-8')

	# gives FeatureCollection
	return loads(json.loads(response_data))[0]
