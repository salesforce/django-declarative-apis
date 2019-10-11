from django.db import models
import django_declarative_apis.models

class User(models.Model):
    consumer = models.ForeignKey(django_declarative_apis.models.OauthConsumer)
    name = models.CharField(max_length=50, null=False, blank=False)
