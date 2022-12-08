import pytest
import json

from mundipy.dataset import Dataset
from mundipy.geometry import enrich_geom, Point, MultiPolygon, loads, dumps
import mundipy.geometry as geom

import shapely.geometry
from shapely import from_wkt, GEOSException

def test_geometry():
    df = Dataset('tests/fixtures/polygon.geojson')

    # dataset __len__
    assert len(df) == 1
    assert df.bounds == pytest.approx((-125.859375, 27.994401411046148, -81.2109375, 49.15296965617042))

    geom = list(df)

    assert len(geom) == 1
    # fictitious polygon
    assert geom[0].area == pytest.approx(7865519140303.677)
    assert geom[0]['name'] == 'example_property'

    geom[0]['name'] = 'new_name'
    assert geom[0]['name'] == 'new_name'

def test_constructor():
    pt = Point((-104.991531, 39.742043), 'EPSG:4326', { 'feat': 'test' })

    assert isinstance(pt, Point)
    assert pt.centroid.features['feat'] == 'test'
    center = pt.centroid
    assert center['feat'] == 'test'

def test_multi_polygon():
    outer = enrich_geom(shapely.geometry.Polygon([[25.273428697681624,6.026182562140747],[26.063011790518573,-7.9853706778425675],[30.13724140836942,-8.088943835912445],[30.13782361496999,6.078309828324564],[25.273428697681624,6.026182562140747]]), dict())
    inner = enrich_geom(shapely.geometry.Polygon([[18.381743157653403,-1.3600556177262746],[18.313380419378433,-4.991685343163752],[39.81788374424539,-5.007774504721652],[39.62298421833077,-0.6253503748207265],[18.381743157653403,-1.3600556177262746]]), dict())

    subbed = outer.difference(inner)

    assert isinstance(subbed, MultiPolygon)

def test_attr_error():
    pt = enrich_geom(shapely.geometry.Point(-104.991531, 39.742043), { 'feat': 'test' })

    with pytest.raises(AttributeError, match='foobar'):
        pt.foobar()

def test_project_properties():
    pt = enrich_geom(shapely.geometry.Point(-104.991531, 39.742043), { 'feat': 'test' })

    assert isinstance(pt, Point)
    assert pt.centroid.features['feat'] == 'test'
    center = pt.centroid
    assert center['feat'] == 'test'

def test_invalid_geometry_ops():
    foo = from_wkt('POLYGON((0 0, 0 1, 2 1, 2 2, 1 2, 1 0, 0 0))')
    bar = from_wkt('POLYGON((0 0, 0 1, 2 1, 2 2, 1 2, 1 0, 0 0))')

    with pytest.raises(GEOSException, match='TopologyException'):
        foo.difference(bar)

    mfoo = enrich_geom(foo, dict())
    mbar = enrich_geom(bar, dict())

    # no error
    res = mfoo.difference(mbar)
    assert res.area == 0.0

def test_local_properties():
    # an outline of the paris urban area
    paris = from_wkt('POLYGON ((2.1920900667610113 48.95792877415394, 2.154649820686018 48.89855338018583, 2.154649820686018 48.83230904559585, 2.208873625347394 48.742995477507094, 2.3005376760825698 48.70211346591506, 2.398656941658629 48.72085517951464, 2.4735374338087013 48.76682797269828, 2.572947742352227 48.811058328366954, 2.5355074962771766 48.91043410745752, 2.4051121564982623 48.99267300641242, 2.3108660198269604 49.00283746919706, 2.1920900667610113 48.95792877415394))')
    local_paris = enrich_geom(paris, dict())

    # for order of magnitude checks, a la wolfram alpha:
    # 0.65x the area of hong kong
    assert local_paris.area == pytest.approx(723011286.0469426)
    # 3.7x the large hadron colider circumference
    assert local_paris.length == pytest.approx(98778.35201223548)

def test_fast_bounds():
    paris = from_wkt('POLYGON ((2.1920900667610113 48.95792877415394, 2.154649820686018 48.89855338018583, 2.154649820686018 48.83230904559585, 2.208873625347394 48.742995477507094, 2.3005376760825698 48.70211346591506, 2.398656941658629 48.72085517951464, 2.4735374338087013 48.76682797269828, 2.572947742352227 48.811058328366954, 2.5355074962771766 48.91043410745752, 2.4051121564982623 48.99267300641242, 2.3108660198269604 49.00283746919706, 2.1920900667610113 48.95792877415394))')
    local_paris = enrich_geom(paris, dict()).as_shapely('EPSG:3949')

    mparis = enrich_geom(paris, dict())

    assert pytest.approx(paris.bounds) == mparis.bounds
    assert pytest.approx(paris.bounds) == mparis.fast_bounds

def test_benchmark_fast_bounds(benchmark):
    west_virginia = from_wkt('POLYGON ((-80.51599140389841 40.644461760355, -80.5808948469124 40.613115701987994, -80.61777180316982 40.61983395311833, -80.66202415067976 40.57279200917043, -80.62662227267194 40.53468619507322, -80.60744625541811 40.48534060098896, -80.58974531641452 40.448307579672445, -80.61187149016884 40.41686961058409, -80.62367211617142 40.39103457022384, -80.60892133366836 40.365189614967164, -80.60892133366836 40.33708602836572, -80.60302102066672 40.305596108642106, -80.61187149016884 40.28421958413122, -80.61334656841908 40.25383078582033, -80.64579828992576 40.2527050125658, -80.65612383767811 40.23131176258562, -80.68172262516738 40.17687919210766, -80.70532387717257 40.15546199595306, -80.70679895542284 40.11599157919713, -80.7200746596757 40.086655858745814, -80.74072575517977 40.04488706675983, -80.73482544217877 40.024557854722815, -80.73630052042904 39.97257789599698, -80.75695161593374 39.94318041878566, -80.758426694184 39.92055837593247, -80.79382857219113 39.92168965564116, -80.79382857219113 39.88887495633486, -80.78202794618855 39.870763567293096, -80.82480521544758 39.842454946370594, -80.82480521544758 39.808469189592586, -80.84840646745278 39.76426257643769, -80.86168217170562 39.76426257643769, -80.82362709908051 39.71718676243006, -80.83542772508312 39.69789515366884, -80.85755389883744 39.68540947375601, -80.85902897708834 39.658160152472334, -80.86935452484003 39.627491819554535, -80.91065671584883 39.614993414499565, -80.96670968936073 39.60476576790779, -80.99473617611665 39.56497722547621, -81.06111469738089 39.48760847450956, -81.14371907939848 39.41243285967181, -81.1746957226549 39.429525353359, -81.2159979136637 39.37367435771435, -81.34285464319055 39.36683238716108, -81.36203066044435 39.34630245327324, -81.47561168571836 39.41927036012774, -81.55050393379945 39.34124114242448, -81.55640424680107 39.29901872246131, -81.5637796380523 39.25905514273353, -81.63605847231752 39.26019727566265, -81.67883574157652 39.26019727566265, -81.68916128932891 39.223639793143036, -81.72603824558631 39.20078169256672, -81.7275133238372 39.15733080505632, -81.73931394983916 39.12529717993863, -81.74373918459052 39.090959265460924, -81.79094168860031 39.08637961296321, -81.80421739285315 39.0531682401423, -81.77324074959674 39.0210872599645, -81.77176567134646 38.99013823644046, -81.75889452203982 38.926908211820574, -81.82527304330405 38.93494049777337, -81.84887429530858 38.916579650506065, -81.90050203406975 38.870656744990214, -81.9108275818221 38.8809919875184, -81.90640234707074 38.93264565174738, -81.94180422507853 38.977381754003005, -81.97278086833495 38.993433978702825, -82.03178399834734 39.03469441201179, -82.07456126760638 38.96017890288908, -82.16601611912607 38.84883296417195, -82.20289307538349 38.77757194353438, -82.17634166687778 38.6636364323536, -82.17634166687778 38.601413251329916, -82.26927159664773 38.601413251329916, -82.3219755506913 38.44841372623915, -82.57120217764607 38.37624357720631, -82.6145459388554 38.14225842877096, -82.47909668507593 37.93316479269495, -82.3165575805406 37.78772884015493, -82.11067471479532 37.577625574779844, -81.96980749086435 37.5303777816862, -81.83977620723584 37.35831526616107, -81.69890898330483 37.20312094380685, -81.49844408771112 37.27644702894192, -81.3521588936292 37.310928733843966, -81.22754558015164 37.22038055734109, -80.84286969941763 37.31954669033537, -80.86454158002199 37.427187752839714, -80.73451029639347 37.38845476536406, -80.40401411717124 37.48310004025247, -80.13853357976325 37.84764898624634, -79.80803740054046 38.197632003711874, -79.6429943623957 38.56454554227909, -79.30708021302196 38.403384189744855, -78.94949418304381 38.86891459589705, -78.89531448153204 38.79294387021898, -78.49438469034402 39.12576752163412, -78.3480994962621 39.33141618616489, -78.35351746641304 39.45702595523906, -77.80630248114308 39.12576752163412, -77.74128683932885 39.310459242201375, -77.83881030205052 39.54064012075267, -78.01760331703929 39.63249949476602, -78.23432212308698 39.640844307689434, -78.43478701868071 39.615806848786946, -78.49438469034402 39.52392533472889, -78.75986522775199 39.60745901584221, -78.93324027258983 39.44447515621607, -79.09036140697421 39.46120905215207, -79.46420134740634 39.142577751684996, -79.48045537877665 39.67713119178032, -80.5369595582582 39.71465067829291, -80.51599140389841 40.644461760355))')

    local_wv = enrich_geom(west_virginia, dict()).as_shapely('EPSG:32151')

    def wrapper():
        # this is a cached property, regenerate
        wv = enrich_geom(local_wv, dict(), pcs='EPSG:32151')
        return wv.fast_bounds

    # benchmark something
    result = benchmark(wrapper)

    # distortion due to projection
    closest_realistic_bounds = enrich_geom(local_wv, dict(), pcs='EPSG:32151').as_shapely('EPSG:4326').bounds

    # very generous bound, unfortunately it's needed
    assert result == pytest.approx(closest_realistic_bounds, 0.1)


def test_loads_dumps():
    with open('tests/fixtures/polygon.geojson', 'r') as f:
        res = loads(json.loads(f.read()))

        assert len(res) == 1
        assert res[0]['name'] == 'example_property'
        assert len(res[0].exterior.coords) == 6

    assert json.dumps(dumps(res)) == '{"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-125.859375, 49.03786794532644], [-125.5078125, 30.600093873550072], [-83.14453125, 27.994401411046148], [-81.2109375, 42.68243539838623], [-92.46093749999999, 49.15296965617042], [-125.859375, 49.03786794532644]]]}, "properties": {"name": "example_property"}}]}'
