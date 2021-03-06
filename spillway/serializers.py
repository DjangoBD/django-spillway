from django.core import exceptions
from django.contrib.gis.db import models
from rest_framework import renderers, serializers
from greenwich.srs import SpatialReference
import numpy as np

from spillway import query, collections as sc
from spillway.fields import GeometryField
from spillway.renderers.gdal import BaseGDALRenderer

serializers.ModelSerializer.serializer_field_mapping.update({
    models.GeometryField: GeometryField,
    models.PointField: GeometryField,
    models.LineStringField: GeometryField,
    models.PolygonField: GeometryField,
    models.MultiPointField: GeometryField,
    models.MultiLineStringField: GeometryField,
    models.MultiPolygonField: GeometryField,
    models.GeometryCollectionField: GeometryField
})


class GeoModelSerializer(serializers.ModelSerializer):
    """Serializer class for GeoModels."""

    def __new__(cls, *args, **kwargs):
        cls.Meta.geom_field = getattr(cls.Meta, 'geom_field', None)
        return super(GeoModelSerializer, cls).__new__(cls, *args, **kwargs)

    def get_fields(self):
        """Returns a fields dict for this serializer with a 'geometry' field
        added.
        """
        fields = super(GeoModelSerializer, self).get_fields()
        # Set the geometry field name when it's undeclared.
        if not self.Meta.geom_field:
            for name, field in fields.items():
                if isinstance(field, GeometryField):
                    self.Meta.geom_field = name
                    break
        # Alter geometry field source based on the requested format.
        try:
            renderer = self.context['request'].accepted_renderer
        except (AttributeError, KeyError):
            pass
        else:
            geom_field = fields.get(self.Meta.geom_field)
            obj = getattr(self.context.get('view'), 'queryset', self.instance)
            if geom_field and hasattr(obj, renderer.format):
                geom_field.source = renderer.format
        return fields


class FeatureListSerializer(serializers.ListSerializer):
    """Feature list serializer for GeoModels."""

    @property
    def data(self):
        return super(serializers.ListSerializer, self).data

    def to_representation(self, data):
        data = map(self.child.to_representation, data)
        try:
            srid = query.get_srid(self.instance)
        except AttributeError:
            srid = None
        return sc.FeatureCollection(features=data, crs=srid)


class FeatureSerializer(GeoModelSerializer):
    """Feature serializer for GeoModels."""

    @classmethod
    def many_init(cls, *args, **kwargs):
        kwargs['child'] = cls()
        meta = getattr(cls, 'Meta', None)
        list_serializer_cls = getattr(
            meta, 'list_serializer_cls', FeatureListSerializer)
        return list_serializer_cls(*args, **kwargs)

    @property
    def data(self):
        if not hasattr(self, '_data'):
            self._data = super(FeatureSerializer, self).data
            if 'crs' not in self._data:
                geom = getattr(self.instance, self.Meta.geom_field, None)
                if geom and geom.srid:
                    self._data['crs'] = sc.NamedCRS(geom.srid)
        return self._data

    def to_representation(self, instance):
        native = super(FeatureSerializer, self).to_representation(instance)
        geometry = native.pop(self.Meta.geom_field)
        pk = native.pop(instance._meta.pk.name, None)
        return sc.Feature(pk, geometry, native)

    def to_internal_value(self, data):
        if sc.has_features(data):
            for feat in data['features']:
                return self.to_internal_value(feat)
        try:
            sref = SpatialReference(data['crs']['properties']['name'])
        except KeyError:
            sref = None
        # Force evaluation of fields property.
        if not self.fields and self.Meta.geom_field is None:
            raise exceptions.FieldDoesNotExist('Geometry field not found')
        record = {self.Meta.geom_field: data.get('geometry')}
        record.update(data.get('properties', {}))
        feature = super(FeatureSerializer, self).to_internal_value(record)
        if feature and sref:
            geom = feature[self.Meta.geom_field]
            geom.srid = sref.srid
        return feature


class RasterModelSerializer(GeoModelSerializer):
    """Serializer class for raster models."""

    def __new__(cls, *args, **kwargs):
        cls.Meta.raster_field = getattr(cls.Meta, 'raster_field', None)
        return super(RasterModelSerializer, cls).__new__(cls, *args, **kwargs)

    def get_fields(self):
        fields = super(RasterModelSerializer, self).get_fields()
        if not self.Meta.raster_field:
            for name, field in fields.items():
                if isinstance(field, serializers.FileField):
                    self.Meta.raster_field = name
                    break
        fieldname = self.Meta.raster_field
        request = self.context.get('request')
        renderer = getattr(request, 'accepted_renderer', None)
        if (isinstance(renderer, BaseGDALRenderer)
                or (isinstance(renderer, renderers.JSONRenderer)
                and 'g' in request.GET)):
            fields[fieldname] = serializers.ReadOnlyField()
        return fields
