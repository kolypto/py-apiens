import graphql
import ariadne
import ariadne.asgi

from apiens.error import exc
from apiens.testing.object_match import Whatever, DictMatch
from apiens.tools.ariadne.testing.test_client import AriadneTestClient
from apiens.tools.ariadne.errors.format_error import application_error_formatter
from apiens.tools.ariadne.testing.query import graphql_query_sync
from apiens.tools.graphql.errors.error_extensions import add_graphql_error_extensions


def test_graphql_application_error_extensions():
    """ Test: add_graphql_error_extensions() """
    e = graphql.GraphQLError(
        'Failed',
        original_error=exc.F_FAIL('Failed', 'Tryagain')
    )
    add_graphql_error_extensions(e, debug=True)
    add_graphql_error_extensions(e, debug=True)  # okay to do it twice

    assert e.formatted == DictMatch({
        'message': 'Failed',
        'extensions': {
            'error': {
                'name': 'F_FAIL',
                'httpcode': 500,
                'title': exc.F_FAIL.title,
                'error': 'Failed',
                'fixit': 'Tryagain',
                'info': {},
                'debug': {},
            },
        },
    })


def test_human_readable_scalars():
    def main():
        # Test: default error messages
        #language=GraphQL
        query = '''
            query ($int: Int!, $float: Float!, $bool: Boolean!) {
                input(int: $int, float: $float, bool: $bool)
            }
        '''
        res = graphql_query_sync(schema, query, int='Z', float='Z', bool='Z')
        
        # Predictable testability: sort()
        res.exceptions.sort(key=lambda v: v.message)

        # add_graphql_error_extensions() can augment such errors
        for error in res.exceptions:
            add_graphql_error_extensions(error)
        
        # Check messages
        messages = [error.message for error in res.exceptions]
        assert messages == [
            # These messages are non-standard :)
            "Not a valid yes/no value",
            "Not a valid number",
            "Not a valid number",
        ]

        # Check extensions
        assert [error.extensions for error in res.exceptions] == [
            {'validation': {'path': ('bool',), 'variable': 'bool', 'message': 'Not a valid yes/no value'}},
            {'validation': {'path': ('float',), 'variable': 'float', 'message': 'Not a valid number'}},
            {'validation': {'path': ('int',), 'variable': 'int', 'message': 'Not a valid number'}},
        ]


    #language=GraphQL
    schema_gql = '''
        type Query {
            input(int: Int!, float: Float!, bool: Boolean!): String
        }
    '''
    schema = ariadne.make_executable_schema(schema_gql)

    from apiens.tools.graphql.errors.human_readable import install_types_to_schema
    install_types_to_schema(schema)

    # Go
    main()



def test_graphql_exception_handlers():
    """ Test application_error_formatter() """
    def main(c: AriadneTestClient):
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
            'debug': {},
        }
        assert isinstance(res.original_error, exc.E_AUTH_REQUIRED)

        # === Test: internal server error
        res = c.execute_sync('query { serverError }')
        expected_error = {
            'message': 'Internal server error',
            'locations': Whatever,
            'path': ['serverError'],
        }
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
    with AriadneTestClient(schema, debug=True, error_formatter=application_error_formatter) as c:
        main(c)


