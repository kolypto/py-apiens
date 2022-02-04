import logging

import pydantic as pd
from fastapi import Request, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler as fastapi_http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException, ExceptionMiddleware

from apiens.structure.error.schema import ErrorResponse
from apiens.structure.error import exc

from .route_suggestions import suggest_api_endpoint

logger = logging.getLogger()


def register_application_exception_handlers(app: FastAPI, *, passthru: bool = False):
    """ Register exception handlers on a FastAPI application

    Those handlers would catch specific errors by exception class and apply custom processing to them

    Args:
        passthru: Let unexpected errors pass through. Used in testing.
    """
    app.add_exception_handler(exc.BaseApplicationError, application_exception_handler)
    if app.debug:
        app.add_exception_handler(HTTPException, http_404_handler_with_route_suggestions)

    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(pd.ValidationError, validation_error_exception_handler)

    # Handler for `Exception` has to be installed as middleware.
    # Otherwise `add_exception_handler()` applies it separately and includes fancy HTML traceback page
    if not passthru:
        app.add_middleware(ExceptionMiddleware, handlers={Exception: unexpected_exception_handler}, debug=app.debug)


async def application_exception_handler(request: Request, e: exc.BaseApplicationError) -> JSONResponse:
    """ Exception handler: Application exceptions

    Every exc.BaseApplicationError are meant for the end-user and are returned as JSON response.
    """
    # TODO: errors passthrough mode for unit-tests
    # Format the JSON error object properly
    return JSONResponse(
        status_code=e.httpcode,
        content=jsonable_encoder(ErrorResponse.from_exception(e, include_debug_info=request.app.debug)),
        headers=e._response_headers
    )


async def request_validation_exception_handler(request: Request, e: pd.ValidationError) -> JSONResponse:
    """ Exception handler: validation errors on the user input

    Every `ValidationError` raised by FastAPI is returned as `E_CLIENT_VALIDATION`.
    Most likely, the user has failed validation of some field. Most likely, this is a user error.

    Note that FastAPI validation errors are handled differently from other validation errors:
    because Pydantic may be used for validating not only the user input, but other things as well.
    We have to keep the two separate.
    """
    return await application_exception_handler(
        request,
        exc.E_CLIENT_VALIDATION.from_pydantic_validation_error(e)
    )


async def validation_error_exception_handler(request: Request, e: pd.ValidationError) -> JSONResponse:
    """ Exception handler: validation errors on other objects

    Any `ValidationError`s thrown in view functions are considered unexpected and converted into `F_UNEXPECTED_ERROR`.

    If your code needs to report a ValidationError to the user, convert it into `E_CLIENT_VALIDATION` manually.
    """
    return await unexpected_exception_handler(
        request,
        e,
        model=e.model.__name__,
        errors=e.errors(),  # [ {loc: Tuple[str], msg: str, type; str} ]
    )


async def unexpected_exception_handler(request: Request, e: Exception, **info) -> JSONResponse:
    """ Exception handler: unexpected exceptions; generic server error

    Every Python exception thrown in a view is conveted to F_UNEXPECTED_ERROR
    """
    # Record the exception before passing it on
    logger.exception('Unexpected exception')

    # Tell the user we have failed
    return await application_exception_handler(
        request,
        exc.F_UNEXPECTED_ERROR.from_exception(e, **info)
    )


async def http_404_handler_with_route_suggestions(request: Request, e: HTTPException, **info) -> JSONResponse:
    """ Exception handler for 404 errors that shows route suggestsions. Only use in debug mode.

    When the API URL is invalid, this handler will offer a list of suggestions that the user may have meant.
    """
    if not request.app.debug:
        return await fastapi_http_exception_handler(request, e)

    # In FastAPI, there is no such thing yet as "current route". It's not stored in the request.
    # Therefore, we can't tell whether this 404 come from a view or from the router itself.
    # So this "not found" page is
    if e.status_code == status.HTTP_404_NOT_FOUND and e.detail == 'Not Found':
        close_matches = suggest_api_endpoint(request.app, request.scope['method'], request.scope['path'])

        # Report
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=jsonable_encoder({
                'detail': 'API not found',
                'suggestions': close_matches,
            }),
        )

    return await fastapi_http_exception_handler(request, e)
