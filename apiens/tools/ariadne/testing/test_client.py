""" Test client for Ariadne applications.

This client offers greater flexibility than the FastAPI GraphQL client because:

* It involves fewer application layers and works faster
* You can customize the context before executing any operations
* Errors are reported as Exceptions (rather than JSON objects) and can be analyzed
* Supports subscriptions :) 
"""

from __future__ import annotations

import graphql
import ariadne
from collections import abc
from typing import Any

from apiens.tools.graphql.testing.test_client import GraphQLTestClient as _BaseGraphQLTestClient
from apiens.tools.graphql.testing.error_collector import GraphQLErrorCollector
from .query import GraphQLResult, ContextT


class AriadneTestClient(_BaseGraphQLTestClient):
    """ Test client for Ariadne GraphQL schema """

    def __init__(self, schema: graphql.GraphQLSchema, debug: bool = True, error_formatter: ariadne.types.ErrorFormatter = ariadne.format_error):
        super().__init__(schema, debug)
        self.error_formatter = error_formatter

        # Initialize a MiddlewareManager if you need one
        self.middleware = None

    #region: Lower level methods

    async def execute_async_operation(self, query: str, context_value: Any = None, /, operation_name: str = None, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL operation on the schema, async """
        error_collector = GraphQLErrorCollector()
        success, response = await ariadne.graphql(
            self.schema,
            dict(query=query, variables=variables or {}, operationName=operation_name),
            context_value=context_value,
            root_value=None,
            debug=self.debug,
            logger=__name__,
            error_formatter=error_collector.error_formatter(self.error_formatter),
            middleware=self.middleware,
        )
        return GraphQLResult(
            response,  # type: ignore[arg-type]
            context=context_value, 
            exceptions=error_collector.errors
        )

    def execute_sync_operation(self, query: str, context_value: Any = None, /, operation_name: str = None, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL operation on the schema, with a custom context, in sync mode

        Sync mode assumes that every resolver is a sync function
        """
        error_collector = GraphQLErrorCollector()
        success, response = ariadne.graphql_sync(
            self.schema,
            dict(query=query, variables=variables or {}, operationName=operation_name),
            context_value=context_value,
            root_value=None,
            debug=self.debug,
            logger=__name__,
            error_formatter=error_collector.error_formatter(self.error_formatter),
            middleware=self.middleware,
        )
        return GraphQLResult(
            response,   # type: ignore[arg-type]
            context=context_value, 
            exceptions=error_collector.errors
        )

    async def execute_subscription(self, query: str, context_value: Any = None, **variables) -> abc.AsyncIterator[GraphQLResult[ContextT]]:  # type: ignore[override]
        """ Execute a GraphQL subscription """
        success, results = await ariadne.subscribe(
            self.schema,
            dict(query=query, variables=variables or {}, operationName=None),
            context_value=context_value,
            root_value=None,
            debug=self.debug,
            logger=__name__,
            error_formatter=self.error_formatter,
        )

        # When success=True, `results` is an async generator.
        # When success=False, `results` is a list of error dicts

        if success == False:
            GraphQLResult({'data': None, 'errors': results}).raise_errors()  # type: ignore[typeddict-item]
        else:
            result: graphql.ExecutionResult
            async for result in results:  # type: ignore[union-attr]
                yield GraphQLResult({
                        'data': result.data,
                        'errors': [],  # we do not have any formatted errors
                    },
                    context=context_value,
                    exceptions=result.errors,  # GraphQLError objects
                )

    #endregion


