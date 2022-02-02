import logging

import pydantic as pd
from fastapi import Request, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler as fastapi_http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException

from apiens.structure.error.schema import ErrorResponse
from apiens.structure.error import exc

from .route_suggestions import suggest_api_endpoint

logger = logging.getLogger()


def register_application_exception_handlers(app: FastAPI, *, debug: bool = False):
    """ Register exception handlers on a FastAPI application

    Those handlers would catch specific errors by exception class and apply custom processing to them
    """
    # Exception handlers in order of application
    app.add_exception_handler(exc.BaseApplicationError, application_exception_handler)
    app.add_exception_handler(RequestValidationError, user_input_validation_exception_handler)
    app.add_exception_handler(pd.ValidationError, validation_error_exception_handler)
    if debug:
        app.add_exception_handler(HTTPException, http_404_handler_with_route_suggestions)
    app.add_exception_handler(Exception, unexpected_exception_handler)


async def application_exception_handler(request: Request, e: exc.BaseApplicationError, *, debug: bool = False) -> JSONResponse:
    """ Exception handler: Application exceptions """
    # Format the JSON error object properly
    return JSONResponse(
        status_code=e.httpcode,
        content=jsonable_encoder(ErrorResponse.from_exception(e, include_debug_info=debug)),
        headers=e._response_headers
    )


async def user_input_validation_exception_handler(request: Request, e: pd.ValidationError) -> JSONResponse:
    """ Exception handler: validation errors on the user input

    These have to be different from other `pydantic.ValidationError` because Pydantic may be used for validating
    not only the user input, but other things as well.
    """
    return await application_exception_handler(
        request,
        exc.E_CLIENT_VALIDATION.from_pydantic_validation_error(e)
    )


async def validation_error_exception_handler(request: Request, e: pd.ValidationError) -> JSONResponse:
    """ Exception handler: validation errors on other objects """
    return await unexpected_exception_handler(
        request,
        e,
        model=e.model.__name__,
        errors=e.errors(),  # [ {loc: Tuple[str], msg: str, type; str} ]
    )


async def unexpected_exception_handler(request: Request, e: Exception, **info) -> JSONResponse:
    """ Exception handler: unexpected exceptions; generic server error """
    # Record the exception before passing it on
    logger.exception('Unexpected exception')

    # Tell the user we have failed
    return await application_exception_handler(
        request,
        exc.F_UNEXPECTED_ERROR.from_exception(e, **info)
    )


async def http_404_handler_with_route_suggestions(request: Request, e: HTTPException, **info) -> JSONResponse:
    """ Exception handler for 404 errors that shows route suggestsions. Only use in debug mode. """
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
