from typing import Mapping

from fastapi.params import Param

from apiens.util import decomarker


class fastapi_route(decomarker):
    """ Additional options for FastAPI routes

    Example:
        from apiens import operation
        from apiens.via.fastapi import fastapi_route

        @operation
        @fastapi_route()
    """

    # The HTTP verb to use on this endpoint
    method: str

    # The API path to use
    path: str

    # Customized parameters
    parameters: Mapping[str, Param]

    def __init__(self, method: str, path: str, **parameters: Param):
        super().__init__()

        self.method = method
        self.path = path
        self.parameters = parameters
