import collections
from spillway.compat import json


class LinkedCRS(dict):
    def __init__(self, srid=4326, iterable=(), **kwargs):
        self['type'] = 'link'
        properties = {}
        properties['href'] = 'http://spatialreference.org/ref/epsg/%s/proj4/' % srid
        properties['type'] = 'proj4'
        self['properties'] = properties
        self.update(iterable, **kwargs)


class Feature(dict):
    """GeoJSON Feature dict."""

    def __init__(self, id=None, geometry=None, properties=None,
                 crs=None, iterable=(), **kwargs):
        super(Feature, self).__init__()
        self['type'] = self.__class__.__name__
        self['id'] = id
        self['geometry'] = geometry or {}
        self['properties'] = properties or {}
        if crs and not isinstance(crs, LinkedCRS):
            self['crs'] = LinkedCRS(crs)
        self.update(iterable, **kwargs)

    @property
    def __geo_interface__(self):
        return self

    def __str__(self):
        geom = self['geometry'] or '{}'
        if isinstance(geom, dict):
            return json.dumps(self)
        keys = self.viewkeys() - {'geometry'}
        props = json.dumps({k: self[k] for k in keys})[1:-1]
        feature = '{"geometry": %s, %s}' % (geom, props)
        return feature


class FeatureCollection(dict):
    """GeoJSON FeatureCollection dict."""

    def __init__(self, features=None, crs=None, iterable=(), **kwargs):
        super(FeatureCollection, self).__init__()
        self['type'] = self.__class__.__name__
        if crs and not isinstance(crs, LinkedCRS):
            self['crs'] = LinkedCRS(crs)
        if features and not isinstance(features[0], Feature):
            self['features'] = [Feature(**feat) for feat in features]
        else:
            self['features'] = features or []
        self.update(iterable, **kwargs)

    @property
    def __geo_interface__(self):
        return self

    def __str__(self):
        features = ','.join(map(str, self['features']))
        keys = self.viewkeys() - {'features'}
        collection = '%s, "features": [' % json.dumps(
                {k: self[k] for k in keys})[:-1]
        return ''.join([collection, features, ']}'])
