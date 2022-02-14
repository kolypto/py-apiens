import logging
import pytest
import graphql
import ariadne

from apiens.structure.error import exc
from apiens.structure.func import UndocumentedError
from apiens.testing.object_match import Whatever
from apiens.tools.ariadne.testing.test_client import GraphQLTestClient
from apiens.tools.ariadne.format_error import application_error_formatter
from apiens.tools.graphql.middleware.documented_errors import documented_errors_middleware


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

        # === Test: internal server error
        res = c.execute_sync('query { serverError }')
        expected_error = {
            'message': 'Internal server error',
            'locations': Whatever,
            'path': ['serverError'],
        }
        if debug:
            expected_error['extensions'] = {
                'exception': {'stacktrace': Whatever, 'context': Whatever},
                # Application error: 'error' key is missing because
                # no middleware has converted the error to ApplicationError
                # 'error': N/A,
            }
        assert res.graphql_error == expected_error

    # GraphQL schema
    # language=graphql
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


def test_input_validation(caplog):
    """ Test how input validation errors are reported """
    def main(c: GraphQLTestClient):
        query_inputScalar = 'mutation ($age: Int!) { inputScalar(age: $age) }'
        query_inputScalarCustom = 'mutation ($age: PositiveInt!) { inputScalarCustom(age: $age) }'
        query_inputEnum = 'mutation ($letter: FavoriteLetter!) { inputEnum(letter: $letter) }'
        query_inputObject = 'mutation ($user: User!) { inputObject(user: $user) }'

        from apiens.tools.ariadne import rich_validation
        rich_validation.install_types_to_schema(schema)

        # ### Argument tests ### #
        # Argument tests fail because the query itself has something wrong with the argument.
        # Method argument may be missing, or have a wrong type.

        # === Test: Argument: variable not provided
        # inputScalar() wants an argument, but we do not provide any
        res = c.execute_sync('mutation { inputScalar }')
        assert res.graphql_error == {
            'message': "Field 'inputScalar' argument 'age' of type 'Int!' is required, but it was not provided.",
            'locations': Whatever,
            'path': None,
            'extensions': {'exception': None},
        }

        # === Test: Argument: wrong type provided
        # inputScalar() wants an `Int!`, but we provide something else
        res = c.execute_sync('mutation ($age: String!) { inputScalar(age: $age) }')
        assert res.graphql_error == {
            'message': "Variable '$age' of type 'String!' used in position expecting type 'Int!'.",
            'locations': Whatever,
            'path': None,
            'extensions': {'exception': None},
        }

        # === Test: Argument: nullable type provided
        # inputScalar() wants an `Int!`, but we provide a nullable `Int`
        res = c.execute_sync('mutation ($age: Int) { inputScalar(age: $age) }')
        assert res.graphql_error == {
            'message': "Variable '$age' of type 'Int' used in position expecting type 'Int!'.",
            'locations': Whatever,
            'path': None,
            'extensions': {'exception': None},
        }

        # ### Variable tests ### #
        # Tests where something's wrong with the variable.
        # No value provided, wrong type, null, or custom validation error

        # === Test: Variable: variable not provided
        assert c.execute_sync(query_inputScalar).graphql_error == {
            'message': "Variable '$age' of required type 'Int!' was not provided.",
            'locations': Whatever,
            'path': None,
            'extensions': {'exception': None},
        }

        # === Test: Variable: variable wrong type
        assert c.execute_sync(query_inputScalar, age='INVALID').graphql_error == {
            # 'message': "Variable '$age' got invalid value 'INVALID'; Int cannot represent non-integer value: 'INVALID'",  # original GraphQL error
            'message': "Variable '$age' got invalid value 'INVALID'; Not a valid number",
            'locations': Whatever,
            'path': None,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'age',
                    'path': ('age',),
                    'message': 'Not a valid number',
                },
            },
        }

        # === Test: Variable: variable must not be null
        assert c.execute_sync(query_inputScalar, age=None).graphql_error == {
            'message': "Variable '$age' of non-null type 'Int!' must not be null.",
            'locations': Whatever,
            'path': None,
            'extensions': {'exception': None},
        }

        # === Test: Variable: variable custom type failed
        assert c.execute_sync(query_inputScalarCustom, age=-1).graphql_error == {
            'message': "Variable '$age' got invalid value -1; Expected type 'PositiveInt'. Must be positive",
            'locations': Whatever,
            'path': None,
            'extensions': {
                'exception': {
                    'context': {'value': '-1'},
                    'stacktrace': Whatever,
                },
                'validation': {
                    'variable': 'age',
                    'path': ('age',),
                    'message': "Must be positive",
                },
            },
        }

        # ### Field tests ### #
        # Tests where a value fails inside a complex object, `User`.
        # A nested field's value is not provided, has a wrong type, or there's a custom validation error

        # === Test: Field: variable must be a dict
        assert c.execute_sync(query_inputObject, user='INVALID').graphql_error == {
            'message':  "Variable '$user' got invalid value 'INVALID'; Expected type 'User' to be a dict.",
            'locations': Whatever,
            'path': None,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'user',
                    'path': ('user',),
                    'message': "Expected type 'User' to be a dict.",
                },
            },
        }

        # === Test: Field: variable not provided
        assert c.execute_sync(query_inputObject, user={}).graphql_error == {
            'message': "Variable '$user' got invalid value {}; Field 'age' of required type 'Int!' was not provided.",
            'locations': Whatever,
            'path': None,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'user',
                    'path': ('user',),
                    'message': "Field 'age' of required type 'Int!' was not provided.",
                },
            },
        }

        # === Test: Field: variable wrong type
        assert c.execute_sync(query_inputObject, user={'age': 'INVALID'}).graphql_error == {
            # 'message': "Variable '$user' got invalid value 'INVALID' at 'user.age'; Int cannot represent non-integer value: 'INVALID'",  # original GraphQL error
            'message': "Variable '$user' got invalid value 'INVALID' at 'user.age'; Not a valid number",
            'locations': Whatever,
            'path': None,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'user',
                    'path': ('user', 'age',),
                    'message': "Not a valid number",
                },
            },
        }

        # === Test: Field: variable must not be null
        assert c.execute_sync(query_inputObject, user={'age': None}).graphql_error == {
            'message': "Variable '$user' got invalid value None at 'user.age'; Expected non-nullable type 'Int!' not to be None.",
            'locations': Whatever,
            'path': None,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'user',
                    'path': ('user', 'age',),
                    'message': "Expected non-nullable type 'Int!' not to be None.",
                },
            },
        }

        # === Test: Field: variable custom type failed
        assert c.execute_sync(query_inputObject, user={'age': -1, 'positiveAge': -1}).graphql_error == {
            'message': "Variable '$user' got invalid value -1 at 'user.positiveAge'; Expected type 'PositiveInt'. Must be positive",
            'locations': Whatever,
            'path': None,
            'extensions': {
                'exception': {
                    'context': {'value': '-1'},
                    'stacktrace': Whatever,
                },
                'validation': {
                    'variable': 'user',
                    'path': ('user', 'positiveAge'),
                    'message': 'Must be positive',
                },
            },
        }

        # === Test: Field: nested nested: variable wrong type
        assert c.execute_sync(query_inputObject, user={'age': 0, 'parent': {'age': 'INVALID'}}).graphql_error == {
            # 'message': "Variable '$user' got invalid value 'INVALID' at 'user.parent.age'; Int cannot represent non-integer value: 'INVALID'",  # original GraphQL error
            'message': "Variable '$user' got invalid value 'INVALID' at 'user.parent.age'; Not a valid number",
            'locations': Whatever,
            'path': None,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'user',
                    'path': ('user', 'parent', 'age'),
                    'message': 'Not a valid number',
                },
            },
        }


        # === Test: enum: wrong value
        assert c.execute_sync(query_inputEnum, letter='Z').graphql_error == {
            'message': "Variable '$letter' got invalid value 'Z'; Value 'Z' does not exist in 'FavoriteLetter' enum. Did you mean the enum value 'A', 'B', or 'C'?",
            'locations': Whatever,
            'path': None,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'letter',
                    'path': ('letter',),
                    # This message is not user-friendly, but it should never be raised because of a user error
                    'message': "Value 'Z' does not exist in 'FavoriteLetter' enum. Did you mean the enum value 'A', 'B', or 'C'?",
                },
            },
        }

    # GraphQL schema
    #language=graphql
    gql_schema = '''
    type Query { hello: String }
    
    type Mutation {
        # Test: scalar, non-null
        inputScalar(age: Int!): Void
        # Test: scalar, custom
        inputScalarCustom(age: PositiveInt!): Void
        # Test: object, non-null
        # Test: embedded object
        inputObject(user: User!): Void
        # Test: enum
        inputEnum(letter: FavoriteLetter!): Void
    }
    
    input User {
        # Object fields: scalars
        age: Int!
        positiveAge: PositiveInt
        # Object fields: embedded
        parent: User
    }
    
    scalar Void
    scalar PositiveInt
    
    enum FavoriteLetter {
        A B C
    }
    '''

    Mutation = ariadne.MutationType()

    PositiveInt = ariadne.ScalarType('PositiveInt')
    @PositiveInt.value_parser
    def positive_int_value(value: str):
        value = int(value)
        if value <= 0:
            raise ValueError('Must be positive')
        return value

    schema = ariadne.make_executable_schema(
        gql_schema,
        PositiveInt,
        Mutation,
    )

    # Go
    with GraphQLTestClient(schema, debug=True, error_formatter=application_error_formatter) as c:
        main(c)


def test_documented_errors():
    def main(c: GraphQLTestClient):
        # A field raises undocumented error
        res = c.execute_sync('query { undocumented }')
        assert isinstance(res.original_error, UndocumentedError)

        # A field raises documented error
        res = c.execute_sync('query { documented }')
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
    with GraphQLTestClient(schema, debug=True, error_formatter=application_error_formatter) as c:
        c.middleware = middleware
        main(c)


@pytest.fixture(autouse=True)
def no_graphql_test_client_logging(caplog):
    # Don't log all these annoying GraphQL errors. They're all expected and welcome.
    caplog.set_level(logging.CRITICAL, logger="apiens.tools.ariadne.testing.test_client")
