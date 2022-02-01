from collections import abc
from functools import cache
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

    input_route = ' '.join([method, path])
    valid_routes = [
        f'{method} {path}'
        for method, path in _all_application_routes(app)
    ]

    return get_close_matches(input_route, valid_routes)


@cache
def _all_application_routes(app: FastAPI) -> abc.Collection[tuple]:
    # Get all routes that make sense
    routes = [
        route
        for route in app.routes
        if isinstance(route, (Route, APIRoute,))
    ]

    # Render as list
    return (
        (method, route.path)
        for route in routes
        for method in route.methods
    )
