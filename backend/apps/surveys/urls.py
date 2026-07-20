from django.urls import path

from .views_hooks import TusdHookView
from .views_options import ProcessingOptionsView
from .views_surveys import (
    ProjectSurveysView,
    SurveyArtifactsView,
    SurveyDetailView,
    SurveyProcessView,
    SurveyRestoreView,
    SurveyRetryView,
)
from .views_uploads import ProjectUploadsView

urlpatterns = [
    path("processing-options", ProcessingOptionsView.as_view()),
    path("projects/<uuid:project_id>/uploads", ProjectUploadsView.as_view()),
    path("projects/<uuid:project_id>/surveys", ProjectSurveysView.as_view()),
    path("surveys/<uuid:survey_id>", SurveyDetailView.as_view()),
    path("surveys/<uuid:survey_id>/restore", SurveyRestoreView.as_view()),
    path("surveys/<uuid:survey_id>/retry", SurveyRetryView.as_view()),
    path("surveys/<uuid:survey_id>/process", SurveyProcessView.as_view()),
    path("surveys/<uuid:survey_id>/artifacts", SurveyArtifactsView.as_view()),
    path("hooks/tusd", TusdHookView.as_view()),
]
