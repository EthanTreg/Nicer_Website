from django.shortcuts import render
from django.core.serializers import serialize
from django.http import HttpRequest, HttpResponse, JsonResponse

from .models import Item


def dir_file_fetcher(items, start, end):
    dirs = items.filter(type=Item.item_type[0][0]).order_by('name')[start:end]
    files = items.filter(type=Item.item_type[1][0]).order_by('name')[start:end]
    return dirs, files


def index(request: HttpRequest) -> HttpResponse:
    items = Item.objects.filter(path=Item._meta.get_field('path').get_default()).order_by('type')
    dirs, files = dir_file_fetcher(items, 0, 5)

    return render(
        request,
        'file_mgr/directory.html', {
            'current_dir': 'Root',
            'dirs': dirs,
            'files': files,
        })


def directory(request: HttpRequest, path) -> HttpResponse:
    if path:
        path += '/'

    sub_items = Item.objects.filter(path=path).order_by('type')
    sub_dirs, sub_files = dir_file_fetcher(sub_items, 0, 5)
    parent_path = '/'.join(path.split('/')[:-1])

    return render(
        request,
        'file_mgr/directory.html', {
            'current_dir': path,
            'dirs': sub_dirs,
            'files': sub_files,
            'parent_path': parent_path,
        })


def file(request: HttpRequest, path) -> HttpResponse:
    parent_path = '/'.join(path.split('/')[:-1])
    file_name = path.split('/')[-1]

    if not parent_path:
        parent_path = Item._meta.get_field('path').get_default()

    file_object = Item.objects.filter(path=parent_path + '/').get(name=file_name)

    return render(
        request,
        'file_mgr/file.html', {
            'parent_path': parent_path,
            'file': file_object,
        })


def file_request(request: HttpRequest) -> JsonResponse:
    start = int(request.GET.get('start'))
    end = int(request.GET.get('end'))
    path = request.GET.get('path')

    if path == 'Root':
        path = Item._meta.get_field('path').get_default()

    sub_items = Item.objects.filter(path=path).order_by('type')
    sub_dirs, sub_files = dir_file_fetcher(sub_items, start, end)
    sub_dirs = list(sub_dirs.values())
    sub_files = list(sub_files.values())

    return JsonResponse({
        "dirs": sub_dirs,
        "files": sub_files,
    })
