import json
import urllib.parse

from tqdm import tqdm
import geopandas as gpd
import pandas as pd
from shapely.ops import transform
from shapely.geometry import Polygon, LineString, Point, box
from shapely.geometry.base import BaseGeometry
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches

from mundipy.map import Map
from mundipy.layer import Layer, VisibleLayer
from mundipy.api.osm import grab_from_osm
from mundipy.pcs import choose_pcs
from mundipy.cache import pyproj_transform

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

    """ Returns a VisibleLayer. """
    def __call__(self, *args):
        # variable length arguments
        dataset = args[0] if len(args) > 0 else None

        # First, if it's just Q(), give the center.
        if dataset == None:
            return self.center

        # Next, if dataset is in the pool, return the
        # VisibleLayer
        if dataset in self.mapdata.collections.keys():
            return VisibleLayer(self.mapdata.collections[dataset], self.bbox(), self.center.geometry, pcs=self.pcs)

        if dataset == 'openstreetmap' or dataset == 'osm':
            # Take either a tuple, or a list of tuples
            if len(args) <= 1:
                raise TypeError('openstreetmap Q() takes at least two arguments')

            # build bounding box in WGS84
            p1, p2, p3, p4 = self.bbox()

            gdf = grab_from_osm(tups=args[1], bbox=('%f,%f,%f,%f' % (p2, p1, p4, p3)))
            # convert to local CRS, because grab_from_osm gives WGS84
            return VisibleLayer(Layer(gdf), self.bbox(), self.center.geometry, pcs=self.pcs)

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
        if isinstance(shape, Polygon):
            shape = gpd.GeoSeries([shape])
        elif isinstance(shape, gpd.GeoDataFrame):
            shape = shape.geometry
        elif isinstance(shape, pd.Series) and isinstance(shape.geometry, BaseGeometry):
            shape = gpd.GeoSeries([shape.geometry])
        elif isinstance(shape, pd.Series) and isinstance(shape.geometry, gpd.GeoSeries):
            shape = shape.geometry
        elif isinstance(shape, VisibleLayer):
            shape = shape.local_collection
        else:
            raise TypeError('unexpected type passed to plot(), got %s' % type(shape))

        # fix self-intersections and such
        shape = shape.buffer(0)

        # clip shape by bounding box
        # especially nearby roads make the plot unreadable
        #
        shape = gpd.clip(shape, mask=self._bbox(distance=self.clip_distance))

        # LineString and Point won't show up when plotted; buffer
        shape = shape.apply(lambda g: g.buffer(2) if isinstance(g, LineString) or isinstance(g, Point) else g)

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
        res = fn(Q)

        if output_type == 'geojson':
            # convert to dfs
            dfs = gpd.GeoDataFrame(data=Q.plot_contents, crs='EPSG:4326', columns=['geometry', 'fill'], geometry='geometry')

            # 'http://geojson.io/#data=data:application/json,%s' % urllib.parse.quote(
            return dfs.to_json()
        elif output_type == 'matplotlib':
            ax.legend(handles=Q.plot_handles, loc='upper right')
            plt.show()

    def q(self, fn, progressbar=False, n=0):
        # make iterator unique by geometry
        # TODO: drop duplicates, except it's very slow
        unique_iterator = self.main.dataframe

        res_keys = None
        res_outs = dict()
        # progressbar optional
        finiter = list(unique_iterator.iterrows())
        if progressbar:
            finiter = tqdm(finiter, total=min(n, len(unique_iterator)))

        for idx, window in finiter:
            # fn(Q) can edit window
            original_shape = window.geometry

            Q = MundiQ(window, self.mapdata)
            res = fn(Q)

            # if res is None, skip
            if res is None:
                continue

            # coerce to tuple
            if not isinstance(res, dict):
                raise TypeError('function passed to mundi.q() must return dict or None but instead got %s' % type(res).__name__)

            if res_keys is None:
                res_keys = res.keys()

                for key in res.keys():
                    res_outs[key] = []
                res_outs['geometry'] = []
            elif res_keys != res.keys():
                raise TypeError('function passed to mundi.q() returned dict with different keys')

            for key, val in res.items():
                res_outs[key].append(val)
            res_outs['geometry'].append(original_shape)

            # check n
            if n > 0 and len(res_outs['geometry']) == n:
                break

        return gpd.GeoDataFrame(res_outs, crs='EPSG:4326', geometry='geometry')
