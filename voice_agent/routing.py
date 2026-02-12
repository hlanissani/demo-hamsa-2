from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/agent/<str:session_id>/", consumers.VoiceAgentConsumer.as_asgi()),
    path("ws/agent/", consumers.VoiceAgentConsumer.as_asgi()),
]
