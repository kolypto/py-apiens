import graphql
from apiens.structure.error import exc


def convert_to_graphql_error(e: Exception, *, include_debug_info: bool, exc=exc) -> graphql.GraphQLError:
    """ Given an arbitrary exception, convert it into a GraphQL error with an ApplicationError inside """
    if isinstance(e, graphql.GraphQLError):
        return e

    # Convert unexpected errors to F_UNEXPECTED_ERROR
    if not isinstance(e, exc.BaseApplicationError):
        e = exc.F_UNEXPECTED_ERROR.from_exception(e)

    return graphql.GraphQLError(
        str(e.error),
        original_error=e,
        extensions={
            'error': e.dict(include_debug_info=include_debug_info)
        }
    )
