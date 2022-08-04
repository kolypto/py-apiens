""" Query a GraphQL schema, report errors as Exceptions

By default, GraphQL schema converts every exception into a dict. This is cool for production, but in unit-tests,
we want to access those original Exception objects because they contain stack traces.
This module provides a magic error formatter that is to be used for catching exceptions.

Normally, you won't need to use this module directly, but GraphQL TestClient uses it internally to capture errors.
"""
from __future__ import annotations

import graphql
import unittest.mock
from collections import abc
from contextlib import contextmanager

from ..errors.error_convert import unwrap_graphql_error


class GraphQLErrorCollector(list):
    """ Collect errors through a GraphQL wrapper

    Example:

        ecollector = GraphQLErrorCollector()
        success, res = ariadne.graphql_sync(
            schema,
            data,
            error_formatter=ecollector.error_formatter(ariadne.error_formatter),
        )
        ecollector.raise_errors()

    When used as a context manager, will automatically raise any errors when it exits:

    Example:

        with GraphQLErrorCollector(autoraise=True) as ecollector:
            success, res = ariadne.graphql_sync(
                schema,
                data,
                error_formatter=ecollector.error_formatter(),
            )

    Can also be used to patch a GraphQL asgi app to catch errors from it:

    Example:
        with GraphQLErrorCollector().patch_ariadne_app(app):
            client.post(...)
    """

    def __init__(self, autoraise=True):
        self.autoraise = autoraise
        self.errors = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.autoraise:
            self.raise_errors()

    def error_formatter(self, error_formatter: abc.Callable[[graphql.GraphQLError, bool], dict]):
        """ Get an error formatter that will intercept errors """
        def wrapper(error: graphql.GraphQLError, debug: bool = False) -> dict:
            # Remember it
            self.errors.append(error)

            # Actually format it
            return error_formatter(error, debug)
        return wrapper

    def raise_errors(self):
        """ Raise collected errors """
        raise_graphql_errors(self.errors)

    @contextmanager
    def patch_ariadne_app(self, app: ariadne.asgi.GraphQL):
        """ Patch Ariadne GraphQL application and catch every error on it. """
        # Prepare a wrapped formatter
        new_formatter = self.error_formatter(app.error_formatter)

        # Patch it, yield self
        with unittest.mock.patch.object(app, 'error_formatter', new_formatter), self:
            yield self


def raise_graphql_errors(errors: abc.Sequence[graphql.GraphQLError]):
    """ Raise exceptions from the list """
    if not errors:
        return

    # One error? Raise it.
    if len(errors) == 1:
        error = errors[0]

        # Unwrap GraphQLError if there was any original error
        original_error = unwrap_graphql_error(error) or error

        # Raise it
        raise original_error
    # Many errors? Raise all.
    else:
        # TODO: In Python 3.11, raise ExceptionGroup
        raise RuntimeError(errors)


try:
    import ariadne
except ImportError:
    class ariadne:  # type: ignore[no-redef]
        class asgi:
            GraphQL = object()
