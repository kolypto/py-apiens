import pydantic as pd
from fastapi import FastAPI, Depends, Body
from starlette.testclient import TestClient

from apiens.tools.fastapi.class_based_view.class_based_view import class_based_view, Route, api_route


def test_class_based_view():
    # Schemas
    class User(pd.BaseModel):
        id: int
        login: str

    # Dependencies
    user_1 = User(id=1, login='kolypto')

    def current_user():
        return user_1

    # Prepare an application
    app = FastAPI(debug=True, docs_url=None, redoc_url=None, openapi_url=None)

    @class_based_view(
        app,
        # As Route() class
        Route('list', '/'),
        # As a tuple
        ('get', '/{id:int}'),  # NOTE: must specify the type in the URL
        # With a method
        ('create', '/', 'POST'),
    )
    class View:
        # Class-Based View __init__() has dependencies
        def __init__(self, current_user: User = Depends(current_user)):
            self.current_user = current_user

        # Method: returns a list of users
        def list(self):
            return {'users': list(db.values())}

        # Method: has a path argument
        def get(self, id: int):
            return {'user': db[id]}

        # Method: receives input object
        def create(self, user: User = Body(..., embed=True)):
            id = user.id
            db[id] = user
            return self.get(id=id)

        # Custom method
        @api_route.get('/whoami')
        def whoami(self):
            return {
                # Test that the dependency has worked
                'current_user': self.current_user,
            }

    db = {}  # mock database

    # See which routes have been created
    assert [
        (route.path,
         route.methods,
         route.path_regex.pattern,
         {param: convertor.__class__.__name__ for param, convertor in route.param_convertors.items()}
         )
        for route in app.routes
    ] == [
        ('/', {'GET'}, r'^/$', {}),
        ('/{id:int}', {'GET'}, r'^/(?P<id>[0-9]+)$', {'id': 'IntegerConvertor'}),
        ('/', {'POST'}, r'^/$', {}),
        ('/whoami', {'GET'}, r'^/whoami$', {}),
    ]

    # Test it with a client
    with TestClient(app) as c:
        # list()
        res = c.get('/')
        assert res.json() == {'users': []}

        # create()
        user_2_json = {'id': 2, 'login': 'ootync'}
        res = c.post('/', json={'user': user_2_json})
        assert res.json() == {'user': user_2_json}

        # list()
        res = c.get('/')
        assert res.json() == {'users': [user_2_json]}

        # get()
        res = c.get('/2')
        assert res.json() == {'user': user_2_json}

        # whoami()
        res = c.get('/whoami')
        assert res.json() == {'current_user': user_1.dict()}
