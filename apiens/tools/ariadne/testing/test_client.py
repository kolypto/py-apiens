from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager

import asyncio
import graphql
import ariadne
from collections import abc
from typing import Optional, Any

from apiens.tools.asyncio import run_in_threadpool
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
            return self.execute_operation(query, context_value, **variables)

    def execute_sync(self, query: str, /, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL query in sync mode """
        with self.init_context_sync() as context_value:
            return self.execute_sync_operation(query, context_value, **variables)

    async def subscribe(self, query: str, /, **variables) -> abc.AsyncIterator[GraphQLResult[ContextT]]:
        """ Execute a GraphQL subscription, in async mode """
        async with self.init_context_async() as context_value:
            sub: abc.AsyncIterator[GraphQLResult[ContextT]] = self.execute_subscription(query, context_value, **variables)
            async for res in sub:
                yield res

    @contextmanager
    def init_context_sync(self) -> abc.Iterator[Optional[ContextT]]:
        """ Prepare a context for a GraphQL request """
        yield None

    @asynccontextmanager
    async def init_context_async(self) -> abc.AsyncIterator[Optional[ContextT]]:
        """ Prepare a context for a GraphQL request, async mode. Used for GraphQL subscriptions. """
        # Simply run the same function, but using threads
        cm = self.init_context_sync()

        value = await run_in_threadpool(next, cm.gen)  # type: ignore[arg-type]
        try:
            yield value
        finally:
            await run_in_threadpool(next, cm.gen, None)  # type: ignore[call-arg, arg-type]

    #region: Lower level methods

    def execute_operation(self, query: str, context_value: Any = None, /, operation_name: str = None, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL operation on the schema, with a custom context, in async mode

        Async mode supports async resolvers. Blocking sync resolvers must be careful to run themselves in threadpool.
        See `tools.ariadne.asgi` to aid with this.
        """
        return asyncio.run(self.execute_async_operation(query, context_value, operation_name=operation_name, **variables))

    async def execute_async_operation(self, query: str, context_value: Any = None, /, operation_name: str = None, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL operation on the schema, async """
        error_collector = GraphQLErrorCollector()
        success, response = await ariadne.graphql(
            self.schema,
            _prepare_data(query, variables, operation_name),
            context_value=context_value,
            root_value=None,
            debug=self.debug,
            logger=__name__,
            error_formatter=error_collector.error_formatter(self.error_formatter),
            middleware=self.middleware,
        )
        return GraphQLResult(response, context=context_value, exceptions=error_collector.errors)  # type: ignore[arg-type]

    def execute_sync_operation(self, query: str, context_value: Any = None, /, operation_name: str = None, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL operation on the schema, with a custom context, in sync mode

        Sync mode assumes that every resolver is a sync function
        """
        error_collector = GraphQLErrorCollector()
        success, response = ariadne.graphql_sync(
            self.schema,
            _prepare_data(query, variables, operation_name),
            context_value=context_value,
            root_value=None,
            debug=self.debug,
            logger=__name__,
            error_formatter=error_collector.error_formatter(self.error_formatter),
            middleware=self.middleware,
        )
        return GraphQLResult(response, context=context_value, exceptions=error_collector.errors)  # type: ignore[arg-type]

    async def execute_subscription(self, query: str, context_value: Any = None, **variables) -> abc.AsyncIterator[GraphQLResult[ContextT]]:
        """ Execute a GraphQL subscription """
        success, results = await ariadne.subscribe(
            self.schema,
            _prepare_data(query, variables, operation_name=None),
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

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


def _prepare_data(query: str, variables: dict, operation_name: str = None) -> dict:
    """ Prepare data dict for ariagne.graphql() """
    return dict(
        query=query,
        variables=variables or {},
        operationName=operation_name,
    )

