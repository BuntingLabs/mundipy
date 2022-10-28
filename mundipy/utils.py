from contextvars import ContextVar
import math

_plot = ContextVar('mundipy_plot', default=None)

def plot(*args, **kwargs):
    plot_fn = _plot.get()
    if plot_fn is None:
        raise TypeError('mundipy.utils.plot() called outside of process fn')

    # pass onto actual plotting function in mundi.py
    return plot_fn(*args, **kwargs)
