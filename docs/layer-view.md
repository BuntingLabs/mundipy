<a id="mundipy.layer"></a>

# mundipy.layer

`Dataset`s and `LayerView`s form the core abstractions in mundipy.

`Dataset` comprises any source for vector data. Instantiating a
`Dataset` declares its accessibility, but does not automatically
load features, as all features are lazily loaded.

`LayerView` represents a collection of vector features, typically
a subset from a `Dataset`. This makes queries like intersection
and nearest much faster because only a subset of the `Dataset`
must be loaded.

<a id="mundipy.layer.Dataset"></a>

## Dataset Objects

```python
class Dataset()
```

A Dataset represents a source of vector features.

	from mundipy.layer import Dataset

	src = Dataset({
 		'url': 'postgresql://postgres@localhost:5432/postgres',
		'table': 'table_name'
	})

<a id="mundipy.layer.Dataset.__init__"></a>

#### \_\_init\_\_

```python
def __init__(data)
```

Initialize a Dataset from a data source.

<a id="mundipy.layer.Dataset.dataframe"></a>

#### dataframe

```python
@property
def dataframe()
```

Load an entire Dataset as a dataframe.

<a id="mundipy.layer.LayerView"></a>

## LayerView Objects

```python
class LayerView()
```

`LayerView` represents a collection of vector features in
a single dataset. It implements an `Iterable` interface,
allowing for one to loop through all features in the dataset,
or smart filtering without loading the entire dataset into
memory.

<a id="mundipy.layer.LayerView.__iter__"></a>

#### \_\_iter\_\_

```python
def __iter__()
```

Iterate through all items of the dataset.

<a id="mundipy.layer.LayerView.intersects"></a>

#### intersects

```python
def intersects(geom)
```

Returns an `Iterator` of mundipy geometries that intersect
		with `geom`.

		`geom`: inherits from `shapely.geometry`

        from mundipy.utils import plot

        for feat in layer.intersects(Point(-37.0, 42.1)):
            plot(feat)

<a id="mundipy.layer.LayerView.nearest"></a>

#### nearest

```python
def nearest(geom)
```

Returns the nearest feature in this collection to the passed
geometry.

Returns `None` if the dataset has no features.

`geom`: inherits from `shapely.geometry`

