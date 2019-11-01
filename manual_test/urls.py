from django.urls import path, re_path

from . import views

urlpatterns = [
    path('dummy', views.index, name='dummy'),
    re_path(r'token/.*', views.index, name='token'),
    re_path(r'leaky_token/.*', views.index, name='leaky_token'),
    re_path(r'fixed_window/.*', views.index, name='fixed_window'),
    re_path(r'sliding_window_log/.*', views.index, name='sliding_window_log'),
    re_path(
        r'sliding_window_prorate/.*',
        views.index,
        name='sliding_window_prorate'),
]
