from django.urls import path

from .views import (
    CrsCatalogView,
    ProjectListCreateView,
    ProjectMemberDetailView,
    ProjectMembersView,
)

urlpatterns = [
    path("crs-catalog", CrsCatalogView.as_view()),
    path("projects", ProjectListCreateView.as_view()),
    path("projects/<uuid:project_id>/members", ProjectMembersView.as_view()),
    path(
        "projects/<uuid:project_id>/members/<str:username>",
        ProjectMemberDetailView.as_view(),
    ),
]
