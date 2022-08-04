""" A Mixin for your API test client to support GraphQL requests """

from __future__ import annotations

import requests  # type: ignore[import]
import starlette.testclient
from dataclasses import dataclass
from collections import abc
from typing import Protocol, ClassVar

from .test_client import GraphQLResult


class GraphQLClientMixinTarget(Protocol):
    """ Protocol: describes the target for GraphQLClientMixin """
    headers: abc.Mapping[str, str]

    def post(self, *, url: str, json: dict):
        raise NotImplementedError

    def websocket_connect(self, url: str, *args, **kwargs) -> starlette.websockets.WebSocket:
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

    def graphql_subscribe(self, query: str, /, **variables) -> abc.Iterator[GraphQLResult]:
        """ Make a GraphQL WS subscription request and iterate over the data it returns """
        ws: starlette.testclient.WebSocketTestSession
        with self.websocket_connect(self.GRAPHQL_ENDPOINT) as ws:  # type: ignore[attr-defined]
            # Send: connection_init
            ws.send_json({
                'type': 'connection_init',
                'payload': {
                    # Over websockets, you can't pass additional data to the server via HTTP headers.
                    # To work around this limitation, websocket clients include this data in initial
                    # message sent to the server as part of connection negotiation.
                    **self.headers,
                },
            })
            res = ws.receive_json()
            assert res == {'type': 'connection_ack'}

            # Send the actual request
            ws.send_json({
                'id': 1,
                'type': 'start',
                'payload': {
                    'query': query,
                    'variables': variables,
                    'operationName': None,
                    'extensions': {},
                }
            })

            # Keep getting results
            while True:
                res = ws.receive_json()
                assert res['id'] == 1

                # "data" response: payload
                if res['type'] == 'data':
                    yield GraphQLResult(res['payload'])
                # "complete" response: no more data
                elif res['type'] == 'complete':
                    return
                elif res['type'] == 'error':
                    ws.close()
                    yield GraphQLResult({'data': None, 'errors': [res['payload']]})
                    return
                # don't know what to do
                else:
                    raise NotImplementedError(res['type'])

@dataclass
class GraphQLResponse(GraphQLResult):
    """ GraphQL result + response object """
    # The original HTTP request object
    response: requests.Response

    def __init__(self, response: requests.Response):
        self.response = response
        super().__init__(response.json())
