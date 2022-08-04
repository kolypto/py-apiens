""" Test Client for the GraphQL app """
from __future__ import annotations

import asyncio
import graphql
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Optional
from collections import abc

from apiens.tools.python.threadpool import run_in_threadpool
from .query import GraphQLResult, ContextT, graphql_query_async, graphql_query_sync


class GraphQLTestClient:
    def __init__(self, schema: graphql.GraphQLSchema, debug: bool = True):
        self.schema = schema
        self.debug = debug
    
    # Execute queries

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
            sub: abc.AsyncIterator[GraphQLResult[ContextT]] = self.execute_subscription(query, context_value, **variables)  # type: ignore[assignment]
            async for res in sub:
                yield res
    
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    
    # Prepare context

    @contextmanager
    def init_context_sync(self) -> abc.Iterator[Optional[ContextT]]:
        """ Prepare a context for a GraphQL request """
        yield None

    @asynccontextmanager
    async def init_context_async(self) -> abc.AsyncIterator[Optional[ContextT]]:
        """ Prepare a context for a GraphQL request, async mode. Used for GraphQL subscriptions. 
        
        Override this method if your app uses a different way to prepare context in async tests
        """
        # Simply run the same function, but using threads
        cm = self.init_context_sync()

        value = await run_in_threadpool(next, cm.gen)  # type: ignore[arg-type]
        try:
            yield value
        finally:
            await run_in_threadpool(next, cm.gen, None)  # type: ignore[call-arg, arg-type]
    
    #region: Execute queries

    def execute_operation(self, query: str, context_value: Any = None, /, operation_name: str = None, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL operation on the schema, with a custom context, in sync mode

        Async mode supports async resolvers. Blocking sync resolvers must be careful to run themselves in threadpool.
        See `apiens.tools.graphql.resolver.resolver_marker` to aid with this.
        """
        return asyncio.run(
            # We run it through the async so that your async methods can run in unit-tests.
            self.execute_async_operation(query, context_value, operation_name=operation_name, **variables)
        )

    async def execute_async_operation(self, query: str, context_value: Any = None, /, operation_name: str = None, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL operation on the schema, async """
        return await graphql_query_async(self.schema, query, context_value, operation_name, **variables)

    def execute_sync_operation(self, query: str, context_value: Any = None, /, operation_name: str = None, **variables) -> GraphQLResult[ContextT]:
        """ Execute a GraphQL operation on the schema, with a custom context, in sync mode

        Sync mode assumes that every resolver is a sync function
        """
        return graphql_query_sync(self.schema, query, context_value, operation_name, **variables)

    async def execute_subscription(self, query: str, context_value: Any = None, **variables) -> abc.AsyncIterator[GraphQLResult[ContextT]]:
        """ Execute a GraphQL subscription """
        res = await graphql.subscribe(
            self.schema,
            query,  # type: ignore[arg-type]
            context_value=context_value,
            variable_values=variables,
        )
        # TODO: implement
        raise NotImplementedError

    #endregion
