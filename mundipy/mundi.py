import json
import urllib.parse
import io
import difflib
import inspect
from contextvars import copy_context
from contextlib import redirect_stdout

import fiona
from tqdm import tqdm
import geopandas as gpd
from shapely.ops import transform
from shapely.geometry import Polygon, MultiPolygon, LineString, Point, box
from shapely.geometry.collection import GeometryCollection
from shapely.geometry.base import BaseGeometry

from mundipy.map import Map
from mundipy.layer import Dataset
from mundipy.api.osm import grab_from_osm
from mundipy.pcs import choose_pcs, NoProjectionFoundError
from mundipy.cache import pyproj_transform
from mundipy.geometry import enrich_geom
import mundipy.geometry as geom
from mundipy.utils import _plot

class MundiQ:
    def __init__(self, center, mapdata, units='meters'):
        # a shapely object in EPSG:4326
        self.center = center

        # GeoPool
        self.mapdata = mapdata

        # list of shapely features
        self.plot_contents = []

    def call_process(self, fn):
        # pass dataset as dataframe if requested
        args = inspect.getfullargspec(fn)[0][1:]

        df_args = []
        for arg in args:
            try:
                df_args.append(self.mapdata.collections[arg])
            except KeyError:
                raise TypeError('mundi process() function requests dataset \'%s\', but no dataset was defined on Mundi' % arg)

        # call fn with a relevant context
        ctx = copy_context()
        ctx.run(lambda: _plot.set(self.plot))

        return ctx.run(fn, self.center, *df_args)

    def _bbox(self, distance=500):
        """Builds a bounding box around the center object in the local coordinate system."""

        return self.center.buffer(distance)

    def bbox(self, distance=500):
        """Builds a bounding box around the center object in WGS84."""
        return self._bbox(distance).bounds

    def plot(self, shape, name):
        """
        Plot a shape in the current MundiQ context. Shape can be
        a list of mundipy geometries or a single mundipy geometry.
        """
        if isinstance(shape, list):
            for single_shape in shape:
                self.plot(single_shape, name)

            return

        if not isinstance(shape, geom.BaseGeometry):
            raise TypeError('mundipy.plot() requires mundipy BaseGeometry but got "%s"' % type(shape))

        # fix shapes
        shape = shape.transform('EPSG:4326')._geo
        if isinstance(shape, Polygon) or isinstance(shape, MultiPolygon):
            shape = shape.buffer(0)

        # plot_contents can only contain shapely geometries
        self.plot_contents.append(shape)

class Mundi:
    def __init__(self, mapdata, main: str, units='meters'):
        self.mapdata = mapdata

        self.main = self.mapdata.collections[main]

        if units not in ['meters', 'feet']:
            raise TypeError('units passed to Mundi() was neither meters nor feet')
        self.units = units

    def plot(self, fn, element_index=0):
        if element_index < 0 or element_index > len(self.main.geometry_collection()):
            raise TypeError('element_index passed to plot() that was < 0 or > length of dataset')

        # TODO: drop duplicates, except it's very slow
        #.drop_duplicates(subset=['geometry'])
        Q = MundiQ(self.main.geometry_collection()[element_index], self.mapdata, units=self.units)

        with redirect_stdout(io.StringIO()) as f:
            res = Q.call_process(fn)

        # function passed to .q() can return None
        # for .q(), we skip it
        # gracefully handle None as plot with no features
        if res is None:
            res = dict()

        # add stdout
        res['_stdout'] = f.getvalue()
        res['_id'] = element_index

        # merge geometries into one
        geom_col = GeometryCollection(Q.plot_contents)

        return json.dumps({
            "type": "GeometryCollection",
            "geometries": geom_col.__geo_interface__['geometries'],
            "properties": { k: (int(v) if isinstance(v, int) else (float(v) if isinstance(v, float) else str(v))) for (k, v) in res.items() if not isinstance(v, BaseGeometry)}
        })

    def q(self, fn, progressbar=False, n_start=None, n_end=None):
        # make iterator unique by geometry
        # TODO: drop duplicates, except it's very slow
        unique_iterator = self.main.geometry_collection()

        res_keys = None
        res_shapely_col = 'geometry'
        res_outs = dict()
        # progressbar optional
        finiter = list(enumerate(unique_iterator))[n_start:n_end]

        if progressbar:
            finiter = tqdm(finiter, total=len(finiter))

        for idx, original_shape in finiter:
            # TODO fn(Q) can edit window

            user_printed = None

            Q = MundiQ(original_shape, self.mapdata)

            # capture stdout
            with redirect_stdout(io.StringIO()) as f:
                res = Q.call_process(fn)
            user_printed = f.getvalue()

            # if res is None, skip
            if res is None:
                continue

            # coerce to tuple
            if not isinstance(res, dict):
                raise TypeError('function passed to mundi.q() must return dict or None but instead got %s' % type(res).__name__)

            # type check that keys are always the same
            # ignores _stdout and _id
            if res_keys is None:
                res_keys = res.keys()

                for key, val in res.items():
                    res_outs[key] = []

                    if isinstance(val, BaseGeometry):
                        res_shapely_col = key

                if res_shapely_col == 'geometry':
                    res_outs['geometry'] = []

                # internal columns
                res_outs['_stdout'] = []
                res_outs['_id'] = []
            elif res_keys != res.keys():
                raise TypeError('function passed to mundi.q() returned dict with different keys')

            for key, val in res.items():
                # returned straight from mundi.q()
                # geometries should already be in EPSG:4326
                res_outs[key].append(val)

            if res_shapely_col == 'geometry':
                res_outs['geometry'].append(original_shape)

            res_outs['_stdout'].append(user_printed)
            res_outs['_id'].append(idx)

        # if res_outs is empty, give a useful error message
        # creating a GeoDataFrame with an empty array gives an error
        if len(res_outs) == 0:
            raise ValueError('all results from mundi.q() process fn were None')

        return gpd.GeoDataFrame(res_outs, crs='EPSG:4326', geometry=res_shapely_col)
