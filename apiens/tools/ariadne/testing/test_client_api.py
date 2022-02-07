from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import requests  # type: ignore[import]
from typing_extensions import ClassVar

from .test_client import GraphQLResult


class GraphQLClientMixin:
    """ GraphQL mixin for FastAPI test client """

    # URI of the GraphQL endpoint
    GRAPHQL_ENDPOINT: ClassVar[str]

    def graphql(self: _GraphQLClientMixinTarget, query: str, /, **variables) -> GraphQLResponse:
        """ Make a GraphQL query through the API

        NOTE: this is essential for E2E testing, but not too performant.
        Use GraphQLTestClient for the majority of your tests
        """
        # Send the request
        res: requests.Response = self.post(
            url=self.GRAPHQL_ENDPOINT,
            json=dict(
                query=query,
                variables=variables,
                operationName=None,
            ),
        )

        # It must be a 200 OK even in case of an error response
        assert res.ok, f'Bad response code: {res.status_code}: {res.content}'

        # Done
        return GraphQLResponse(res)


class _GraphQLClientMixinTarget(Protocol):
    """ Protocol: describes the target for GraphQLClientMixin """
    GRAPHQL_ENDPOINT: str

    def post(self, *, url: str, json: dict):
        raise NotImplementedError


@dataclass
class GraphQLResponse(GraphQLResult):
    """ GraphQL result + response object """
    # The original HTTP request object
    response: requests.Response

    def __init__(self, response: requests.Response):
        self.response = response
        super().__init__(response.json())
