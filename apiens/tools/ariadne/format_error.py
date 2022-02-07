import graphql
import ariadne

from typing import Optional, Union

from apiens.structure.error import exc
from apiens.tools.ariadne.testing.query import ErrorDict


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
            error.extensions['error'] = original_error.dict(include_debug_info=debug)

    # Format error
    error_dict = ariadne.format_error(error, debug)

    # In debug mode, associate the original exception with it
    if debug:
        error_dict = ErrorDict(error_dict, error)

    # Done
    return error_dict



def convert_exception_to_graphql_error(e: Union[Exception, graphql.GraphQLError]) -> graphql.GraphQLError:
    """ Convert a generic exception to a GraphQL error, if not already.

    Note that such a representation will lack the rich error information Application errors provide.
    Avoid using this function.
    """
    if isinstance(e, graphql.GraphQLError):
        return e

    return graphql.GraphQLError(str(e), original_error=e)


def convert_application_error_to_graphql_error(e: exc.BaseApplicationError, *, include_debug_info: bool) -> graphql.GraphQLError:
    """ Convert an Application Error into a GraphQLError

    Args:
        e: The error to convert
        include_debug_info: Expose debugging information?
    """
    assert isinstance(e, exc.BaseApplicationError)

    return graphql.GraphQLError(
        str(e.error),
        original_error=e,
        extensions={
            'error': e.dict(include_debug_info=include_debug_info)
        }
    )

def unwrap_graphql_error(error: graphql.GraphQLError) -> Optional[Exception]:
    """ Get the original, non-GraphQL error

    The `GraphQLError` wraps the original error, sometimes multiple times.
    Get down to the original error and return it.

    If there's no original error, return None
    """
    if error.original_error is None:
        return None
    elif isinstance(error.original_error, graphql.GraphQLError):
        return unwrap_graphql_error(error)
    else:
        return error.original_error
