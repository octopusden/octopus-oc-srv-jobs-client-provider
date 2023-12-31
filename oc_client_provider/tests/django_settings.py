from django.conf import settings
import django
import os

if not settings.configured:
    if not os.path.isdir('/tmp'):
        os.makedirs('/tmp')

    settings.configure(
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': '/tmp/test.db',
                    }},
                USE_TZ=True,
                TIME_ZONE='Europe/Belgrade',
                INSTALLED_APPS=[
                    'oc_delivery_apps.dlcontents',
                    'oc_delivery_apps.checksums',
                    'oc_delivery_apps.dlmanager',
                    'django.contrib.contenttypes',
                    'django.contrib.auth'],
                LANGUAGE_CODE='en-us',
                USE_I18N=True,
                USE_L10N=True)

    django.setup()
