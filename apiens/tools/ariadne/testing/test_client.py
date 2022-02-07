from __future__ import annotations

import graphql
import ariadne
from dataclasses import dataclass
from typing import TypedDict, Optional, Any, Union

from apiens.structure.error import GraphqlResponseErrorObject, ErrorObject
from .query import debug_format_error, ErrorDict
from ..format_error import unwrap_graphql_error


class GraphQLTestClient:
    """ Test client for GraphQL schema """
    def __init__(self, schema: graphql.GraphQLSchema, debug: bool = True, error_formatter: ariadne.types.ErrorFormatter = debug_format_error):
        self.schema = schema
        self.debug = debug
        self.error_formatter = error_formatter

    def execute_sync(self, query: str, context_value: Any = None, /, **variables) -> GraphQLResult:
        """ Execute a GraphQL operation on the schema """
        data = dict(
            query=query,
            variables=variables or {},
            operationName=None,
        )
        success, response = ariadne.graphql_sync(
            self.schema,
            data,
            context_value=context_value,
            root_value=None,
            debug=self.debug,
            logger=__name__,
            error_formatter=self.error_formatter,
        )
        print(success, response)
        return GraphQLResult(response)  # type: ignore[arg-type]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


@dataclass
class GraphQLResult:
    """ GraphQL result """
    data: Optional[dict]
    errors: list[GraphqlResponseErrorObject]

    def __init__(self, response: GraphQLResponseDict):
        self.data = response['data']
        self.errors = response.get('errors', [])

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
    def graphql_error(self) -> Union[GraphqlResponseErrorObject, ErrorDict]:
        """ Return the single GraphQL Error that the query must have returned

        NOTE: your error formatter may have provided ErrorDict with a reference to the original Exception object
        """
        assert len(self.errors) == 1, f'Expected exactly one error, got {len(self.errors)}'  # type: ignore[arg-type]
        return self.errors[0]  # type: ignore[return-value,index]

    @property
    def original_error(self) -> Union[None, Exception, graphql.GraphQLError]:
        """ Get the original exception object, if available

        NOTE: your error formatter may have provided ErrorDict with a reference to the original Exception object
        """
        if not self.errors or not isinstance(self.graphql_error, ErrorDict):
            return None

        return unwrap_graphql_error(self.graphql_error.error) or self.graphql_error.error

    def raise_errors(self):
        """ Raise errors as exceptions, if any """
        # No errors? pass.
        if not self.errors:
            pass
        # One error? Raise it.
        elif len(self.errors) == 1:
            error = self.errors[0]
            # If ErrorDict, raise the original error
            if isinstance(error, ErrorDict):
                original_error = unwrap_graphql_error(error.error) or error.error
                raise RuntimeError from original_error
            # Otherwise raise the dict =\
            else:
                raise RuntimeError(error)
        # Many errors? Raise all.
        else:
            # TODO: In Python 3.11, raise ExceptionGroup
            raise RuntimeError(self.errors)


class GraphQLResponseDict(TypedDict, total=False):
    """ Dict structure for GraphQL responses """
    data: Optional[dict]
    errors: list[GraphqlResponseErrorObject]
