from __future__ import annotations

import graphql

from dataclasses import dataclass
from collections import abc
from typing import TypedDict, Optional, Any, Generic, TypeVar

from apiens.error.error_object.python import GraphqlResponseErrorObject, ErrorObject
from .error_collector import raise_graphql_errors
from ..errors.error_convert import unwrap_graphql_error


def graphql_query_sync(schema: graphql.GraphQLSchema, query: str, context_value: Any = None, /, operation_name: str = None, **variable_values) -> GraphQLResult:
    """ Make a GraphQL query, quick. Collect errors. """
    res = graphql.graphql_sync(
        schema, 
        query, 
        context_value=context_value, 
        variable_values=variable_values,
        operation_name=operation_name,
    )
    return GraphQLResult(
        res.formatted,  # type: ignore[arg-type]
        context=context_value,
        exceptions=res.errors,
    )

async def graphql_query_async(schema: graphql.GraphQLSchema, query: str, context_value: Any = None, /, operation_name: str = None, **variable_values) -> GraphQLResult:
    """ Make a GraphQL query, quick, async. Collect errors. """
    res = await graphql.graphql(
        schema, 
        query, 
        context_value=context_value, 
        variable_values=variable_values,
        operation_name=operation_name,
    )
    return GraphQLResult(
        res.formatted,  # type: ignore[arg-type]
        context=context_value,
        exceptions=res.errors,
    )


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
    context: Optional[ContextT]

    def __init__(self, response: GraphQLResponseDict, context: ContextT = None, exceptions: abc.Iterable[graphql.GraphQLError] = None):
        self.data = response.get('data', None)
        self.errors = response.get('errors', [])
        self.exceptions = list(exceptions or ())
        self.context = context

    @property
    def ok(self) -> bool:
        """ Did the request go without errors? """
        return not self.errors

    def successful(self):
        """ Assert the request was successful """
        self.raise_errors()
        return self

    def __getitem__(self, name):
        """ Get a result field, assuming that there were no errors 
        
        Note: it will re-raise the original GraphQL errors if you attempt to access fields while there are errors!
        To access fields anyway, use `.data`.
        """
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
        # Try to get it from the exception object first
        if exception := self.original_error:
            return exception.name 
        else:
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
        # If we have nice Python Exception objects, raise them as is
        if self.exceptions:
            raise_graphql_errors(self.exceptions)
        # If not, reconstruct them from JSON data
        if self.errors:
            raise_graphql_errors([
                graphql.GraphQLError(e['message'], path=e.get('path'), extensions=e['extensions'])
                for e in self.errors
            ])


class GraphQLResponseDict(TypedDict, total=False):
    """ Dict structure for GraphQL responses """
    data: Optional[dict]
    errors: list[GraphqlResponseErrorObject]
