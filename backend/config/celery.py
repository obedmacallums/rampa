import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("rampa")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["apps.surveys"], related_name="tasks")
app.autodiscover_tasks(["apps.surveys"], related_name="tasks_maintenance")
