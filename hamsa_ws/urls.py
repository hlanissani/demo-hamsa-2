from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", include("voice_agent.urls")),
    path("health/", health),
]
