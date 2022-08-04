import graphql
import ariadne
import ariadne.asgi

from apiens.tools.ariadne.testing.test_client import AriadneTestClient
from apiens.tools.graphql.resolver.resolver_marker import resolves_nonblocking, resolves_in_threadpool, assert_no_unmarked_resolvers


def test_resolver_markers():
    def main(c: AriadneTestClient):
        # === Test: run validation to make sure all resolvers are fine
        assert_no_unmarked_resolvers(schema)

        # === Test: GraphQL Test Client
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

    # Resolvers:
    # Three types:
    # 1. async function
    # 2. sync function run in threadpool
    # 3. sync function, non-blocking
    QueryType = ariadne.QueryType()

    @QueryType.field('async')
    async def resolve_async(_, info: graphql.GraphQLResolveInfo):
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

    # language=graphql
    schema = ariadne.make_executable_schema('''
    type Query {
        async: String!
        threaded: String!
        nonblocking: String!
        object: ABC!
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
