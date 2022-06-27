from __future__ import annotations

import graphql
import ariadne

from dataclasses import dataclass
from collections import abc
from typing import TypedDict, Optional, Any, Generic, TypeVar

from apiens.structure.error import GraphqlResponseErrorObject, ErrorObject
from .error_collector import GraphQLErrorCollector, raise_graphql_errors
from ..format_error import unwrap_graphql_error


def graphql_query_sync(schema: graphql.GraphQLSchema, query: str, context_value: Any = None, /, **variable_values):
    """ Make a GraphqQL query, quick. """
    data = dict(
        query=query,
        variables=variable_values or {},
        operationName=None,
    )
    error_collector = GraphQLErrorCollector()
    success, res = ariadne.graphql_sync(
        schema,
        data,
        context_value=context_value,
        root_value=None,
        debug=True,
        logger=__name__,
        error_formatter=error_collector.error_formatter(),
    )
    return GraphQLResult(res, error_collector.errors)  # type: ignore[arg-type]


ContextT = TypeVar('ContextT')

@dataclass
class GraphQLResult(Generic[ContextT]):
    """ GraphQL result. Contains data, errors, and exceptions

    Super features:
    * supports getting resulrs with result['fieldName']
    * will raise exceptions when you assert no errors
    """
    # Data returned by the GraphQL API. Dict.
    data: Optional[dict]

    # List of reported errors, if any
    errors: list[GraphqlResponseErrorObject]

    # List of captured Python exceptions, if any
    exceptions: list[graphql.GraphQLError]

    # The context value used for this request.
    # Note that there is no real HTTP request: just this context.
    context: ContextT

    def __init__(self, response: GraphQLResponseDict, exceptions: abc.Iterable[graphql.GraphQLError] = ()):
        self.data = response.get('data', None)
        self.errors = response.get('errors', [])
        self.exceptions = list(exceptions)

    @property
    def ok(self) -> bool:
        """ Did the request go without errors? """
        return not self.errors

    def successful(self):
        """ Assert the request was successful """
        self.raise_errors()
        return self

    def __getitem__(self, name):
        """ Get a result field, assuming that there were no errors """
        self.successful()
        return self.data[name]

    @property
    def app_error(self) -> ErrorObject:
        """ Return the single Application Error Object that the query must have returned

        Usage:
            assert res.app_error['name'] == 'E_AUTH_REQUIRED'
        """
        return self.graphql_error['extensions']['error']  # type: ignore[return-value]

    @property
    def app_error_name(self) -> str:
        """ Return the single Application Error Object name the query must have returned

        Usage:
            assert res.app_error_name == 'E_AUTH_REQUIRED'
        """
        return self.app_error['name']

    @property
    def graphql_error(self) -> GraphqlResponseErrorObject:
        """ Return the single GraphQL Error that the query must have returned """
        assert len(self.errors) == 1, f'Expected exactly one error, got {len(self.errors)}'  # type: ignore[arg-type]
        return self.errors[0]  # type: ignore[return-value,index]

    @property
    def original_error(self) -> Optional[Exception]:
        """ Get the original exception object, if available """
        if not self.exceptions:
            return None
        else:
            return unwrap_graphql_error(self.exceptions[0])

    def raise_errors(self):
        """ Raise errors as exceptions, if any """
        raise_graphql_errors(self.exceptions)


class GraphQLResponseDict(TypedDict, total=False):
    """ Dict structure for GraphQL responses """
    data: Optional[dict]
    errors: list[GraphqlResponseErrorObject]
