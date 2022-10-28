import json
import urllib.parse
import difflib
import inspect
from contextvars import copy_context

import fiona
from tqdm import tqdm
import geopandas as gpd
import pandas as pd
from shapely.ops import transform
from shapely.geometry import Polygon, MultiPolygon, LineString, Point, box
from shapely.geometry.base import BaseGeometry
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches

from mundipy.map import Map
from mundipy.layer import Dataset, LayerView
from mundipy.api.osm import grab_from_osm
from mundipy.pcs import choose_pcs, NoProjectionFoundError
from mundipy.cache import pyproj_transform
from mundipy.geometry import from_row_series
from mundipy.utils import _plot, sanitize_geo

class MundiQ:
    def __init__(self, center, mapdata, plot_target=None, units='meters', clip_distance=500):
        self.pcs = choose_pcs(box(*center.geometry.bounds), units=units)['crs']

        # a row in a GeoDataFrame, with a column called .geometry
        # in local projected coordinate system
        self.center = center

        to_local = pyproj_transform('EPSG:4326', self.pcs)
        self.center.geometry = transform(to_local, self.center.geometry)

        # GeoPool
        self.mapdata = mapdata

        # could be matplotlib axes or 'geojson'
        self.plot_target = plot_target
        self.plot_legend = dict()
        self.plot_handles = []
        self.plot_contents = []

        if not isinstance(clip_distance, float) and not isinstance(clip_distance, int):
            raise TypeError('clip_distance to mundi.plot() must be float or int')
        self.clip_distance = clip_distance

    def call_process(self, fn):
        # pass dataset as dataframe if requested
        args = inspect.getfullargspec(fn)[0][1:]

        df_args = []
        for arg in args:
            try:
                df_args.append(LayerView(self.mapdata.collections[arg], self.pcs))
            except KeyError:
                raise TypeError('mundi process() function requests dataset \'%s\', but no dataset was defined on Mundi' % arg)

        center = from_row_series(self.center)

        # call fn with a relevant context
        ctx = copy_context()
        ctx.run(lambda: _plot.set(self.plot))

        return ctx.run(fn, center, *df_args)

    def _bbox(self, distance=500):
        """Builds a bounding box around the center object in the local coordinate system."""

        return self.center.geometry.buffer(distance)

    def bbox(self, distance=500):
        """Builds a bounding box around the center object in WGS84."""
        to_wgs = pyproj_transform(self.pcs, 'EPSG:4326')
        return transform(to_wgs, self._bbox(distance=distance)).bounds

    def plot(self, shape, name):
        if self.plot_target is None:
            return

        # coerce shape into a GeoSeries, no matter what it is
        # shape can literally be anything
        if isinstance(shape, Point) or isinstance(shape, Polygon) or isinstance(shape, MultiPolygon) or isinstance(shape, LineString):
            shape = gpd.GeoSeries([shape])
        elif isinstance(shape, gpd.GeoDataFrame):
            shape = shape.geometry
        elif isinstance(shape, pd.Series) and isinstance(shape.geometry, BaseGeometry):
            shape = gpd.GeoSeries([shape.geometry])
        elif isinstance(shape, pd.Series) and isinstance(shape.geometry, gpd.GeoSeries):
            shape = shape.geometry
        elif isinstance(shape, list):
            shape = gpd.GeoSeries(shape)
        else:
            raise TypeError('unexpected type passed to plot(), got %s' % type(shape))

        # clip shape by bounding box
        # especially nearby roads make the plot unreadable
        if self.clip_distance > 0:
            shape = gpd.clip(shape, mask=self._bbox(distance=self.clip_distance))

        # LineString and Point won't show up when plotted; buffer
        # 10 feet and meters should be, fine, i guess
        shape = shape.apply(lambda g: g.buffer(10) if isinstance(g, LineString) or isinstance(g, Point) else g.buffer(0))

        # convert to WGS84
        shape = shape.set_crs(crs=self.pcs).to_crs(epsg=4326)

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

    def plot(self, fn, element_index=0, clip_distance=500, output_type='matplotlib'):
        if output_type == 'geojson':
            pass
        elif output_type == 'matplotlib':
            fig, ax = plt.subplots()

        if element_index < 0 or element_index > len(self.main.dataframe):
            raise TypeError('element_index passed to plot() that was < 0 or > length of dataset')

        # TODO: drop duplicates, except it's very slow
        #.drop_duplicates(subset=['geometry'])
        Q = MundiQ(self.main.dataframe.iloc[element_index], self.mapdata, plot_target=('geojson' if output_type == 'geojson' else ax), units=self.units, clip_distance=clip_distance)
        res = Q.call_process(fn)

        if output_type == 'geojson':
            # convert to dfs
            dfs = gpd.GeoDataFrame(data=Q.plot_contents, crs='EPSG:4326', columns=['geometry', 'fill'], geometry='geometry')

            # sanitize object before dumping to json
            return json.dumps(sanitize_geo(dfs.__geo_interface__))
        elif output_type == 'matplotlib':
            ax.legend(handles=Q.plot_handles, loc='upper right')
            plt.show()

    def q(self, fn, progressbar=False, n_start=None, n_end=None):
        # make iterator unique by geometry
        # TODO: drop duplicates, except it's very slow
        unique_iterator = self.main.dataframe

        res_keys = None
        res_shapely_col = 'geometry'
        res_outs = dict()
        # progressbar optional
        finiter = list(unique_iterator.iterrows())[n_start:n_end]

        if progressbar:
            finiter = tqdm(finiter, total=len(finiter))

        for idx, window in finiter:
            # fn(Q) can edit window
            original_shape = window.geometry

            try:
                Q = MundiQ(window, self.mapdata)
                res = Q.call_process(fn)
            except NoProjectionFoundError:
                continue

            # if res is None, skip
            if res is None:
                continue

            # coerce to tuple
            if not isinstance(res, dict):
                raise TypeError('function passed to mundi.q() must return dict or None but instead got %s' % type(res).__name__)

            if res_keys is None:
                res_keys = res.keys()

                for key, val in res.items():
                    res_outs[key] = []

                    if isinstance(val, BaseGeometry):
                        res_shapely_col = key

                if res_shapely_col == 'geometry':
                    res_outs['geometry'] = []
            elif res_keys != res.keys():
                raise TypeError('function passed to mundi.q() returned dict with different keys')

            for key, val in res.items():
                # returned straight from mundi.q()
                # will need to translate from local PCS to WGS84
                # if this is the geometry column
                if key == res_shapely_col:
                    to_wgs = pyproj_transform(Q.pcs, 'EPSG:4326')
                    geodetic_out = transform(to_wgs, val)

                    res_outs[key].append(geodetic_out)
                else:
                    res_outs[key].append(val)

            if res_shapely_col == 'geometry':
                res_outs['geometry'].append(original_shape)

        # if res_outs is empty, give a useful error message
        # creating a GeoDataFrame with an empty array gives an error
        if len(res_outs) == 0:
            raise ValueError('all results from mundi.q() process fn were None')

        return gpd.GeoDataFrame(res_outs, crs='EPSG:4326', geometry=res_shapely_col)
