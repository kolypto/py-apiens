import graphql
import ariadne
import ariadne.asgi

from apiens.error import exc
from apiens.structure.func.documented_errors import UndocumentedError
from apiens.tools.ariadne.testing.test_client import AriadneTestClient
from apiens.tools.ariadne.errors.format_error import application_error_formatter
from apiens.tools.graphql.middleware.documented_errors import documented_errors_middleware


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
