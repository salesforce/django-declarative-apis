from django.test import TestCase
from django_declarative_apis import models

from myapp.models import User


class ModelsTestCase(TestCase):
    def test_create_user(self):
        consumer = models.OauthConsumer.objects.create(name="smith")

        user = User(consumer=consumer, name="smith")
        user.save()

        self.assertEqual(user.consumer.content_type_id, consumer.content_type_id)
        self.assertEqual(user.consumer.id, consumer.id)
        self.assertEqual(user.consumer.key, consumer.key)
        self.assertEqual(user.consumer.name, consumer.name)
        self.assertEqual(user.consumer.object_id, consumer.object_id)
        self.assertEqual(user.consumer.secret, consumer.secret)
        self.assertEqual(user.consumer.type, consumer.type)
        self.assertEqual(user.name, "smith")
