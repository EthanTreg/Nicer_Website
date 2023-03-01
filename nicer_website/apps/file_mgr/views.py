from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, JsonResponse

from .models import Item


def dir_file_fetcher(start: int, end: int, path: str):
    dirs = Item.objects.filter(path=path, type=Item.item_type[0][0]).order_by('name')[start:end]
    files = Item.objects.filter(path=path, type=Item.item_type[1][0]).order_by('name')[start:end]
    return dirs, files


def directory(request: HttpRequest, path) -> HttpResponse:
    if path:
        path = path.strip('/') + '/'

    sub_dirs, sub_files = dir_file_fetcher(0, 1, path)
    parent_path = '/'.join(path.split('/')[:-2]) + '/'

    return render(
        request,
        'file_mgr/directory.html', {
            'current_dir': path,
            'dirs_exist': sub_dirs.exists(),
            'files_exist': sub_files.exists(),
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

    sub_dirs, sub_files = dir_file_fetcher(start, end, path)

    sub_dirs = list(sub_dirs.values())
    sub_files = list(sub_files.values())

    return JsonResponse({
        "dirs": sub_dirs,
        "files": sub_files,
    })
