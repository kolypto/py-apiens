from __future__ import annotations

import graphql
import ariadne

from typing import Any, Union


def graphql_query_sync(schema: graphql.GraphQLSchema, query: str, context_value: Any = None, /, **variable_values):
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
            raise res['errors'][0].error
        # Many errors? Raise a list
        else:
            raise RuntimeError(res['errors'])

    return res


def debug_format_error(error: graphql.GraphQLError, debug: bool = False) -> Union[dict, ErrorDict]:
    """ Error formatter for unit-tests

    When `debug` is set, it will add a custom `error` attribute to the error dict so that you can get the original error
    """
    error_dict = ariadne.format_error(error, debug)

    if debug:
        error_dict = ErrorDict(error_dict, error)

    return error_dict


class ErrorDict(dict):
    """ Error dict, with a reference to the original error """
    error: graphql.GraphQLError

    def __init__(self, error_dict: dict, error: graphql.GraphQLError):
        super().__init__(error_dict)
        self.error = error
