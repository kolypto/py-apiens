import anyio
import pytest
import graphql

from apiens.tools.graphql.testing.test_client import GraphQLTestClient
from apiens.testing.object_match import DictMatch
from apiens.error import exc


@pytest.mark.asyncio
async def test_graphql_test_client():
    """ Testing the test client. Recursively :) """
    async def main():
        q_ok = 'query { ok }'
        q_fail = 'query { fail }'
        q_app_fail = 'query { app_fail }'
        q_count = 'subscription { count }'

        # === Test: sync query
        with GraphQLTestClient(schema) as c:
            # q_ok
            res = c.execute_sync(q_ok).successful()
            assert res.ok
            assert res.data == {'ok': 'ok'}
            assert res.errors == []
            assert res.exceptions == []
            assert res['ok'] == 'ok'

            # q_fail
            res = c.execute_sync(q_fail)
            assert not res.ok
            assert res.data == {'fail': None}
            assert res.errors == [DictMatch(
                message='Bad',
                path=['fail'],
            )]
            assert isinstance(res.exceptions[0], graphql.GraphQLError)
            assert res.exceptions[0].message == 'Bad'
            assert isinstance(res.exceptions[0].original_error, ValueError)
            assert res.exceptions[0].args == ('Bad',)

            with pytest.raises(ValueError):
                assert res['fail']
            with pytest.raises(ValueError):
                res.raise_errors()

            # q_app_fail
            res = c.execute_sync(q_app_fail)
            assert res.data == {'app_fail': None}
            assert res.errors == [DictMatch(
                message='Bad',
                path=['app_fail'],
            )]
            assert isinstance(res.exceptions[0], graphql.GraphQLError)
            assert res.exceptions[0].message == 'Bad'
            assert isinstance(res.exceptions[0].original_error, exc.E_API_ARGUMENT)
            assert res.exceptions[0].original_error.name == 'E_API_ARGUMENT'
            
            with pytest.raises(exc.E_API_ARGUMENT):
                assert res['fail']
            with pytest.raises(exc.E_API_ARGUMENT):
                res.raise_errors()
            
            assert res.app_error_name == 'E_API_ARGUMENT'
            assert res.graphql_error == res.exceptions[0]
            assert res.original_error == res.exceptions[0].original_error


        # === Test: async query
        with GraphQLTestClient(schema) as c:
            res = await c.execute_async(q_ok)
            assert res['ok'] == 'ok'

        # === Test: query
        with GraphQLTestClient(schema) as c:
            # Run it in a thread because it uses asyncio.run()
            res = await anyio.to_thread.run_sync(c.execute, q_ok)
            
            assert res['ok'] == 'ok'

        # === Test: subscription
        with GraphQLTestClient(schema) as c:
            res = c.subscribe(q_count)
            results = [item async for item in res]
            assert results == [
                {'count': 1},
                {'count': 2},
                {'count': 3},
            ]

    # Resolvers

    def resolve_ok(_, info):
        return 'ok'

    def resolve_fail(_, info):
        raise ValueError('Bad')
    
    def resolve_app_fail(_, info):
        raise exc.E_API_ARGUMENT('Bad', 'Tryagain', name='arg')

    async def subscribe_count(_, info):
        yield {'count': 1}
        yield {'count': 2}
        yield {'count': 3}

    # GraphQL objects
    Query = graphql.GraphQLObjectType('Query', fields={
        # A field that reports success
        'ok': graphql.GraphQLField(
            graphql.GraphQLString, 
            resolve=resolve_ok,
        ),
        # A field that returns a Python exception
        'fail': graphql.GraphQLField(
            graphql.GraphQLString,
            resolve=resolve_fail,
        ),
        # A field that returns Application Exception
        'app_fail': graphql.GraphQLField(
            graphql.GraphQLString,
            resolve=resolve_app_fail,
        ),
    })

    Subscription = graphql.GraphQLObjectType('Subscription', fields={
        # A field for testing subscriptions
        'count': graphql.GraphQLField(
            graphql.GraphQLInt,
            subscribe=subscribe_count,
        ),
        'count2': graphql.GraphQLField(
            graphql.GraphQLInt,
            subscribe=subscribe_count,
        ),
    })

    # GraphQL Schema
    schema = graphql.GraphQLSchema(
        query=Query,
        subscription=Subscription,
    )

    # Go
    await main()