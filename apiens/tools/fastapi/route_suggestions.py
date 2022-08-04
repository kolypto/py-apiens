""" Route suggestions: suggest valid URL routes when the user has entered a wrong one """

from collections import abc
from functools import cache, lru_cache
from typing import Optional

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.routing import Route


def suggest_api_endpoint(app: FastAPI, method: Optional[str], path: str) -> abc.Collection[str]:
    """ Suggest a page that the user may have wanted when they got a 404 error

    This function is used to respond to 404 API pages: try to guess what the user may have meant
    and suggest that they fix the typo.

    Example:
        Input:
        "GET /doc"

        Suggestions:
        "GET /apii/docs",
        "GET /apii/redoc",
    """
    from difflib import get_close_matches

    input_route = ' '.join([method or '-', path])
    valid_routes = [
        f'{method} {path}'
        for method, path in _all_application_routes(app)
    ]

    return get_close_matches(input_route, valid_routes, n=9)


@lru_cache(maxsize=9)  # must be 1, but just in case
def _all_application_routes(app: FastAPI) -> tuple[tuple[str, str], ...]:
    """ Get a list of all routes from a FastAPI app """
    # Get all routes that make sense
    routes = [
        route
        for route in app.routes
        if isinstance(route, (Route, APIRoute,))
    ]

    # Render as immutable list: tuple
    return tuple(
        (method, route.path)
        for route in routes
        for method in (route.methods or ())
    )
