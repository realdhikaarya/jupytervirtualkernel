from django.urls import include, path
from . import views

urlpatterns = [
    path('run-code', views.PythonCodeRunnerView.as_view()),
    ]
