import pytest
import graphql
import ariadne

from apiens.structure.error import exc
from apiens.tools.ariadne.testing.test_client import GraphQLTestClient
from apiens.tools.ariadne.format_error import application_error_formatter


@pytest.mark.parametrize('debug', [True, False])
def test_graphql_exception_handlers(debug: bool):
    def main(c: GraphQLTestClient):
        # === Test: hello()
        res = c.execute_sync('query { hello }')
        assert res['hello'] == 'hi'

        # === Test: Application error
        res = c.execute_sync('query { applicationError }')
        assert res.app_error == {
            'httpcode': 401,
            'name': 'E_AUTH_REQUIRED',
            'title': exc.E_AUTH_REQUIRED.title,
            'error': 'Need auth',
            'fixit': 'Sign in',
            'info': {},
            'debug': {} if debug else None,
        }
        if debug:
            assert isinstance(res.original_error, exc.E_AUTH_REQUIRED)
        else:
            assert res.original_error is None

    # GraphQL schema
    gql_schema = '''
    type Query {
        hello: String!
        applicationError: ID
        serverError: ID
    }
    '''

    Query = ariadne.QueryType()

    @Query.field('hello')
    def resolve_hello(_, info: graphql.GraphQLResolveInfo):
        return 'hi'

    @Query.field('applicationError')
    def resolve_application_error(_, info: graphql.GraphQLResolveInfo):
        raise exc.E_AUTH_REQUIRED(error='Need auth', fixit='Sign in')

    @Query.field('serverError')
    def resolve_server_error(_, info: graphql.GraphQLResolveInfo):
        # Python exceptions are converted into F_UNEXPECTED_ERROR
        raise RuntimeError('Internal server error')

    schema = ariadne.make_executable_schema(
        gql_schema,
        Query,
    )

    # Go
    with GraphQLTestClient(schema, debug=debug, error_formatter=application_error_formatter) as c:
        main(c)
