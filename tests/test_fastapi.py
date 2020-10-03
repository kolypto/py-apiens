from fastapi import FastAPI
from fastapi.params import Path
from starlette.testclient import TestClient

from apiens import errors_default as app_exc  # noqa: used in docstrings
from apiens import operation, di
from apiens.via.fastapi import fastapi_route


def test_flat_operation():
    # Services

    @di.signature()
    class AuthenticationService:
        def current_user(self):
            return {'user': {'email': 'kolypto@gmail.com'}}

    # Operations

    @operation()
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
    router.add_operations(index)

    # Application
    app = FastAPI(debug=True)
    app.include_router(router)

    # Test the API
    with TestClient(app) as c:
        res = c.post('/index', json={'a': 1, 'b': '2'})
        assert res.json() == {
            'hello': 'moto',
            'current_user': {'user': {'email': 'kolypto@gmail.com'}},
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


def test_class_endpoint():
    # Operations

    @operation('user')
    class UserOperations:
        """ Operations on the User object """

        @operation()
        @fastapi_route('GET', '/')
        def list(self) -> dict:
            """ Get a list of all users

            Returns:
                the list of users
            """
            return {'users': []}

        @operation()
        @fastapi_route('POST', '/')
        def create(self, user: dict) -> dict:
            """ Create a user

            Args:
                user: The user to create

            Returns:
                the created user
            """
            return {'user': user}

        @operation()
        @fastapi_route('GET', '/{id:int}', id=Path(...))
        def get(self, id: int) -> dict:
            """ Get a user

            Args:
                id: The user to get

            Returns:
                the user
            """
            return {'user': {'id': id}}

        @operation()
        @fastapi_route('PATCH', '/{id:int}', id=Path(...))
        def update(self, id: int, user: dict) -> dict:
            """ Update a user

            Args:
                id: The user to update
                user: Updated fields

            Returns:
                the updated user
            """
            return {'user': {'id': id, **user}}

        @operation()
        @fastapi_route('DELETE', '/{id:int}', id=Path(...))
        def delete(self, id: int) -> dict:
            """ Delete a user

            Args:
                id: The user to delete

            Returns:
                the user
            """
            return {'user': {'id': id}}


    # Router
    from apiens.via.fastapi import OperationalApiRouter

    router = OperationalApiRouter(debug=True, fully_documented=True)
    router.add_operations(UserOperations)

    # Application
    app = FastAPI(debug=True, redoc_url=None, docs_url=None, openapi_url=None)
    app.include_router(router)

    # Test the routes
    assert {
        (route.path, tuple(sorted(route.methods)))
        for route in app.routes
    } == {
        ('/user/', ('GET',)),  # list()
        ('/user/', ('POST',)),  # create()
        ('/user/{id:int}', ('GET',)),  # get()
        ('/user/{id:int}', ('PATCH',)),  # update()
        ('/user/{id:int}', ('DELETE',)),  # delete
    }

    # Test the API
    with TestClient(app) as c:
        # list()
        res = c.get('/user/')
        assert res.json() == {'users': []}

        # create()
        res = c.post('/user/', json={'user': {'name': 'K'}})
        assert res.json() == {'user': {'name': 'K'}}

        # get()
        res = c.get('/user/1')
        assert res.json() == {'user': {'id': 1}}

        # update()
        res = c.patch('/user/1', json={'id': 1, 'user': {'name': 'K'}})
        assert res.json() == {'user': {'id': 1, 'name': 'K'}}

        # delete()
        res = c.delete('/user/1', json={'id': 1})
        assert res.json() == {'user': {'id': 1}}

    # Test the OpenAPI
    openapi = app.openapi()

    assert set(openapi['paths']) == {
        '/user/',
        '/user/{id}',
    }
    assert set(openapi['paths']['/user/']) == {
        'get',
        'post',
    }
    assert set(openapi['paths']['/user/{id}']) == {
        'get',
        'delete',
        'patch',
    }

    assert openapi['paths']['/user/']['get']['operationId'] == 'user.list'
    assert openapi['paths']['/user/']['post']['operationId'] == 'user.create'
    assert openapi['paths']['/user/{id}']['get']['operationId'] == 'user.get'
    assert openapi['paths']['/user/{id}']['patch']['operationId'] == 'user.update'
    assert openapi['paths']['/user/{id}']['delete']['operationId'] == 'user.delete'

    assert openapi['paths']['/user/{id}']['get']['parameters'] == [
      {
        "required": True,
        "schema": {"title": "Id", "type": "integer"},
        "name": "id",
        "in": "path",  # the parameter has successfully gone into Path()
      }
    ]