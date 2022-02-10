import graphql
from typing import Union, Optional
from apiens.structure.error import exc


def convert_to_graphql_application_error(e: Exception) -> graphql.GraphQLError:
    """ Given an arbitrary exception, convert it into a GraphQL error with an ApplicationError inside """
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
        return unwrap_graphql_error(error)
    else:
        return error.original_error
