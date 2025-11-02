from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alx_travel_app.settings')

app = Celery('alx_travel_app')

# Load config from Django settings, using namespace CELERY
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover tasks in Django apps
app.autodiscover_tasks()
