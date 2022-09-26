from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from .models import Directory


def directory(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        'directory/directory.html',
        {'directories': Directory.objects.all()}
    )


def files(request: HttpRequest, directory) -> HttpResponse:
    current_dir = Directory.objects.get(name=directory)
    return render(request, 'directory/files.html', {
        'directory': current_dir.name,
        'sub_dirs': current_dir.directories,
        'files': current_dir.files.all(),
    })
