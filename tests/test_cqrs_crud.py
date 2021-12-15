from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import json
import graphql
import fastapi
import fastapi.testclient

import pydantic as pd
import sqlalchemy as sa
import sqlalchemy.orm

import jessiql
import jessiql.testing
from apiens.testing import Parameter, ObjectMatch
from apiens.tools.pydantic.derive import derive_model
from apiens.tools.sqlalchemy import db_transaction
from jessiql.integration.graphql import query_object_for
from jessiql.testing.graphql.query import graphql_query_sync
from jessiql.util import sacompat
from jessiql.testing.graphql import resolves
from jessiql.integration.fastapi import query_object, QueryObject


from apiens.crud import QueryApi, MutateApi, ReturningMutateApi
from apiens.crud import saves_custom_fields, MISSING
from apiens.crud import CrudSettings
from apiens.crud import CrudParams


# TODO: break this huge test apart into smaller tests, test more thoroughly

# TODO: parameterize `commands_return_fields`. Test with returning fields.
def test_crud_api(engine: sa.engine.Engine, commands_return_fields: bool = False):
    def main():
        q = {'select': json.dumps(['id', 'login', 'name'])}

        # === Test: createUser
        input_user = {'is_admin': True, 'login': 'kolypto', 'name': 'Mark-typo'}  # 'name': typo
        if commands_return_fields:
            expected_result = {'user': {'id': 1, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark-typo'}}
        else:
            expected_result = {'user': {'id': 1}}

        assert client.post('/user', json={'user': input_user}).json() == expected_result
        # expected_result['id'] += 1
        assert gq('mutation ($user: UserCreate!) { createUser(user: $user) }', user=input_user) == {'createUser': expected_result['user']['id']}

        with sa.orm.Session(bind=engine, future=True) as ssn:
            users = ssn.query(User).all()
            assert users == [
                ObjectMatch(id=1, is_admin=True, login='kolypto', name='Mark-typo'),
                # ObjectMatch(id=2, is_admin=True, login='kolypto', name='Mark-typo'),
            ]

        # === Test: updateUserId
        user_id = 1
        input_user = {'id': user_id, 'login': 'kolypto', 'name': 'Mark-fix-1'}
        if commands_return_fields:
            expected_result = {'user': {'id': user_id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark-fix-1'}}
        else:
            expected_result = {'user': {'id': user_id}}

        assert client.post(f'/user/{user_id}', json={'user': input_user}).json() == expected_result
        assert gq('mutation ($id: Int!, $user: UserUpdate!) { updateUserId(id: $id, user: $user) }', id=user_id, user=input_user) == {'updateUserId': expected_result['user']['id']}

        with sa.orm.Session(bind=engine, future=True) as ssn:
            users = ssn.query(User).all()
            assert users == [
                ObjectMatch(id=1, name='Mark-fix-1'),  # fixed
                # ObjectMatch(id=2, name='Mark-fix-1'),
            ]

        # === Test: updateUser, full update (all fields are provided)
        input_user['name'] = 'Mark-fix-2'
        assert client.put(f'/user', json={'user': input_user}).json() == expected_result
        assert gq('mutation ($user: UserUpdate!) { updateUser(user: $user) }', user=input_user) == {'updateUser': expected_result['user']['id']}

        with sa.orm.Session(bind=engine, future=True) as ssn:
            users = ssn.query(User).all()
            assert users == [
                ObjectMatch(id=1, name='Mark-fix-2'),  # fixed
                # ObjectMatch(id=2, name='Mark-fix-2'),
            ]

        # === Test: updateUser, partial updates
        # Check: does not fail on "skippable" fields: i.e. "login" not provided, API does not fail
        input_partial_user = {'id': user_id, 'name': 'Mark'}
        assert client.post(f'/user/{user_id}', json={'user': input_partial_user}).json() == expected_result
        assert gq('mutation ($id: Int!, $user: UserUpdate!) { updateUserId(id: $id, user: $user) }', id=user_id, user=input_partial_user) == {'updateUserId': expected_result['user']['id']}

        with sa.orm.Session(bind=engine, future=True) as ssn:
            users = ssn.query(User).all()
            assert users == [
                ObjectMatch(id=1, login='kolypto', name='Mark'),  # name: fixed, login: not modified
                # ObjectMatch(id=2, login='kolypto', name='Mark'),
            ]

        # === Test: listUsers
        # Check: our `q` does not select the "extra_field" field. It must not be visible, nor shoud it fail.
        expected_results = [
            {'id': 1, 'login': 'kolypto', 'name': 'Mark'},
        ]

        assert client.get('/user', params=q).json() == {'users': expected_results, 'next': None, 'prev': None}
        assert gq('query { listUsers { users { id login name } next prev } }') == {'listUsers': {'users': expected_results, 'next': None, 'prev': None}}

        # === Test: getUser
        user_id = 1
        expected_result = {'id': user_id, 'login': 'kolypto', 'name': 'Mark'}

        assert client.get(f'/user/{user_id}', params=q).json() == {'user': expected_result}
        assert gq('query ($id: Int!) { getUser(id: $id) { id login name } }', id=user_id) == {'getUser': expected_result}

        # === Test: deleteUser
        user_id = 1
        if commands_return_fields:
            expected_result = {'user': {'id': user_id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}}
        else:
            expected_result = {'user': {'id': user_id}}

        assert client.delete(f'/user/{user_id}').json() == expected_result
        assert gq('mutation ($id: Int!) { deleteUser(id: $id) }', id=user_id) == {'deleteUser': expected_result['user']['id']}

        # === Test: countUsers
        expected_count = 0
        assert client.get('/user/count').json() == {'count': expected_count}
        assert gq('query { countUsers }') == {'countUsers': expected_count}

        # === Test: list/get with customized filter
        # Create some users
        with sa.orm.Session(bind=engine, future=True) as ssn:
            for i in range(5):
                ssn.add(User(is_admin=True, login=f'admin{i+1}', name=f'admin{i+1}'))
            for i in range(5):
                ssn.add(User(is_admin=False, login=f'user{i+1}', name=f'user{i+1}'))
            ssn.commit()

        # List only admins
        q = {'select': json.dumps(['id', 'login']),
             'role': 'admin'}
        assert client.get('/user', params=q).json() == {
            'users': [
                {'id':  2, 'login': 'admin1'},
                {'id':  3, 'login': 'admin2'},
                {'id':  4, 'login': 'admin3'},
                {'id':  5, 'login': 'admin4'},
                {'id':  6, 'login': 'admin5'},
            ],
            'next': None,
            'prev': None
        }

        # List only users
        q = {'select': json.dumps(['id', 'login']),
             'role': 'user'}
        assert client.get('/user', params=q).json() == {
            'users': [
                {'id':  7, 'login': 'user1'},
                {'id':  8, 'login': 'user2'},
                {'id':  9, 'login': 'user3'},
                {'id': 10, 'login': 'user4'},
                {'id': 11, 'login': 'user5'},
            ],
            'next': None,
            'prev': None
        }

        # === Test: pagination
        # Load: first page
        q = {'select': json.dumps(['id', 'login']),
             'sort': json.dumps(['id+']),
             'limit': 2}
        assert client.get('/user', params=q).json() == {
            'users': [
                {'id': 2, 'login': 'admin1'},
                {'id': 3, 'login': 'admin2'},
            ],
            'next': (next_page := Parameter()),
            'prev': None,
        }
        assert next_page.value.startswith('keys:')  # keyset pagination

        # Load: next page
        q['skip'] = next_page.value

        assert client.get('/user', params=q).json() == {
            'users': [
                {'id': 4, 'login': 'admin3'},
                {'id': 5, 'login': 'admin4'},
            ],
            'next': (next_page := Parameter()),
            'prev': (prev_page := Parameter()),
        }
        assert next_page.value.startswith('keys:')  # keyset pagination
        assert prev_page.value.startswith('keys:')  # keyset pagination


        # === Test: @saves_custom_fields

        # === Test: create user with articles
        # Check: must not fail because `user_id` is not provided on the Article
        input_user = {'is_admin': True, 'login': 'kolypto', 'name': 'Mark', 'articles': [
            {
                'slug': 'cqrs-is-awesome',
                'text': 'CQRS is Awesome',
            },
        ]}
        if commands_return_fields:
            expected_result = {'user': {'id': 12, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}}
        else:
            expected_result = {'user': {'id': 12}}

        assert client.post('/user', json={'user': input_user}).json() == expected_result
        # expected_result['user']['id'] += 1
        expected_result['user']['id'] = 1
        assert gq('mutation ($user: UserCreate!) { createUser(user: $user) }', user=input_user) == {'createUser': expected_result['user']['id']}

        # === Test: modify user with articles
        user_id = 12
        input_user = {'id': user_id, 'new_articles': [
            {
                'slug': 'build-great-apis',
                'text': 'Build Great APIs',
            },
        ]}
        if commands_return_fields:
            expected_result = {'user': {'id': user_id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}}
        else:
            expected_result = {'user': {'id': user_id}}

        assert client.post(f'/user/{user_id}', json={'user': input_user}).json() == expected_result
        assert gq('mutation ($id: Int!, $user: UserUpdate!) { updateUserId(id: $id, user: $user) }', id=user_id, user=input_user) == {'updateUserId': expected_result['user']['id']}

        # Test that articles were actually saved
        with sa.orm.Session(bind=engine, future=True) as ssn:
            articles = ssn.query(Article).order_by(Article.id.asc()).all()
            assert articles == [
                ObjectMatch(user_id=user_id, slug='cqrs-is-awesome'),
                ObjectMatch(user_id=user_id, slug='build-great-apis'),
            ]


    # FastAPI dependencies
    def ssn() -> sa.orm.Session:
        """ Dependency: SqlAlchemy Session """
        ssn = sa.orm.Session(bind=engine, autoflush=True, future=True)

        try:
            yield ssn
        finally:
            ssn.close()

    # FastAPI app
    app = fastapi.FastAPI()
    client = fastapi.testclient.TestClient(app=app)

    # API models
    class UserListResponse(pd.BaseModel):
        users: list[UserDbPartial]
        prev: Optional[str]
        next: Optional[str]

    class UserGetResponse(pd.BaseModel):
        user: UserDbPartial

    class CountResponse(pd.BaseModel):
        count: int

    # CQRS
    @dataclass
    class UserCrudParams(CrudParams):
        """ Crud Params for many Users view """
        i_am_admin: bool
        role_filter: Optional[str] = None
        crudsettings = CrudSettings(Model=User, debug=True)

        def filter(self):
            return (
                # Only let users list admins when they themselves are admins
                {
                    True: True,
                    False: User.is_admin == False,
                }[self.i_am_admin],
                # Role filter
                {
                    'user': User.is_admin == False,
                    'admin': User.is_admin == True,
                    None: True,
                }[self.role_filter],
            )

    @dataclass
    class UserIdCrudParams(UserCrudParams):
        """ Crud Params for one User view """
        id: Optional[int] = None

    class UserQueryApi(QueryApi):
        pass

    class UserMutateApi(MutateApi):
        # Implement a method for saving articles
        @saves_custom_fields('articles', 'new_articles')
        def save_articles(self, /, new: User, prev: User = None, *, articles: list[dict] = MISSING, new_articles: list[dict] = MISSING):
            if new_articles is not MISSING:
                articles = new_articles  # same handling

            if articles is not MISSING:
                # Assume: creating a new user
                assert prev is None

                # Create articles: add
                new.articles.extend((  # associate with the User
                    Article(**article_dict)
                    for article_dict in articles
                ))


    class UserReturningMutateApi(ReturningMutateApi):
        pass


    # Choose class: mutation returns values or not?
    UserMutateApiCls = UserReturningMutateApi if commands_return_fields else UserMutateApi


    # API: FastAPI
    @app.get('/user', response_model=UserListResponse, response_model_exclude_unset=True)
    def list_users(ssn: sa.orm.Session = fastapi.Depends(ssn),
                   query_object: Optional[QueryObject] = fastapi.Depends(query_object),
                   role: Optional[str] = fastapi.Query(None)):
        # TODO: helpers to simplify crud endpoints?
        params = UserCrudParams(i_am_admin=True, role_filter=role)
        api = UserQueryApi(ssn, params, query_object)
        users = api.list()
        links = api.query.page_links()
        return {
            'users': users,
            'next': links.next,
            'prev': links.prev,
        }

    @app.get('/user/count', response_model=CountResponse, response_model_exclude_unset=True)
    def count_users(ssn: sa.orm.Session = fastapi.Depends(ssn),
                    query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        params = UserCrudParams(i_am_admin=True, role_filter=None)
        api = UserQueryApi(ssn, params, query_object)
        return {'count': api.count()}

    @app.get('/user/{id}', response_model=UserGetResponse, response_model_exclude_unset=True)
    def get_user(id: int, ssn: sa.orm.Session = fastapi.Depends(ssn),
                 query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        params = UserIdCrudParams(i_am_admin=True, role_filter=None, id=id)
        api = UserQueryApi(ssn, params, query_object)
        return {'user': api.get()}

    @app.post('/user')
    def create_user(user: UserCreate = fastapi.Body(..., embed=True),
                    ssn: sa.orm.Session = fastapi.Depends(ssn),
                    query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        params = UserCrudParams(i_am_admin=True, role_filter=None)
        api = UserMutateApiCls(ssn, params)
        with db_transaction(ssn):
            res = api.create(user.dict(exclude_unset=True))
        return {'user': res} if commands_return_fields else {'user': res}

    @app.put('/user')
    def update_user(user: UserUpdate = fastapi.Body(..., embed=True),
                    ssn: sa.orm.Session = fastapi.Depends(ssn),
                    query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        params = UserIdCrudParams(i_am_admin=True, role_filter=None)
        api = UserMutateApiCls(ssn, params)
        with db_transaction(ssn):
            res = api.update(user.dict(exclude_unset=True))
        return {'user': res} if commands_return_fields else {'user': res}

    @app.post('/user/{id}')
    def update_user_id(id: int,
                       user: UserUpdate = fastapi.Body(..., embed=True),
                       ssn: sa.orm.Session = fastapi.Depends(ssn),
                       query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        params = UserIdCrudParams(i_am_admin=True, role_filter=None, id=id)
        api = UserMutateApiCls(ssn, params)
        with db_transaction(ssn):
            res = api.update_id(user.dict(exclude_unset=True))
        return {'user': res} if commands_return_fields else {'user': res}

    @app.delete('/user/{id}')
    def delete_user(id: int,
                    ssn: sa.orm.Session = fastapi.Depends(ssn),
                    query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        params = UserIdCrudParams(i_am_admin=True, role_filter=None, id=id)
        api = UserMutateApiCls(ssn, params)
        with db_transaction(ssn):
            res = api.delete()
        return {'user': res} if commands_return_fields else {'user': res}

    # API: GraphQL
    # TODO: provide dependencies to GraphQL via the root object / singleton getters or something
    # TODO: implement GraphQL endpoints
    gql_schema = graphql.build_schema(schema_prepare())

    @resolves(gql_schema, 'Query', 'listUsers')
    def resolve_list_users(root, info: graphql.GraphQLResolveInfo):
        return {
            'users': [
                {'id': 1, 'login': 'kolypto', 'name': 'Mark'},
            ],
            'next': None,
            'prev': None,
        }

    @resolves(gql_schema, 'Query', 'getUser')
    def resolve_get_user(root, info: graphql.GraphQLResolveInfo, id: int):
        return {'id': id, 'login': 'kolypto', 'name': 'Mark'}

    @resolves(gql_schema, 'Query', 'countUsers')
    def resolve_count_users(root, info: graphql.GraphQLResolveInfo):
        return 0

    @resolves(gql_schema, 'Mutation', 'createUser')
    @resolves(gql_schema, 'Mutation', 'createUserF')
    def resolve_create_user(root, info: graphql.GraphQLResolveInfo, user: dict):
        if commands_return_fields:
            return {'id': id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}
        else:
            return 1

    @resolves(gql_schema, 'Mutation', 'updateUserId')
    def resolve_update_user(root, info: graphql.GraphQLResolveInfo, id: int, user: dict):
        if commands_return_fields:
            return {'id': id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}
        else:
            return id

    @resolves(gql_schema, 'Mutation', 'updateUser')
    @resolves(gql_schema, 'Mutation', 'updateUserF')
    def resolve_update_user(root, info: graphql.GraphQLResolveInfo, user: dict):
        if commands_return_fields:
            return {'id': id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}
        else:
            return user['id']

    @resolves(gql_schema, 'Mutation', 'deleteUser')
    @resolves(gql_schema, 'Mutation', 'deleteUserF')
    def resolve_delete_user(root, info: graphql.GraphQLResolveInfo, id: int):
        if commands_return_fields:
            return {'id': id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}
        else:
            return 1


    # Helpers
    def gq(query: str, **variable_values):
        """ Make a GraphqQL query """
        return graphql_query_sync(gql_schema, query, **variable_values)

    # Run
    with jessiql.testing.created_tables(engine, Base.metadata):
        main()


# region: Models
Base = sacompat.declarative_base()

class User(Base):
    __tablename__ = 'u'

    id = sa.Column(sa.Integer, primary_key=True)
    is_admin = sa.Column(sa.Boolean, nullable=False)
    login = sa.Column(sa.String)
    name = sa.Column(sa.String)

    articles = sa.orm.relationship(lambda: Article, back_populates='user')


class Article(Base):
    __tablename__ = 'a'

    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.ForeignKey('u.id'), nullable=False)
    slug = sa.Column(sa.String, nullable=False)
    text = sa.Column(sa.String)

    user = sa.orm.relationship(User, back_populates='articles')

# endregion


# region: Schema

class UserBase(pd.BaseModel):
    # rw fields
    login: str
    name: str


class UserDb(UserBase):
    # all fields: +ro and +const fields and +relations
    id: int
    is_admin: bool

    articles: list[ArticleDb]

    # A field that is available but is never used (to test field exclusion)
    extra_field: str


class UserDbPartial(UserDb):  # TODO: user derive_optional(UserDb). Also `ArticleDbPartial`
    # TODO: implement a helper for this validator. Also `ArticleDbPartial`
    # all fields, optional, but not nullable
    # this is the return type for partially-selected models
    @pd.validator(*(name for name, field in UserDb.__fields__.items()
                    if field.shape != pd.fields.SHAPE_SINGLETON or not field.allow_none))
    def validate_optional_yet_not_nullable(cls, v):
        if v is None:
            raise ValueError
        else:
            return v

    # TODO: these fields ideally should be derived from an existing model by making every field Optional. Also `ArticleDbPartial`
    id: Optional[int]
    is_admin: Optional[bool]
    login: Optional[str]
    name: Optional[str]
    articles: Optional[list[ArticleDb]]
    extra_field: Optional[str]


class UserCreate(UserBase):
    # rw, const fields
    is_admin: bool

    # NOTE: we do not use `ArticleCreate` because it requires a user_id
    articles: list[ArticleBase] = pd.Field(None)


class UserUpdate(UserBase):
    # rw fields, pk fields, make optional,
    id: Optional[int]
    login: Optional[str]
    name: Optional[str]

    new_articles: list[ArticleBase] = pd.Field(None)
    # articles: list[Union[ArticleUpdate, ArticleBase]] = pd.Field(None)


class ArticleBase(pd.BaseModel):
    # rw fields
    slug: str
    text: Optional[str]


class ArticleDb(ArticleBase):
    # all fields
    id: int
    user_id: int


class ArticleDbPartial(ArticleDb):
    # Fields are optional but not nullable
    @pd.validator(*(name for name, field in ArticleDb.__fields__.items() if not field.allow_none))
    def validate_optional_yet_not_nullable(cls, v):
        if v is None:
            raise ValueError
        else:
            return v

    id: Optional[int]
    user_id: Optional[int]
    slug: Optional[str]
    text: Optional[str]


class ArticleCreate(ArticleBase):
    # rw, const fields
    user_id: int


ArticleCreateForUser = derive_model(
    ArticleCreate,
    name='ArticleCreateForUser',
    exclude='user_id',
    BaseModel=ArticleCreate,
)


class ArticleUpdate(ArticleBase):
    # rw fields, pk fields, make optional
    id: Optional[int]
    slug: Optional[str]
    text: Optional[str]



UserCreate.update_forward_refs()
UserUpdate.update_forward_refs()
UserDbPartial.update_forward_refs()


# TODO: validate models against DB schema
# TODO: strict include/exclude mode ; auto-match mode (only overlaps). Implement: types, nullable required fields, nullable skippable fields
# schemas.settings = SchemaSettings(
#     models.User,
#     read=schemas.UserDb,
#     create=schemas.UserCreate,
#     update=schemas.UserUpdate,
# ).field_names(
#     ro_fields='id',
#     ro_relations=[],
#     const_fields=['is_admin'],
#     rw_fields=['login', 'name'],
#     rw_relations=[]
# )

# endregion

# region GraphQL

# language=graphql
GQL_SCHEMA = '''
type Query {
    getUser(id: Int!, query: QueryObjectInput): User!
    listUsers(query: QueryObjectInput): ListUsersResponse!
    countUsers(query: QueryObjectInput): Int!
}

type Mutation {
    # Mutations that return the id
    createUser(user: UserCreate!): Int!
    updateUser(user: UserUpdate!): Int!
    updateUserId(id: Int, user: UserUpdate!): Int!
    deleteUser(id: Int!): Int!
    
    # Mutations that return the object
    createUserF(user: UserCreate!): User!
    updateUserF(user: UserUpdate!): User!
    updateUserIdF(id: Int, user: UserUpdate!): User!
    deleteUserF(id: Int!): User!
}

type User {
    # all fields
    id: Int!
    is_admin: Boolean!
    login: String!
    name: String!
}

input UserCreate {
    # rw, const fields
    is_admin: Boolean!
    login: String!
    name: String!
    
    articles: [ArticleCreateForUser]
}

input UserUpdate {
    # rw fields; optional PK
    id: Int
    # TODO: how to implement non-nullable skippable fields? 
    #   a validator that's applied to a resolve function?
    #   a directive that's applied to an Input and makes everything optional? or should it just apply a validator?
    login: String
    name: String
    # login: String!
    # name: String!
    
    new_articles: [ArticleCreateForUser]
}

input ArticleCreateForUser {
    slug: String!
    text: String!
}

type ListUsersResponse {
    # The list of found users
    users: [User!]!
    
    # Cursor to the previous page, if any
    prev: String
    # Cursor to the next page, if any
    next: String
}
'''


def schema_prepare() -> str:
    """ Build a GraphQL schema for testing JessiQL queries """
    from jessiql.integration.graphql.schema import graphql_jessiql_schema
    return (
        GQL_SCHEMA +
        # Also load QueryObject and QueryObjectInput
        graphql_jessiql_schema
    )

# endregion
