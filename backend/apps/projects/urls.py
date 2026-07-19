from django.urls import path

from .views import CrsCatalogView, ProjectListCreateView

urlpatterns = [
    path("crs-catalog", CrsCatalogView.as_view()),
    path("projects", ProjectListCreateView.as_view()),
]
