import json
import urllib.parse

from tqdm import tqdm
import geopandas as gpd
import pandas as pd
from shapely.ops import transform
from shapely.geometry import Polygon, LineString, Point, box
from shapely.geometry.base import BaseGeometry
import pyproj
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches

from mundipy.map import Map
from mundipy.layer import Layer, VisibleLayer
from mundipy.api.osm import grab_from_osm
from mundipy.pcs import choose_pcs

class MundiQ:
    def __init__(self, center, mapdata, plot_target=None, pcs=None, clip_distance=500):
        # a row in a GeoDataFrame, with a column called .geometry
        # in local projected coordinate system
        self.center = center
        # GeoPool
        self.mapdata = mapdata

        self.pcs = pcs

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

        reproject = pyproj.Transformer.from_crs(pyproj.CRS(self.pcs),
            pyproj.CRS('EPSG:4326'), always_xy=True).transform
        return transform(reproject, self._bbox(distance=distance)).bounds

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

        # check color
        if name in self.plot_legend.keys():
            color = self.plot_legend[name]
        else:
            # grab next color in list
            color = list(mcolors.CSS4_COLORS.keys())[len(self.plot_legend)]
            self.plot_legend[name] = color
            self.plot_handles.append(mpatches.Patch(color=color, label=name))

        if self.plot_target == 'geojson':
            self.plot_contents.append((shape, mcolors.CSS4_COLORS[color]))
        else:
            shape.plot(ax=self.plot_target, edgecolor='black', facecolor=color, aspect='equal', alpha=0.75)

class Mundi:
    def __init__(self, mapdata, main: str, units='meters'):
        self.mapdata = mapdata

        self.main = self.mapdata.collections[main]

        if units not in ['meters', 'feet']:
            raise TypeError('units passed to Mundi() was neither meters nor feet')

        self.pcs = choose_pcs(box(*self.main.dataframe.geometry.total_bounds), units=units)['crs']

    def plot(self, fn, clip_distance=500, output_type='matplotlib'):
        if output_type == 'geojson':
            pass
        elif output_type == 'matplotlib':
            fig, ax = plt.subplots()

        df = self.main.dataframe.drop_duplicates(subset=['geometry']).to_crs(crs=self.pcs)

        Q = MundiQ(df.iloc[1], self.mapdata, plot_target=('geojson' if output_type == 'geojson' else ax), pcs=self.pcs, clip_distance=clip_distance)
        res = fn(Q)

        if output_type == 'geojson':
            # convert to dfs
            dfs = list(map(lambda shp: gpd.GeoDataFrame(data={ 'geometry': shp[0] }, crs=self.pcs).to_crs(epsg=4326), Q.plot_contents))
            for i, df in enumerate(dfs):
                df['fill'] = Q.plot_contents[i][1]

            # 'http://geojson.io/#data=data:application/json,%s' % urllib.parse.quote(
            return gpd.GeoDataFrame(data=pd.concat(dfs)).to_json()
        elif output_type == 'matplotlib':
            ax.legend(handles=Q.plot_handles, loc='upper right')
            plt.show()

    def q(self, fn, progressbar=False):
        # make iterator unique by geometry
        unique_iterator = self.main.dataframe.drop_duplicates(subset=['geometry']).to_crs(crs=self.pcs)

        res_keys = None
        res_outs = dict()
        # progressbar optional
        finiter = list(unique_iterator.itertuples())[:20]
        if progressbar:
            finiter = tqdm(finiter, total=len(unique_iterator))

        for window in finiter:
            Q = MundiQ(window, self.mapdata, pcs=self.pcs)
            res = fn(Q)

            # coerce to tuple
            if not isinstance(res, dict):
                raise TypeError('function passed to mundi.q() must return dict but instead got %s' % type(res).__name__)

            if res_keys is None:
                res_keys = res.keys()

                for key in res.keys():
                    res_outs[key] = []
                res_outs['geometry'] = []
            elif res_keys != res.keys():
                raise TypeError('function passed to mundi.q() returned dict with different keys')

            for key, val in res.items():
                res_outs[key].append(val)
            res_outs['geometry'].append(window.geometry)

        return gpd.GeoDataFrame(res_outs, crs=self.pcs, geometry='geometry').to_crs(crs='EPSG:4326')
