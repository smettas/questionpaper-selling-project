from django.contrib import admin
from django.db import connection
from django.db.utils import DatabaseError
from django.http import HttpResponse
from django.urls import path

from paper_builder import views
from question_bank.upload import import_questions


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return HttpResponse("Database unavailable", status=503)
    return HttpResponse("OK")


urlpatterns = [
    path("", views.builder, name="builder"),
    path("questions/", views.browse_questions, name="browse-questions"),
    path("questions/<int:pk>/<str:kind>/", views.question_asset, name="question-asset"),
    path("download/", views.download, name="download"),
    path("health/", health, name="health"),
    path("admin/import-questions/", admin.site.admin_view(import_questions), name="import_questions"),
    path("admin/", admin.site.urls),
]
