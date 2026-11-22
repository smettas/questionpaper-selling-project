from django.urls import path
from . import views
urlpatterns=[path('',views.home,name='faculty-home'),path('logout/',views.logout),path('api/<str:action>/',views.api)]
