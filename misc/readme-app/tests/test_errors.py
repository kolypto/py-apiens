import pytest
from apiens.testing.object_match import Whatever
from .conftest import ApiClient


def test_fastapi_error(api_client: ApiClient):
    # === Test: application error
    res = api_client.get('/app_error')
    assert res.json() == {
        'error': {
            'name': 'E_NOT_FOUND',
            'title': 'Not found',
            "error": "User not found by email",
            "fixit": "Please check the provided email",
            'httpcode': 404,
            'info': {
                'object': 'User',
                'email': 'user@example.com',
            },
            'debug': {},
        }
    }
    
    # === Test: internal server error
    with pytest.raises(RuntimeError):
        res == api_client.get('/unexpected_error')
        assert res.json() == {
            #... not caught
        }


def test_graphql_api_error(api_client: ApiClient):
    """ Test how API reports errors """
    # === Test: application error
    query = 'query { app_error }'
    
    res = api_client.graphql_sync(query)
    assert res.graphql_error == {
        'message': "Something went wrong",
        'path': ['app_error'],
        'locations': Whatever,
        'extensions': {
            # Application error info
            'error': {
                'name': 'E_API_ACTION',
                'httpcode': 400,
                'title': "Incorrect action",
                'error': "Something went wrong",
                'fixit': "Please try again",
                'info': {},
                'debug': {},
            },
            # Added by Ariadne
            'exception': {
                'context': Whatever,
                'stacktrace': Whatever,
            },
        },
    }

    # === Test: internal server error
    query = 'query { unexpected_error }'
    res = api_client.graphql_sync(query)
    assert res.graphql_error == {
        'message': 'Fail',
        'path': ['unexpected_error'],
        'locations': Whatever,
        'extensions': {
            # Application error info
            'error': {
                # F_UNEXPECTED_ERROR
                'name': 'F_UNEXPECTED_ERROR',
                'httpcode': 500,
                'title': 'Generic server error',
                'error': 'Fail',
                'fixit': 'Please try again in a couple of minutes. If the error does not go away, contact support and describe the issue',
                'info': {},
                'debug': {
                    # References errors with traceback
                    'errors': [
                        {
                            'msg': 'Fail',
                            'type': 'RuntimeError',
                            'trace': [
                                'middleware/unexpected_errors.py:unexpected_errors_middleware_impl',
                                'middleware/documented_errors.py:middleware',
                                'middleware/documented_errors.py:documented_errors_middleware_impl',
                                'graphql/query.py:resolve_unexpected_error',
                            ],
                        }
                    ]
                },
            },
            # Added by Ariadne
            'exception': {
                'context': Whatever,
                'stacktrace': Whatever,
            },
        }
    }

    # === Test: validation error: argument, input type field
    # language=graphql
    query = 'query ($first: Int) { list_users(first: $first) }'
    res = api_client.graphql_sync(query, first='INVALID')
    assert res.errors == [
        # Argument error: `first` got an invalid value
        {
            # 'message': "Int cannot represent non-integer value: 'INVALID'",  # the original
            'message': "Not a valid number",  # Improved, human-readable
            'locations': Whatever,
            'extensions': {
                # Added validation info
                'validation': {
                    'variable': 'first',
                    'path': ['first',],
                    'message': "Not a valid number",
                },
                # Added by Ariadne
                'exception': None,
            }
        },
    ]
    