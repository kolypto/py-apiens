from __future__ import annotations

from contextlib import contextmanager

import asyncio
import graphql
import ariadne
from collections import abc
from typing import Optional, Any

from .error_collector import GraphQLErrorCollector
from .query import GraphQLResult, ContextT


class GraphQLTestClient:
    """ Test client for GraphQL schema """
    def __init__(self, schema: graphql.GraphQLSchema, debug: bool = True, error_formatter: ariadne.types.ErrorFormatter = ariadne.format_error):
        self.schema = schema
        self.debug = debug
        self.error_formatter = error_formatter

        # Initialize a MiddlewareManager if you need one
        self.middleware = None

    def execute(self, query: str, /, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL query, with async resolver support """
        with self.init_context_sync() as context_value:
            res: GraphQLResult[ContextT] = self.execute_operation(query, context_value, **variables)
            res.context = context_value  # type: ignore[assignment]
            return res

    def execute_sync(self, query: str, /, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL query in sync mode """
        with self.init_context_sync() as context_value:
            res: GraphQLResult[ContextT] = self.execute_sync_operation(query, context_value, **variables)
            res.context = context_value  # type: ignore[assignment]
            return res

    @contextmanager
    def init_context_sync(self) -> abc.Iterator[Optional[ContextT]]:
        """ Prepare a context for a GraphQL request """
        yield None

    def execute_operation(self, query: str, context_value: Any = None, /, operation_name: str = None, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL operation on the schema, with a custom context, in async mode

        Async mode supports async resolvers. Blocking sync resolvers must be careful to run themselves in threadpool.
        See `tools.ariadne.asgi` to aid with this.
        """
        return asyncio.run(self.execute_async_operation(query, context_value, operation_name=operation_name, **variables))

    async def execute_async_operation(self, query: str, context_value: Any = None, /, operation_name: str = None, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL operation on the schema, async """
        data = dict(
            query=query,
            variables=variables or {},
            operationName=operation_name,
        )
        error_collector = GraphQLErrorCollector()
        success, response = await ariadne.graphql(
            self.schema,
            data,
            context_value=context_value,
            root_value=None,
            debug=self.debug,
            logger=__name__,
            error_formatter=error_collector.error_formatter(self.error_formatter),
            middleware=self.middleware,
        )
        return GraphQLResult(response, error_collector.errors)  # type: ignore[arg-type]

    def execute_sync_operation(self, query: str, context_value: Any = None, /, operation_name: str = None, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL operation on the schema, with a custom context, in sync mode

        Sync mode assumes that every resolver is a sync function
        """
        data = dict(
            query=query,
            variables=variables or {},
            operationName=operation_name,
        )
        error_collector = GraphQLErrorCollector()
        success, response = ariadne.graphql_sync(
            self.schema,
            data,
            context_value=context_value,
            root_value=None,
            debug=self.debug,
            logger=__name__,
            error_formatter=error_collector.error_formatter(self.error_formatter),
            middleware=self.middleware,
        )
        return GraphQLResult(response, error_collector.errors)  # type: ignore[arg-type]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass
