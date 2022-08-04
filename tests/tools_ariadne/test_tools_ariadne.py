import logging
import pytest
import graphql
import ariadne
import ariadne.asgi
import starlette.applications
import starlette.websockets
from collections import abc

from apiens.tools.ariadne.testing.test_client import AriadneTestClient


@pytest.mark.skipif(not hasattr(ariadne.asgi.GraphQL, 'create_json_response'), reason='Ariadne compatibility')
@pytest.mark.skipif(starlette.__version__ == '0.13.4', reason="Test fails for this old version and I'm lazy to fix")
def test_asgi_finalizing_app():
    import starlette.requests
    import starlette.testclient
    import starlette.applications
    import starlette.routing

    def main(c: starlette.testclient.TestClient):
        nonlocal context_init_should_fail, finalize_request_should_fail
        query = ''' query { _ } '''

        # === Test: ok request
        res = c.post('/graphql', json={'query': query})
        assert res.status_code == 200
        assert res.json() == {
            'data': {'_': None}
        }

        # === Test: fail before request
        context_init_should_fail = True
        finalize_request_should_fail = False

        res = c.post('/graphql', json={'query': query})
        assert res.status_code == 200
        assert res.json() == {
            'data': None,
            'errors': [
                {'message': 'Failed:context', 'extensions':{'where': 'before-request'}},
            ]
        }


        # === Test: fail after request
        context_init_should_fail = False
        finalize_request_should_fail = True

        res = c.post('/graphql', json={'query': query})
        assert res.status_code == 200
        assert res.json() == {
            'data': None,
            'errors': [
                {'message': 'Failed:finalize', 'extensions':{'where': 'after-request'}},
            ]
        }

    # language=graphql
    schema = ariadne.make_executable_schema('''
        type Query {
            _: Int
        }
    ''')

    # Context
    context_init_should_fail = False
    def context_value_provider(request: starlette.requests.Request):
        # Fail on purpose
        if context_init_should_fail:
            raise AssertionError('Failed:context')

        # Init context -- and store it into the request where it can be found
        context = {
            'value': 'context-value'
        }
        request.state.graphql_context = context
        return context

    # Finalizing application
    from apiens.tools.ariadne.asgi_finalizing import FinalizingGraphQL

    finalize_request_should_fail = False
    class App(FinalizingGraphQL):
        async def finalize_request(self, request: starlette.requests.Request) -> tuple[bool, abc.Iterable[Exception]]:
            if finalize_request_should_fail:
                return True, (
                    AssertionError('Failed:finalize'),
                )
            else:
                return False, ()

    # Init app
    app = App(schema, context_value=context_value_provider)
    app = starlette.applications.Starlette(debug=True, routes=[
        starlette.routing.Route('/graphql', app)
    ])

    # Go
    with starlette.testclient.TestClient(app) as c:
        main(c)


@pytest.fixture(autouse=True)
def no_graphql_test_client_logging(caplog):
    # Don't log all these annoying GraphQL errors. They're all expected and welcome.
    caplog.set_level(logging.CRITICAL, logger="apiens.tools.ariadne.testing.test_client")


from starlette import __version__ as STARLETTE_VERSION
STARLETTE_VERSION_TUPLE: tuple[int, ...] = tuple(map(int, STARLETTE_VERSION.split('.')))


@pytest.mark.asyncio
@pytest.mark.skipif(STARLETTE_VERSION_TUPLE < (0, 15, 0), reason=(
    "This test fails with older Starlette versions: when we subscribe(), it attempts to start another even loop "
    "within the loop that's already running. Nested loops are not allowed. But never versions fixed this."
))
async def test_subscriptions():
    """ Test how subscriptions work """
    async def main():
        # === Test: AriadneTestClient
        with AriadneTestClient(schema, debug=True) as c:
            sub = c.subscribe("subscription { updates }")
            results = [result['updates'] async for result in sub]
            assert results == ['#1', '#2', '#3']

        # === Test: APITest
        with APITestClient(app) as c:
            # Load all results
            res = [result['updates'] for result in c.graphql_subscribe("subscription { updates }")]
            assert res == ['#1', '#2', '#3']

            # Load one result
            res = next(c.graphql_subscribe("subscription { updates }"))
            assert res['updates'] == '#1'

    # Schema
    gql_schema = '''
    type Query {
        _: ID
    }

    type Subscription {
        updates: ID!
    }
    '''

    # Subscription that generates integers, with a resolver that converts them into strings
    Subscription = ariadne.SubscriptionType()

    @Subscription.field('updates')
    def resolve_updates(value: int, info: graphql.GraphQLResolveInfo):
        return f'#{value}'

    @Subscription.source('updates')
    async def generate_updates(_, info: graphql.GraphQLResolveInfo):
        yield 1
        yield 2
        yield 3

    # Init schema
    schema = ariadne.make_executable_schema(gql_schema, Subscription)

    # Init Starlette as an ASGI app (for websockets)
    graphql_app = ariadne.asgi.GraphQL(schema)
    app = starlette.applications.Starlette(debug=True)
    app.mount('/', graphql_app)

    # Prepare a test client
    from apiens.tools.fastapi.test_client import TestClient
    from apiens.tools.ariadne.testing.test_client_api import GraphQLClientMixin

    class APITestClient(TestClient, GraphQLClientMixin):
        GRAPHQL_ENDPOINT = '/'


    # Go
    await main()
