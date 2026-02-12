from django.urls import path

from . import views

urlpatterns = [
    path("", views.voice_agent, name="voice-agent"),
]
