from contextvars import ContextVar

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
        value = {sanitize(k): sanitize(v) for k, v in value.items()}
    elif isinstance(value, list):
        value = [sanitize(v) for v in value]
    elif isinstance(value, pd.Timestamp):
        value = str(value)
    return value
