import pydantic as pd

import fastapi
import fastapi.testclient
import pytest

from apiens.error import exc
from apiens.testing.object_match import Parameter, Whatever
from apiens.tools.fastapi.exception_handlers import register_application_exception_handlers


@pytest.mark.parametrize('debug', [True, False])
def test_fastapi_exception_handlers(debug: bool):
    def main():
        # === Test: route suggestions
        res = c.get('/')
        assert res.status_code == 404
        if debug:
            assert res.json() == {
                'detail': 'API not found',
                'suggestions': ['GET /docs', 'GET /redoc'],
            }
        else:
            assert res.json() == {
                'detail': 'Not Found',
            }

        # === Test: application errors
        res = c.get('/application-error')
        assert res.status_code == 401
        assert res.json() == {
            'error': {
                'httpcode': 401,
                'name': 'E_AUTH_REQUIRED',
                'title': exc.E_AUTH_REQUIRED.title,
                'error': 'Need auth',
                'fixit': 'Sign in',
                'info': {},
                'debug': {} if debug else None,
            }
        }

        # === Test: internal server error
        res = c.get('/server-error')
        assert res.status_code == exc.F_UNEXPECTED_ERROR.httpcode
        assert res.json() == {
            'error': {
                'httpcode': 500,
                'name': 'F_UNEXPECTED_ERROR',
                'title': exc.F_UNEXPECTED_ERROR.title,
                'error': 'Internal server error',
                'fixit': (fixit := Parameter()),
                'info': {},
                'debug': (
                    {
                        'errors': [
                            {'type': 'RuntimeError', 'msg': 'Internal server error', 'trace': (trace := Parameter())}
                        ]
                    }
                    if debug else
                    None
                ),
            }
        }
        assert fixit.value.startswith('Please try again')
        if debug:
            assert trace.value[-1] == 'tools_fastapi/test_tools_fastapi.py:server_error'

        # === Test: request validation error
        res = c.post('/validation/request', json={'user': {}})
        assert res.json() == {
            'error': {
                'httpcode': 400,
                'name': 'E_CLIENT_VALIDATION',
                'title': exc.E_CLIENT_VALIDATION.title,
                'error': 'Invalid input',
                'fixit': 'Please fix the data you have provided and try again',
                'info': {
                    'model': 'Request',
                    'errors': [
                        {'loc': ['body', 'login'], 'msg': 'field required', 'type': 'value_error.missing'},
                    ],
                },
                'debug': {} if debug else None,
            }
        }

        # === Test: validation user
        res = c.get('/validation/user')
        assert res.status_code == exc.F_UNEXPECTED_ERROR.httpcode
        assert res.json() == {
            'error': {
                'httpcode': 500,
                'name': 'F_UNEXPECTED_ERROR',
                'title': exc.F_UNEXPECTED_ERROR.title,
                'error': (error := Parameter()),
                'fixit': (fixit := Parameter()),
                'info': {
                    'model': 'User',
                    'errors': [
                        {'loc': ['login'], 'msg': 'none is not an allowed value', 'type': 'type_error.none.not_allowed'},
                    ]
                },
                'debug': (
                    {
                        'errors': [
                            {'type': 'ValidationError', 'msg': error, 'trace': Whatever}
                        ]
                    }
                    if debug else
                    None
                ),
            }
        }
        assert 'none is not an allowed value' in error.value
        assert fixit.value.startswith('Please try again')

    # Set up the FastAPI application
    app = fastapi.FastAPI(debug=debug)

    # Endpoint: test application errors
    @app.get('/application-error')
    def application_error():
        raise exc.E_AUTH_REQUIRED(error='Need auth', fixit='Sign in')

    # Endpoint: test F_UNEXPECTED_ERROR: Internal Server Error
    @app.get('/server-error')
    def server_error():
        # Python exceptions are converted into F_UNEXPECTED_ERROR
        raise RuntimeError('Internal server error')

    # Endpoint: test FastAPI request validation
    class User(pd.BaseModel):
        login: str

    @app.post('/validation/request')
    def validation_request(user: User):
        pass

    # Endpoint: test plain Pydantic validation
    @app.get('/validation/user')
    def validation_user():
        User(login=None)

    # Handle exceptions
    register_application_exception_handlers(app)

    # Go
    with fastapi.testclient.TestClient(app) as c:
        main()
