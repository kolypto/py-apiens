import graphql
import ariadne

from typing import Any, Union


def graphql_query_sync(schema: graphql.GraphQLSchema, query: str, context_value: Any = None, **variable_values):
    """ Make a GraphqQL query, quick. Fail on errors. """
    data = dict(
        query=query,
        variables=variable_values or {},
        operationName=None,
    )
    success, res = ariadne.graphql_sync(
        schema,
        data,
        context_value=context_value,
        root_value=None,
        debug=True,
        logger=__name__,
        error_formatter=debug_format_error,  # type: ignore[arg-type]
    )

    if 'errors' in res:
        # One error? raise it
        if len(res['errors']) == 1:
            raise res['errors'][0]
        # Many errors? Raise a list
        else:
            raise RuntimeError(res['errors'])

    return res


def debug_format_error(error: graphql.GraphQLError, debug: bool = False) -> Union[dict, graphql.GraphQLError]:
    """ Error formatter for unit-tests """
    # Just return the very same error object
    # This goes against GraphQL protocol, but is ok for unit-tests: we'll get the error object embedded into json response!
    if debug:
        return error
    else:
        return ariadne.format_error(error, debug)
