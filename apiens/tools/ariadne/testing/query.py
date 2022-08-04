from __future__ import annotations

import graphql
import ariadne

from typing import Any

from apiens.tools.graphql.testing.query import GraphQLResult, ContextT 
from apiens.tools.graphql.testing.error_collector import GraphQLErrorCollector


def graphql_query_sync(schema: graphql.GraphQLSchema, query: str, context_value: Any = None, /, **variable_values) -> GraphQLResult:
    """ Make a GraphqQL query, quick. Collect errors. """
    error_collector = GraphQLErrorCollector()
    success, res = ariadne.graphql_sync(
        schema,
        dict(query=query, variables=variable_values or {}, operationName=operation_name),
        context_value=context_value,
        root_value=None,
        debug=True,
        logger=__name__,
        error_formatter=error_collector.error_formatter(ariadne.format_error),
    )
    return GraphQLResult(
        res, 
        context=context_value, 
        exceptions=error_collector.errors
    )
