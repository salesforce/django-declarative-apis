from django.http import HttpResponse

from django_declarative_apis.machinery import EndpointDefinition, field


class SimpleEndpointDefinition(EndpointDefinition):
    def is_authorized(self):
        return True

    int_type_field = field(type=int)

    @property
    def resource(self):
        return {}
