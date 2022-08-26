import pytest
import graphql
import ariadne
import ariadne.asgi

from apiens.error import exc
from apiens.testing.object_match import ObjectMatch
from apiens.structure.func.documented_errors import UndocumentedError
from apiens.tools.ariadne.testing.test_client import AriadneTestClient
from apiens.tools.ariadne.errors.format_error import application_error_formatter
from apiens.tools.graphql.middleware.documented_errors import documented_errors_middleware
from apiens.tools.graphql.middleware.unexpected_errors import unexpected_errors_middleware


def test_documented_errors():
    def main(c: AriadneTestClient):
        # A field raises undocumented error
        res = c.execute('query { undocumented }')
        assert isinstance(res.original_error, UndocumentedError)

        # A field raises documented error
        res = c.execute('query { documented }')
        assert res.app_error_name == 'E_AUTH_REQUIRED'


    # GraphQL schema
    #language=graphql
    gql_schema = '''
    type Query {
        """ Documentation missing """
        undocumented: String

        """ Documented

        Errors:
            E_AUTH_REQUIRED: when not authenticated
        """
        documented: String
    }
    '''

    QueryType = ariadne.QueryType()

    @QueryType.field('undocumented')
    @QueryType.field('documented')
    def resolve_error_auth_required(_, info):
        raise exc.E_AUTH_REQUIRED('Unauth', 'Auth')

    schema = ariadne.make_executable_schema(gql_schema, QueryType)

    # Middleware
    middleware = graphql.MiddlewareManager(
        documented_errors_middleware(),
    )

    # Go
    with AriadneTestClient(schema, debug=True, error_formatter=application_error_formatter) as c:
        c.middleware = middleware
        main(c)


@pytest.mark.asyncio
async def test_unexpected_errors_middleware():
    async def main():
        # Application error
        res = await graphql_async('query { app_error }')
        error = res.errors[0]
        assert error.original_error.name == 'E_API_ACTION'

        # Unexpected error
        res = await graphql_async('query { unexpected_error }')
        error = res.errors[0]
        assert error.original_error.name == 'F_UNEXPECTED_ERROR'


    # Schema
    def resolve_application_error(_, info):
        raise exc.E_API_ACTION('Fail', 'Fix')
    
    def resolve_unexpected_error(_, info):
        raise RuntimeError('Bad')

    Query = graphql.GraphQLObjectType('Query', fields={
        # A field that reports success
        'app_error': graphql.GraphQLField(
            graphql.GraphQLString, 
            resolve=resolve_application_error,
        ),
        'unexpected_error': graphql.GraphQLField(
            graphql.GraphQLString,
            resolve=resolve_unexpected_error,
        )
    })
    
    # GraphQL Schema
    schema = graphql.GraphQLSchema(query=Query)

    # Middleware
    middleware = graphql.MiddlewareManager(
        unexpected_errors_middleware(exc=exc)
    )

    # query
    async def graphql_async(query: str):
        return await graphql.graphql(
            schema, 
            query,
            middleware=middleware,
        )
    
    # Go
    await main() 