import pytest
import graphql
import ariadne
import ariadne.asgi
from functools import partial

from apiens.tools.ariadne.testing.test_client import AriadneTestClient
from apiens.tools.graphql.resolver.resolver_marker import resolves_in_threadpool, resolves_nonblocking, assert_no_unmarked_resolvers


@pytest.mark.parametrize('fail', (False, True))
def test_resolver_markers(fail: bool):
    def main(c: AriadneTestClient):
        # === Test: run validation to make sure all resolvers are fine
        if not fail:
            assert_no_unmarked_resolvers(schema)
        else:
            with pytest.raises(AssertionError) as e:
                assert_no_unmarked_resolvers(schema)
            assert 'resolve_threaded' in str(e.value)
            assert 'resolve_nonblocking' in str(e.value)
            assert 'resolve_object' in str(e.value)
            assert 'resolve_async' not in str(e.value)
            assert 'ariadne' not in str(e.value)

        # === Test: everything works
        res = c.execute('query { async threaded nonblocking object { a b c } }')
        assert res.successful().data == {
            'async': 'async',
            'threaded': 'threaded',
            'nonblocking': 'nonblocking',
            'object': {
                'a': 1,
                'b': 2,
                'c': 3,
            },
        }

    # Decorators and no-op decorators.
    # If we expect to fail, decorators should do nothing
    if fail:
        resolves_in_threadpool = resolves_nonblocking = lambda f: f
    else:
        from apiens.tools.graphql.resolver.resolver_marker import (
            resolves_nonblocking, resolves_in_threadpool
        )


    # Resolvers:
    # Three types:
    # 1. async function
    # 2. sync function run in threadpool
    # 3. sync function, non-blocking
    QueryType = ariadne.QueryType()

    @QueryType.field('async')
    async def resolve_async(_, info: graphql.GraphQLResolveInfo):  # async functions don't need to be decorated
        return 'async'

    @QueryType.field('threaded')
    @resolves_in_threadpool
    def resolve_threaded(_, info: graphql.GraphQLResolveInfo):
        import time
        time.sleep(1)
        return 'threaded'

    @QueryType.field('nonblocking')
    @resolves_nonblocking
    def resolve_nonblocking(_, info: graphql.GraphQLResolveInfo):
        return 'nonblocking'

    @QueryType.field('object')
    @resolves_nonblocking
    def resolve_object(_, info: graphql.GraphQLResolveInfo):
        return {'a': 1, 'b': 2, 'c': 3}

    # Test partial() resolvers because they may obstruct access to the decorator
    QueryType.set_field('another_object', partial(resolve_object))

    # language=graphql
    schema = ariadne.make_executable_schema('''
    type Query {
        async: String!
        threaded: String!
        nonblocking: String!
        object: ABC!
        another_object: ABC
    }

    type ABC {
        a: Int!
        b: Int!
        c: Int!
    }
    ''', QueryType, ariadne.snake_case_fallback_resolvers)

    # Go
    with AriadneTestClient(schema, debug=True) as c:
        main(c)
