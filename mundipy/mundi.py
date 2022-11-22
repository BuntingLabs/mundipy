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
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches

from mundipy.map import Map
from mundipy.layer import Dataset
from mundipy.api.osm import grab_from_osm
from mundipy.pcs import choose_pcs, NoProjectionFoundError
from mundipy.cache import pyproj_transform
from mundipy.geometry import enrich_geom
import mundipy.geometry as geom
from mundipy.utils import _plot

class MundiQ:
    def __init__(self, center, mapdata, plot_target=None, units='meters'):
        # a shapely object in EPSG:4326
        self.center = center

        # GeoPool
        self.mapdata = mapdata

        # could be matplotlib axes or 'geojson'
        self.plot_target = plot_target
        self.plot_legend = dict()
        self.plot_handles = []
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
        if self.plot_target is None:
            return

        # coerce shape into a GeoSeries, no matter what it is
        # shape can literally be anything
        if isinstance(shape, Point) or isinstance(shape, Polygon) or isinstance(shape, MultiPolygon) or isinstance(shape, LineString):
            shape = gpd.GeoSeries([shape])
        # convert from our geom first
        elif isinstance(shape, geom.Point) or isinstance(shape, geom.Polygon) or isinstance(shape, geom.MultiPolygon) or isinstance(shape, geom.LineString):
            shape = gpd.GeoSeries([shape._geo])
        elif isinstance(shape, gpd.GeoDataFrame):
            shape = shape.geometry
        elif isinstance(shape, list):
            shape = gpd.GeoSeries(shape)
        else:
            raise TypeError('unexpected type passed to plot(), got %s' % type(shape))

        # fix shapes
        shape = shape.apply(lambda g: g.buffer(0) if isinstance(g, Polygon) or isinstance(g, MultiPolygon) else g)

        # check color
        if name in self.plot_legend.keys():
            color = self.plot_legend[name]
        else:
            # grab next color in list
            color = list(mcolors.CSS4_COLORS.keys())[len(self.plot_legend)]
            self.plot_legend[name] = color
            self.plot_handles.append(mpatches.Patch(color=color, label=name))

        if self.plot_target == 'geojson':
            # plot_contents can only contain shapely geometries
            for idx, row in shape.items():
                self.plot_contents.append((row, mcolors.CSS4_COLORS[color]))
        else:
            shape.plot(ax=self.plot_target, edgecolor='black', facecolor=color, aspect='equal', alpha=0.75)

class Mundi:
    def __init__(self, mapdata, main: str, units='meters'):
        self.mapdata = mapdata

        self.main = self.mapdata.collections[main]

        if units not in ['meters', 'feet']:
            raise TypeError('units passed to Mundi() was neither meters nor feet')
        self.units = units

    def plot(self, fn, element_index=0, output_type='matplotlib'):
        if output_type == 'geojson':
            pass
        elif output_type == 'matplotlib':
            fig, ax = plt.subplots()

        if element_index < 0 or element_index > len(self.main.geometry_collection()):
            raise TypeError('element_index passed to plot() that was < 0 or > length of dataset')

        # TODO: drop duplicates, except it's very slow
        #.drop_duplicates(subset=['geometry'])
        Q = MundiQ(self.main.geometry_collection()[element_index], self.mapdata, plot_target=('geojson' if output_type == 'geojson' else ax), units=self.units)

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

        if output_type == 'geojson':
            # merge geometries into one
            geom_col = GeometryCollection([r[0] for r in Q.plot_contents])

            return json.dumps({
                "type": "GeometryCollection",
                "geometries": geom_col.__geo_interface__['geometries'],
                "properties": { k: (int(v) if isinstance(v, int) else (float(v) if isinstance(v, float) else str(v))) for (k, v) in res.items() if not isinstance(v, BaseGeometry)}
            })

        elif output_type == 'matplotlib':
            ax.legend(handles=Q.plot_handles, loc='upper right')
            plt.show()

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