def test_input_validation():
    """ Test: application_error_formatter(). How input validation messages are reported. Must be user-friendly. """
    def main(c: AriadneTestClient):
        query_inputScalar = 'mutation ($age: Int!) { inputScalar(age: $age) }'
        query_inputScalarCustom = 'mutation ($age: PositiveInt!) { inputScalarCustom(age: $age) }'
        query_inputEnum = 'mutation ($letter: FavoriteLetter!) { inputEnum(letter: $letter) }'
        query_inputObject = 'mutation ($user: User!) { inputObject(user: $user) }'

        from apiens.tools.graphql.errors import human_readable
        human_readable.install_types_to_schema(schema)

        # ### Argument tests ### #
        # Argument tests fail because the query itself has something wrong with the argument.
        # Method argument may be missing, or have a wrong type.

        # === Test: Argument: variable not provided
        # inputScalar() wants an argument, but we do not provide any
        res = c.execute_sync('mutation { inputScalar }')
        assert dict(res.graphql_error) == DictMatch({
            'message': "Field 'inputScalar' argument 'age' of type 'Int!' is required, but it was not provided.",
            'locations': Whatever,
            'extensions': {'exception': None},
        })

        # === Test: Argument: wrong type provided
        # inputScalar() wants an `Int!`, but we provide something else
        res = c.execute_sync('mutation ($age: String!) { inputScalar(age: $age) }')
        assert dict(res.graphql_error) == DictMatch({
            'message': "Variable '$age' of type 'String!' used in position expecting type 'Int!'.",
            'locations': Whatever,
            'extensions': {'exception': None},
        })

        # === Test: Argument: nullable type provided
        # inputScalar() wants an `Int!`, but we provide a nullable `Int`
        res = c.execute_sync('mutation ($age: Int) { inputScalar(age: $age) }')
        assert dict(res.graphql_error) == DictMatch({
            'message': "Variable '$age' of type 'Int' used in position expecting type 'Int!'.",
            'locations': Whatever,
            'extensions': {'exception': None},
        })

        # ### Variable tests ### #
        # Tests where something's wrong with the variable.
        # No value provided, wrong type, null, or custom validation error

        # === Test: Variable: variable not provided
        assert dict(c.execute_sync(query_inputScalar).graphql_error) == DictMatch({
            'message': "Variable '$age' of required type 'Int!' was not provided.",
            'locations': Whatever,
            'extensions': {'exception': None},
        })

        # === Test: Variable: variable wrong type
        assert dict(c.execute_sync(query_inputScalar, age='INVALID').graphql_error) == DictMatch({
            # 'message': "Variable '$age' got invalid value 'INVALID'; Int cannot represent non-integer value: 'INVALID'",  # original GraphQL error
            'message': "Not a valid number",
            'locations': Whatever,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'age',
                    'path': ('age',),
                    'message': 'Not a valid number',
                },
            },
        })

        # === Test: Variable: variable must not be null
        assert dict(c.execute_sync(query_inputScalar, age=None).graphql_error) == DictMatch({
            'message': "Variable '$age' of non-null type 'Int!' must not be null.",
            'locations': Whatever,
            'extensions': {'exception': None},
        })

        # === Test: Variable: variable custom type failed
        assert dict(c.execute_sync(query_inputScalarCustom, age=-1).graphql_error) == DictMatch({
            'message': "Must be positive",
            'locations': Whatever,
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
        })

        # ### Field tests ### #
        # Tests where a value fails inside a complex object, `User`.
        # A nested field's value is not provided, has a wrong type, or there's a custom validation error

        # === Test: Field: variable must be a dict
        DICT_NAME = 'dict' if graphql.version_info < (3, 2, 0) else 'mapping'
        assert dict(c.execute_sync(query_inputObject, user='INVALID').graphql_error) == DictMatch({
            'message':  f"Expected type 'User' to be a {DICT_NAME}.",
            'locations': Whatever,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'user',
                    'path': ('user',),
                    'message': f"Expected type 'User' to be a {DICT_NAME}.",
                },
            },
        })

        # === Test: Field: variable not provided
        assert dict(c.execute_sync(query_inputObject, user={}).graphql_error) == DictMatch({
            'message': "Field 'age' of required type 'Int!' was not provided.",
            'locations': Whatever,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'user',
                    'path': ('user',),
                    'message': "Field 'age' of required type 'Int!' was not provided.",
                },
            },
        })

        # === Test: Field: variable wrong type
        assert dict(c.execute_sync(query_inputObject, user={'age': 'INVALID'}).graphql_error) == DictMatch({
            # 'message': "Variable '$user' got invalid value 'INVALID' at 'user.age'; Int cannot represent non-integer value: 'INVALID'",  # original GraphQL error
            'message': "Not a valid number",
            'locations': Whatever,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'user',
                    'path': ('user', 'age',),
                    'message': "Not a valid number",
                },
            },
        })

        # === Test: Field: variable must not be null
        assert dict(c.execute_sync(query_inputObject, user={'age': None}).graphql_error) == DictMatch({
            'message': "Expected non-nullable type 'Int!' not to be None.",
            'locations': Whatever,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'user',
                    'path': ('user', 'age',),
                    'message': "Expected non-nullable type 'Int!' not to be None.",
                },
            },
        })

        # === Test: Field: variable custom type failed
        assert dict(c.execute_sync(query_inputObject, user={'age': -1, 'positiveAge': -1}).graphql_error) == DictMatch({
            'message': "Must be positive",
            'locations': Whatever,
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
        })

        # === Test: Field: nested nested: variable wrong type
        assert dict(c.execute_sync(query_inputObject, user={'age': 0, 'parent': {'age': 'INVALID'}}).graphql_error) == DictMatch({
            # 'message': "Variable '$user' got invalid value 'INVALID' at 'user.parent.age'; Int cannot represent non-integer value: 'INVALID'",  # original GraphQL error
            'message': "Not a valid number",
            'locations': Whatever,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'user',
                    'path': ('user', 'parent', 'age'),
                    'message': 'Not a valid number',
                },
            },
        })


        # === Test: enum: wrong value
        assert dict(c.execute_sync(query_inputEnum, letter='Z').graphql_error) == DictMatch({
            'message': "Value 'Z' does not exist in 'FavoriteLetter' enum. Did you mean the enum value 'A', 'B', or 'C'?",
            'locations': Whatever,
            'extensions': {
                'exception': None,
                'validation': {
                    'variable': 'letter',
                    'path': ('letter',),
                    # This message is not user-friendly, but it should never be raised because of a user error
                    'message': "Value 'Z' does not exist in 'FavoriteLetter' enum. Did you mean the enum value 'A', 'B', or 'C'?",
                },
            },
        })

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
    with AriadneTestClient(schema, debug=True, error_formatter=application_error_formatter) as c:
        main(c)
