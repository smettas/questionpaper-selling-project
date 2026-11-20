from django.urls import path
from . import views
app_name = "test_patterns"
urlpatterns = [
    path("catalog/", views.catalog, name="catalog"),
    path("generate/", views.generate, name="generate"),
    path("replace/", views.replace, name="replace"),
]
