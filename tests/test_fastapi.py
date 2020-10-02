from fastapi import FastAPI
from starlette.testclient import TestClient

from apiens import operation, doc, di
from apiens import errors_default as app_exc  # noqa: used in docstrings


def test_flat_operation():
    # Services

    @di.kwargs()
    class AuthenticationService:
        def current_user(self):
            return {'user': {'email': 'kolypto@gmail.com'}}

    # Operations

    @operation('index')
    @doc.string()
    @di.signature('auth')
    def index(a: int, auth: AuthenticationService, b: str = '1') -> dict:
        """ Index page

        With some longer description

        Params:
            a: first thing
            b: second thing
                with a longer description

        Raises:
            app_exc.E_AUTH_REQUIRED: Authentication failed

        Returns:
            sample description
        """
        return {'hello': 'moto', 'current_user': auth.current_user()}

    # Router

    from apiens.via.fastapi import OperationalApiRouter

    router = OperationalApiRouter(debug=True, fully_documented=True)
    router.injector.providers({
        AuthenticationService: AuthenticationService,
    })
    router.register_flat_operation(index)

    # Application
    app = FastAPI(debug=True)
    app.include_router(router)

    # Test the API
    with TestClient(app) as c:
        res = c.post('/index', json={'a': 1, 'b': '2'})
        assert res.json() == {
            'ret': {
                'hello': 'moto',
                'current_user': {'user': {'email': 'kolypto@gmail.com'}},
            }
        }

    # Test the OpenAPI
    openapi = app.openapi()
    index = openapi['paths']['/index']['post']  # method POST, path /index
    # operation id
    assert index["operationId"] == "index"
    # documentation
    assert index["summary"] == "Index page"
    assert index["description"] == "With some longer description"
    # Request
    assert index['requestBody']['content']['application/json']['schema']['$ref'] == '#/components/schemas/Body_index_index_post'
    assert openapi['components']['schemas']['Body_index_index_post'] == {
        "title": "Body_index_index_post",
        "required": ["a"],
        "type": "object",
        # Arguments are correct
        "properties": {
            "a": {
                # Documentation and type
                "title": "first thing",
                "type": "integer"
            },
            "b": {
                # Documentation and type
                "title": "second thing",
                "type": "string",
                "description": "with a longer description",
                "default": "1",  # the default value is here
            }
        }
    }
    # Response
    assert index['responses']['200']['description'] == 'sample description'

    # Errors
    assert index['responses']['401']['description'] == (
        '`E_AUTH_REQUIRED`. Authentication failed\n\n'
    )
    assert index['responses']['401']['content']['application/json']['schema']['$ref'] == '#/components/schemas/ErrorResponse'
