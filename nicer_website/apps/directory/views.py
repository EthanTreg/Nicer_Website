from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def directory(request: HttpRequest) -> HttpResponse:
    return render(request, 'index.html')
