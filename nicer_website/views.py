"""
Main functions for backend functionality of the website home
"""
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse


def index(request: HttpRequest) -> HttpResponse:
    """
    Default index function to return homepage

    Parameters
    ----------
    request : HttpRequest
        Http request for the homepage

    Returns
    -------
    HttpResponse
        Http response containing the homepage
    """
    return render(request, 'index.html')
