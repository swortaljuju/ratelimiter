from django.urls import path

from . import views

urlpatterns = [
    path('dummy', views.index, name='dummy'),
    path('token', views.index, name='token'),
    path('leaky_token', views.index, name='leaky_token'),
    path('fixed_window', views.index, name='fixed_window'),
    path('sliding_window_log', views.index, name='sliding_window_log'),
    path('sliding_window_prorate', views.index, name='sliding_window_prorate'),
]