from contextvars import ContextVar
import math

import pandas as pd

_plot = ContextVar('mundipy_plot', default=None)

def plot(*args, **kwargs):
    plot_fn = _plot.get()
    if plot_fn is None:
        raise TypeError('mundipy.utils.plot() called outside of process fn')

    # pass onto actual plotting function in mundi.py
    return plot_fn(*args, **kwargs)

def sanitize_geo(value):
    """Sanitize a __geo_interface__ for dumping to JSON."""
    if isinstance(value, dict):
        value = {sanitize_geo(k): sanitize_geo(v) for k, v in value.items()}
    elif isinstance(value, list):
        value = [sanitize_geo(v) for v in value]
    elif isinstance(value, pd.Timestamp):
        value = str(value)
    elif isinstance(value, float) and math.isnan(value):
        value = None
    return value
