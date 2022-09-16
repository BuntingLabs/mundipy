import pyproj

import geopandas as gpd
from tqdm import tqdm
import fiona
from fiona.crs import from_epsg
from shapely.ops import transform
from shapely.geometry import shape, mapping, MultiPolygon, box
import sys
import numpy as np

import pyproj.exceptions
import fiona.errors
import shapely.errors

if len(sys.argv) < 3:
	print('needs python3 simplify.py <input> <output>')

with fiona.open(sys.argv[1], 'r') as source:

	new_schema = source.schema
	new_schema['properties'] = {
		'EPSG': 'int',
		'name': 'str',
		'axis_unit': 'str'
	}
	new_schema['geometry'] = 'Polygon'

	with fiona.open(sys.argv[2], 'w', driver='GeoJSON',
		crs=from_epsg(4326), schema=new_schema) as out:

		for region in tqdm(source):
			if region['geometry'] is None:
				continue

			# try:
			old_prop = region['properties']
			properties = {
				'EPSG': int(old_prop['COORD_REF_SYS_CODE'] if 'COORD_REF_SYS_CODE' in old_prop else old_prop['COORD_OP_CODE']),
				'name': old_prop['COORD_REF_SYS_NAME'] if 'COORD_REF_SYS_NAME' in old_prop else old_prop['COORD_OP_NAME'],
				'axis_unit': ''
			}

			# filter out deprecated = 1
			if region['properties']['DEPRECATED'] == 1:
				continue

			# filter out for projections that exist?
			try:
				crs = pyproj.CRS('EPSG:%d' % properties['EPSG'])
				# the axis better have the same units
				if crs.axis_info[0].unit_name != crs.axis_info[1].unit_name:
					continue

				if crs.axis_info[0].unit_name in ['US survey foot', 'foot']:
					properties['axis_unit'] = 'feet'
				elif crs.axis_info[0].unit_name == 'metre':
					properties['axis_unit'] = 'meters'
				else:
					continue

			except pyproj.exceptions.CRSError:
				continue
			except Exception as e:
				raise e

			# simplify by 500m
			simplified_boundary = shape(region['geometry']).simplify(0.005, preserve_topology=False).buffer(0)

			# take largest if multipolygon
			if isinstance(simplified_boundary, MultiPolygon):
				simplified_boundary = max(simplified_boundary, key=lambda a: a.area)

			# some bounds are literally the entire globe
			# 8100 represents one quadrant of the earth
			if simplified_boundary.area > 8100:
				continue

			# round floats, way too precise by default
			rounded_boundary = shapely.wkt.loads(shapely.wkt.dumps(simplified_boundary, rounding_precision=3))

			out.write({
				'geometry': mapping(rounded_boundary),
				'properties': properties
				})
