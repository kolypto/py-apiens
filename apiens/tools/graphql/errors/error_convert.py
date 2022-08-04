import graphql
from typing import Union, Optional
from apiens.error import exc


def convert_to_graphql_application_error(e: Exception) -> graphql.GraphQLError:
    """ Given any exception, convert it into a GraphQL error with an ApplicationError inside 

    1. GraphQL errors are returned as is
    2. ApplicationError errors are wrapped into a GraphQL error
    3. Unexpected errors are reported as F_UNEXPECTED_ERROR, wrapped into a GraphQL error

    The result is a proper GraphQL error that will contain "extensions" with more information
    """
    if isinstance(e, graphql.GraphQLError):
        return e

    # Convert unexpected errors to F_UNEXPECTED_ERROR
    if not isinstance(e, exc.BaseApplicationError):
        e = exc.F_UNEXPECTED_ERROR.from_exception(e)

    return convert_to_graphql_error(e)


def convert_to_graphql_error(e: Union[Exception, graphql.GraphQLError]) -> graphql.GraphQLError:
    """ Convert a generic exception to a GraphQL error, if not already.

    Note that such a representation will lack the rich error information Application errors provide.
    Avoid using this function.
    """
    if isinstance(e, graphql.GraphQLError):
        return e

    return graphql.GraphQLError(str(e), original_error=e)


def unwrap_graphql_error(error: graphql.GraphQLError) -> Optional[Exception]:
    """ Get the original, non-GraphQL error

    The `GraphQLError` wraps the original error, sometimes multiple times.
    Get down to the original error and return it.

    If there's no original error, return None
    """
    if error.original_error is None:
        return None
    elif isinstance(error.original_error, graphql.GraphQLError):
        return unwrap_graphql_error(error.original_error)
    else:
        return error.original_error
