import graphql
import ariadne

from typing import Union

from apiens.structure.error import exc, ErrorObject
from apiens.tools.ariadne.testing.query import ErrorDict
from .convert_error import unwrap_graphql_error


def application_error_formatter(error: graphql.GraphQLError, debug: bool = False, *, BaseApplicationError = exc.BaseApplicationError) -> Union[dict, ErrorDict]:
    """ Error formatter. Add Error Object for application errors

    When `debug` is set, it will return an error dict that also has a reference to the original Exception object.
    """
    # Make sure it's a dict
    if not error.extensions:
        error.extensions = {}

    # If `extensions[error]` key is present, it means that we've handled it already.
    # Act only if not
    if 'error' not in error.extensions:
        # Get the original error.
        original_error = unwrap_graphql_error(error)

        # Application error? Add Error Object
        if isinstance(original_error, BaseApplicationError):
            error.extensions['error'] = _export_application_error_object(original_error, include_debug_info=debug)

    # Format error
    error_dict = ariadne.format_error(error, debug)

    # In debug mode, associate the original exception with it
    if debug:
        error_dict = ErrorDict(error_dict, error)

    # Done
    return error_dict


def _export_application_error_object(e: exc.BaseApplicationError, *, include_debug_info: bool) -> ErrorObject:
    error_object = e.dict(include_debug_info=include_debug_info)

    # NOTE: error objects may contain references to: dates, enums, etc. These have to be jsonable encoded.
    # TODO: it's probably not a good idea to invoke FastAPI here thus adding it as a dependency, but at the moment, I've found no better way to do this.
    if fastapi is not None:
        error_object = fastapi.encoders.jsonable_encoder(error_object)

    return error_object


try:
    import fastapi.encoders
except ImportError:
    fastapi = None  # type: ignore[assignment]
