from django.urls import path
from .views import *

urlpatterns = [
    path("live/", live_speaking_view, name="live-speaking"),
]
