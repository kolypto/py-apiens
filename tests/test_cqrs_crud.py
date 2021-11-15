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
from jessiql.util import sacompat
from jessiql.testing.graphql import resolves
from jessiql.integration.fastapi import query_object, QueryObject


from apiens.crud.crudbase import QueryApi, MutateApi, ReturningMutateApi
from apiens.crud.crudsettings import CrudSettings
from apiens.crud.crudparams import CrudParams


# TODO: parameterize `commands_return_fields`
def test_crud_api(engine: sa.engine.Engine, commands_return_fields: bool = False):
    def main():
        q = {'select': json.dumps(['id', 'login', 'name'])}

        # === Test: createUser
        input_user = {'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}
        if commands_return_fields:
            expected_result = {'user': {'id': 1, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}}
        else:
            expected_result = {'user': {'id': 1}}

        assert client.post('/user', json={'user': input_user}).json() == expected_result
        # expected_result['id'] += 1  # TODO: uncomment
        assert gq('mutation ($user: UserCreate!) { createUser(user: $user) }', user=input_user) == {'createUser': expected_result['user']['id']}

        # === Test: listUsers
        expected_results = [
            {'id': 1, 'login': 'kolypto', 'name': 'Mark'},
        ]

        assert client.get('/user', params={**q, 'role': 'admin'}).json() == {'users': expected_results, 'next': None, 'prev': None}
        assert gq('query { listUsers { users { id login name } next prev } }') == {'listUsers': {'users': expected_results, 'next': None, 'prev': None}}

        # === Test: getUser
        user_id = 1
        expected_result = {'id': user_id, 'login': 'kolypto', 'name': 'Mark'}

        assert client.get(f'/user/{user_id}', params=q).json() == {'user': expected_result}
        assert gq('query ($id: Int!) { getUser(id: $id) { id login name } }', id=user_id) == {'getUser': expected_result}

        # === Test: updateUserId
        user_id = 1
        input_user = {'id': user_id, 'login': 'kolypto', 'name': 'Mark'}
        if commands_return_fields:
            expected_result = {'user': {'id': user_id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}}
        else:
            expected_result = {'user': {'id': user_id}}

        assert client.post(f'/user/{user_id}', json={'user': input_user}).json() == expected_result
        assert gq('mutation ($id: Int!, $user: UserUpdate!) { updateUserId(id: $id, user: $user) }', id=user_id, user=input_user) == {'updateUserId': expected_result['user']['id']}

        # === Test: updateUser
        assert client.put(f'/user', json={'user': input_user}).json() == expected_result
        assert gq('mutation ($user: UserUpdate!) { updateUser(user: $user) }', user=input_user) == {'updateUser': expected_result['user']['id']}

        # === Test: deleteUser
        user_id = 1
        if commands_return_fields:
            expected_result = {'user': {'id': user_id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}}
        else:
            expected_result = {'user': {'id': user_id}}

        assert client.delete(f'/user/{user_id}').json() == expected_result
        assert gq('mutation ($id: Int!) { deleteUser(id: $id) }', id=user_id) == {'deleteUser': expected_result['user']['id']}

        # Count
        expected_count = 0
        assert client.get('/user/count').json() == {'count': expected_count}
        assert gq('query { countUsers }') == {'countUsers': expected_count}

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
        i_am_admin: bool
        id: Optional[int] = None
        role_filter: Optional[str] = None
        crudsettings = CrudSettings(Model=User, debug=True)

        def filter(self):
            return (
                # Only let users list admins when they themselves are admins
                True if self.i_am_admin else User.is_admin == False,
                # Role filter
                (User.is_admin == (self.role_filter == 'admin')) if self.role_filter else True,
            )

    # TODO: find a way to merge these three classes into one? or at least share the settings?
    class UserQueryApi(QueryApi):
        crudsettings = UserCrudParams.crudsettings

    class UserMutateApi(MutateApi):
        crudsettings = UserCrudParams.crudsettings

    class UserReturningMutateApi(ReturningMutateApi):
        crudsettings = UserCrudParams.crudsettings

    # API: FastAPI
    @app.get('/user', response_model=UserListResponse, response_model_exclude_unset=True)
    def list_users(ssn: sa.orm.Session = fastapi.Depends(ssn),
                   query_object: Optional[QueryObject] = fastapi.Depends(query_object),
                   role: str = fastapi.Query('user')):
        params = UserCrudParams(i_am_admin=True, role_filter=None)
        api = UserQueryApi(ssn, params, query_object)
        return {
            'users': api.list(),
            'next': None,
            'prev': None,
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
        params = UserCrudParams(i_am_admin=True, role_filter=None, id=id)
        api = UserQueryApi(ssn, params, query_object)
        return {'user': api.get()}

    UserMutateApiCls = UserReturningMutateApi if commands_return_fields else UserMutateApi

    @app.post('/user')
    def create_user(user: UserCreate = fastapi.Body(..., embed=True),
                    ssn: sa.orm.Session = fastapi.Depends(ssn),
                    query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        params = UserCrudParams(i_am_admin=True, role_filter=None)
        api = UserMutateApiCls(ssn, params)
        res = api.create(user.dict(exclude_unset=True))
        ssn.commit()
        return {'user': res} if commands_return_fields else {'user': res}

    @app.put('/user')
    def update_user(user: UserUpdate = fastapi.Body(..., embed=True),
                    ssn: sa.orm.Session = fastapi.Depends(ssn),
                    query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        params = UserCrudParams(i_am_admin=True, role_filter=None)
        api = UserMutateApiCls(ssn, params)
        res = api.update(user.dict(exclude_unset=True))
        ssn.commit()
        return {'user': res} if commands_return_fields else {'user': res}

    @app.post('/user/{id}')
    def update_user_id(id: int,
                       user: UserUpdate = fastapi.Body(..., embed=True),
                       ssn: sa.orm.Session = fastapi.Depends(ssn),
                       query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        params = UserCrudParams(i_am_admin=True, role_filter=None, id=id)
        api = UserMutateApiCls(ssn, params)
        res = api.update_id(user.dict(exclude_unset=True))
        ssn.commit()
        return {'user': res} if commands_return_fields else {'user': res}

    @app.delete('/user/{id}')
    def delete_user(id: int,
                    ssn: sa.orm.Session = fastapi.Depends(ssn),
                    query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        params = UserCrudParams(i_am_admin=True, role_filter=None, id=id)
        api = UserMutateApiCls(ssn, params)
        res = api.delete()
        ssn.commit()
        return {'user': res} if commands_return_fields else {'user': res}

    # API: GraphQL
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
    def resolve_update_user(root, info: graphql.GraphQLResolveInfo, user: dict):
        if commands_return_fields:
            return {'id': id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}
        else:
            return user['id']

    @resolves(gql_schema, 'Mutation', 'deleteUser')
    def resolve_delete_user(root, info: graphql.GraphQLResolveInfo, id: int):
        if commands_return_fields:
            return {'id': id, 'is_admin': True, 'login': 'kolypto', 'name': 'Mark'}
        else:
            return 1


    # Helpers
    def gq(query: str, **variable_values):
        """ Make a GraphqQL query """
        res = graphql.graphql_sync(gql_schema, query, variable_values=variable_values)
        if res.errors:
            raise ValueError(res.errors)
        return res.data

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


class UserDbPartial(UserDb):
    # all fields, optional, but not nullable
    # this is the return type for partially-selected models
    @pd.validator(*(name for name, field in UserDb.__fields__.items() if not field.allow_none))
    def validate_optional_yet_not_nullable(cls, v):
        if v is None:
            raise ValueError
        else:
            return v

    # TODO: these fields ideally should be derived from an existing model by making every field Optional
    id: Optional[int]
    is_admin: Optional[bool]
    login: Optional[str]
    name: Optional[str]


class UserCreate(UserBase):
    # rw, const fields
    is_admin: bool


class UserUpdate(UserBase):
    # rw fields, pk fields, make optional,
    id: Optional[int]
    login: Optional[str]
    name: Optional[str]


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

    # TODO: these fields ideally should be derived from an existing model by making every field Optional
    id: Optional[int]
    user_id: Optional[int]
    slug: Optional[str]
    text: Optional[str]



class ArticleCreate(ArticleBase):
    # rw, const fields
    user_id: int


class ArticleUpdate(ArticleBase):
    # rw fields, pk fields, make optional
    id: Optional[int]
    slug: Optional[str]
    text: Optional[str]


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
}

input UserUpdate {
    # rw fields; optional PK
    id: Int
    login: String!
    name: String!
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
