from django.urls import path

from .views import (
    CrsCatalogView,
    ProjectDetailView,
    ProjectListCreateView,
    ProjectMemberDetailView,
    ProjectMembersView,
    ProjectRestoreView,
    RecentlyDeletedView,
)

urlpatterns = [
    path("crs-catalog", CrsCatalogView.as_view()),
    path("projects", ProjectListCreateView.as_view()),
    path("deleted", RecentlyDeletedView.as_view()),
    path("projects/<uuid:project_id>", ProjectDetailView.as_view()),
    path("projects/<uuid:project_id>/restore", ProjectRestoreView.as_view()),
    path("projects/<uuid:project_id>/members", ProjectMembersView.as_view()),
    path(
        "projects/<uuid:project_id>/members/<str:username>",
        ProjectMemberDetailView.as_view(),
    ),
]
