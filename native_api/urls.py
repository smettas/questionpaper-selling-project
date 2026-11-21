from django.urls import path
from .views import login, endpoint
urlpatterns = [path('login/', login), path('<str:action>/', endpoint)]
