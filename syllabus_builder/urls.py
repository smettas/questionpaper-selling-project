from django.urls import path
from . import views

app_name = "syllabus_builder"
urlpatterns = [
    path("counts/", views.counts, name="counts"),
    path("sample/", views.sample, name="sample"),
    path("details/", views.details, name="details"),
    path("report/", views.report, name="report"),
]
