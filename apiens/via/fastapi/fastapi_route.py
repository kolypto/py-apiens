from typing import Mapping

from fastapi.params import Param

from apiens.util import decomarker


class fastapi_route(decomarker):
    """ Additional options for FastAPI routes

    Example:
        from apiens import operation
        from apiens.via.fastapi import fastapi_route

        @operation
        @fastapi_route('GET', '/')
        def index():
            pass
    """

    # The HTTP verb to use on this endpoint
    method: str

    # The API path to use
    path: str

    # Customized parameters
    parameters: Mapping[str, Param]

    def __init__(self, /, method: str, path: str, **parameters: Param):
        super().__init__()

        self.method = method
        self.path = path
        self.parameters = parameters


class fastapi_params(fastapi_route):
    """ Additional options for FastAPI class constructor (that is not a route)

    Example:
        @fastapi_params(auth_token=Query(...))
        class UserOperations:
            def __init__(self, auth_token: str = None):
                pass

    """

    MARKER_ATTR = fastapi_route.MARKER_ATTR

    def __init__(self, **parameters: Param):
        # noinspection PyTypeChecker
        super().__init__(None, None, **parameters)
