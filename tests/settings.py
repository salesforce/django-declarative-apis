import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'db.sqlite3'
    }
}

SECRET_KEY = 'NOT A REAL KEY'

DEBUG = True

INSTALLED_APPS = [
    'django_declarative_apis',
    'django.contrib.contenttypes',
    'tests',
]

ROOT_URLCONF = 'tests.urls'

TEST_RUNNER = 'tests.testutils.NoLoggingTestRunner'

MIDDLEWARE_CLASSES = []

REQUIRE_HTTPS_FOR_OAUTH = False

DECLARATIVE_ENDPOINT_RESOURCE_ADAPTER = 'django_declarative_apis.adapters.EndpointResource'
DECLARATIVE_ENDPOINT_DEFAULT_FILTERS = 'tests.filters.DEFAULT_FILTERS'
DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS = (
    (
        (None, 'django_declarative_apis.authentication.oauthlib.oauth1.TwoLeggedOauth1Hint',),
        'django_declarative_apis.authentication.oauthlib.oauth1.TwoLeggedOauth1',
    ),
)
