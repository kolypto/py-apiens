""" Tools for using GraphQL in ASGI mode

When you invoke graphql_sync(), it assumes that every resolver is a sync function.
This makes it impossible to use websockets.

In we want to use graphql(), then it's executed in async context.
All your `async def` functions are fine, but `def` functions must either be run in a threadpool,
or be careful not to use any blocking functions.

This module provides decorators that make sure that your non-async functions work correctly:
* decorator that runs a resolver in a threadpool
* decorator that marks a function as non-blocking
* utility that verifies that your resolvers are correct
"""
from __future__ import annotations

import asyncio
import functools
import graphql
from enum import Enum
from typing import Any, TypeVar, Optional
from collections import abc

from apiens.tools.asyncio import runs_in_threadpool as _runs_in_threadpool


def resolves_in_threadpool(function: abc.Callable[..., T]) -> abc.Callable[..., abc.Coroutine[Any, Any, T]]:
    """ Resolver decorator: blocking function that is run in a threadpool

    Apply to:
    * Resolvers involving I/O, such as database operations
    * Resolvers that do computing, such as encryption & hashing, especially where it comes to passwords
    """
    mark_threadpool_resolver(function)
    return _runs_in_threadpool(function)


def resolves_nonblocking(function: FT) -> FT:
    """ Resolver decorator: non-blocking sync function

    Apply to:
    * Resolvers that are really fast and involve no computing nor networking
    """
    return mark_nonblocking_resolver(function)


def resolves_async(function: AFT) -> AFT:
    """ Resolver decorator: async function

    Apply to:
    * Async resolvers (don't do it because it's applied automatically)
    """
    return mark_async_resolver(function)


def partial_resolver(resolver: FT, *args, **kwargs) -> FT:
    """ partial() for resolvers

    Python partial() loses additional function attributes because it does not use update_wrapper().
    This version does.
    """
    f: FT = functools.partial(resolver, *args, **kwargs)  # type: ignore[assignment]
    functools.update_wrapper(f, resolver)
    return f


# List of built-in modules to ignore while checking resolvers.
# They're assumed to be non-blocking.
BUILTIN_GRAPHQL_MODULES = frozenset((
    'graphql.execution.execute',  # default resolver
    'graphql.type.introspection',  # built-in types
    'ariadne.resolvers',  # fallback resolvers
))


def assert_no_unmarked_resolvers(schema: graphql.GraphQLSchema, *,
                                 ignore_modules: abc.Container = BUILTIN_GRAPHQL_MODULES,
                                 ignore_resolvers: abc.Container = ()):
    """ Make sure that every resolver in a GraphQL schema is properly marked """
    unmarked_resolvers = [
        f"{field.resolve.__qualname__} (module: {field.resolve.__module__})"  # type: ignore[union-attr]
        for field in find_fields_with_unmarked_resolvers(schema)
        if field.resolve.__module__ not in ignore_modules and field.resolve not in ignore_resolvers
    ]
    if not unmarked_resolvers:
        return

    unmarked_resolvers_list = '* ' + '\n* '.join(unmarked_resolvers)

    raise AssertionError(
        f"Some of your resolvers are not properly marked. "
        f"Please decorate with either @resolves_in_threadpool or @resolves_nonblocking. "
        f"\n\n"
        f"List of undecorated resolvers:\n\n"
        f"{unmarked_resolvers_list}"
    )


def find_fields_with_unmarked_resolvers(schema: graphql.GraphQLSchema) -> abc.Iterator[graphql.GraphQLField]:
    """ Collect fields and resolvers that have no @resolves decorator """
    for type_ in schema.type_map.values():
        if isinstance(type_, graphql.GraphQLObjectType):
            for field in type_.fields.values():
                # No resolver? No questions.
                if field.resolve is None:
                    continue

                # Resolver not marked? Report it.
                if _get_resolver_type(field.resolve) is None:
                    yield field  # Shakespeare code


T = TypeVar("T")
FT = TypeVar('FT', bound=abc.Callable)
AFT = TypeVar('AFT', bound=abc.Callable[..., abc.Coroutine[Any, Any, T]])


# region Function markers

def mark_async_resolver(function: FT) -> FT:
    _set_resolver_type(function, ResolverType.ASYNC)
    return function


def mark_threadpool_resolver(function: FT) -> FT:
    _set_resolver_type(function, ResolverType.THREADPOOL)
    return function


def mark_nonblocking_resolver(function: FT) -> FT:
    _set_resolver_type(function, ResolverType.NONBLOCKING)
    return function


def _get_resolver_type(function: abc.Callable) -> Optional[ResolverType]:
    """ Get resolver type marker from a function """
    # Unwrap: partial()
    if isinstance(function, functools.partial):
        function = function.func

    # Async functions don't have to be decorated
    if asyncio.iscoroutinefunction(function):
        return ResolverType.ASYNC

    # Sync functions need decoration because we can't guess
    return getattr(function, RESOLVER_TYPE_ATTR, None)


def _set_resolver_type(function: abc.Callable, resolver_type: ResolverType):
    """ Mark a function as having a resolver type """
    setattr(function, RESOLVER_TYPE_ATTR, resolver_type)


class ResolverType(Enum):
    # async functions
    ASYNC = 'async'

    # sync functions that resolve in a threadpool
    THREADPOOL = 'threadpool'

    # sync functions that are non-blocking: fast
    NONBLOCKING = 'nonblocking'


RESOLVER_TYPE_ATTR = 'apiens::resolver_type'

# endregion
