from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import requests  # type: ignore[import]
from typing_extensions import ClassVar

from .test_client import GraphQLResult



class GraphQLClientMixinTarget(Protocol):
    """ Protocol: describes the target for GraphQLClientMixin """
    def post(self, *, url: str, json: dict):
        raise NotImplementedError


class GraphQLClientMixin(GraphQLClientMixinTarget):
    """ GraphQL mixin for FastAPI test client

    Example:

        from apiens.tools.fastapi.test_client import TestClient

        class MyApiTestClient(TestClient, GraphQLClientMixin):
            GRAPHQL_ENDPOINT = f'{settings.API}/graphql/'
    """

    # URI of the GraphQL endpoint
    GRAPHQL_ENDPOINT: ClassVar[str]

    def graphql_sync(self, query: str, /, **variables) -> GraphQLResponse:
        """ Make a GraphQL query through the API

        NOTE: this is essential for E2E testing, but not too performant.
        Use GraphQLTestClient for the majority of your tests
        """
        # Send the request
        res = self.graphql_sync_request(query, **variables)

        # It must be a 200 OK even in case of an error response
        assert res.response.ok, f'Bad response code: {res.response.status_code}: {res.response.content}'

        # Done
        return res

    def graphql_sync_request(self, query: str, /, **variables) -> GraphQLResponse:
        """ Make a GraphQL HTTP request and get a response """
        res: requests.Response = self.post(
            url=self.GRAPHQL_ENDPOINT,
            json=dict(
                query=query,
                variables=variables,
                operationName=None,
            ),
        )
        return GraphQLResponse(res)

@dataclass
class GraphQLResponse(GraphQLResult):
    """ GraphQL result + response object """
    # The original HTTP request object
    response: requests.Response

    def __init__(self, response: requests.Response):
        self.response = response
        super().__init__(response.json())
