from django.shortcuts import render


def voice_agent(request):
    return render(request, "voice_agent/index.html")
