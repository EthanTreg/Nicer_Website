import logging as log

import numpy as np
from plotly.offline import plot
from plotly.graph_objs import Scatter
from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render

from ..file_mgr.models import Item
from src.spectrum_preprocessing import spectrum_data


def fetch_observations(request: HttpRequest):
    path = request.GET.get('path')
    
    parent_path = '/'.join(path.split('/')[:-1]).lstrip('/')
    path = path.split('/')[-1]
    
    print(parent_path)
    print(path)

    items = Item.objects.filter(name__contains=path, path=parent_path + '/').order_by('type', 'name')[:5]

    return JsonResponse({'dir_suggestions': list(items.values())})


def interactive_plot(request: HttpRequest):
    # with BytesIO() as buffer:
    #     plt.savefig(buffer, format='png')
    #     buffer.seek(0)
    #     image_png = buffer.getvalue()

    # graphic = base64.b64encode(image_png).decode('utf-8')
    # print(static('nicer_data/0001020103/jspipe/js_ni0001020103_0mpu7_goddard_GTI0.jsgrp'))
    if request.method == 'POST':
        file_path = settings.DATA_DIR + request.POST.get('file_path')
        file_dir = '/'.join(file_path.split('/')[:-1]) + '/'
        
        try:
            x_data, y_data, *_ = spectrum_data(file_path, background_dir=file_dir)
        except (FileNotFoundError, IsADirectoryError):
            log.error(f'Spectrum {file_path} or corresponding background not found')
    else:
        x_data = y_data = [0]

    plot_div = plot([Scatter(
        x=x_data,
        y=y_data,
        mode='lines',
        name='test',
        opacity=0.8,
        marker_color='green',
    )], output_type='div', show_link=False, link_text='', include_plotlyjs=False)

    return render(request, 'plots/plot.html', {'plot_div': plot_div})
