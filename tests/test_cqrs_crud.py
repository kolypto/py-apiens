from __future__ import annotations

from collections import abc
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass
from typing import Optional

import graphql
import fastapi
import fastapi.testclient

import pydantic as pd
import pytest
import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.exc
from sqlalchemy.dialects import postgresql as pg

import jessiql
import jessiql.testing
from apiens.testing import Parameter, ObjectMatch
from apiens.tools.pydantic import partial
from apiens.tools.pydantic.derive import derive_model
from apiens.tools.sqlalchemy import db_transaction

from jessiql.query_object import query_object_param as qop
from jessiql.integration.graphql import query_object_for
from jessiql.testing import insert
from jessiql.testing.graphql.query import graphql_query_sync
from jessiql.util import sacompat
from jessiql.testing.graphql import resolves
from jessiql.integration.fastapi import query_object, QueryObject

import apiens
import apiens.exc
from apiens.crud import QueryApi, MutateApi, ReturningMutateApi
from apiens.crud import saves_custom_fields, MISSING
from apiens.crud import CrudSettings
from apiens.crud import CrudParams
from tests.conftest import DATABASE_URL


def test_crud_create():
    """ Test CRUD: mutation: create() """
    def main():
        # Test: MutateApi
        with Session() as ssn:
            api = MutateApi(ssn, UserCrudParams())
            # === Test: create
            # Create: one field
            res = api.create({'is_admin': False})
            assert res == {'id': 1}

            # Create: all fields
            res = api.create({'is_admin': False, 'login': 'john1', 'name': 'John'})
            assert res == {'id': 2}

            assert all_users(ssn) == [
                ObjectMatch(id=1, is_admin=False, login=None, name=None),
                ObjectMatch(id=2, is_admin=False, login='john1', name='John'),
            ]

        # Test: ReturningMutateApi
        with Session() as ssn:
            api = ReturningMutateApi(ssn, UserCrudParams(), {'select': ['id', 'login']})

            # === Test: create, returning
            res = api.create({'is_admin': False})
            assert res == {'id': 3, 'login': None}  # query object worked

        # Test: errors
        with Session() as ssn:
            api = MutateApi(ssn, UserCrudParams())

            # === Test: unknown column
            # TypeError: 'UNKNOWN' is an invalid keyword
            with pytest.raises(TypeError):
                api.create({'UNKNOWN': 'INVALID'})

            # === Test: non-null column violation
            # sqlalchemy.exc.IntegrityError: (psycopg2.errors.NotNullViolation) null value in column "is_admin" of relation "u" violates not-null constraint
            with pytest.raises(sa.exc.IntegrityError) as e:
                api.create({})
            #assert e.value.column_names == ['id_admin]
            ssn.rollback()  # reset a messed-up transaction

            # === Test: PK provided
            res = api.create({'id': 999, 'is_admin': False})
            assert res == {'id': 5}  # Cannot customize: the "id" is removed

            # === Test: unique violation
            class NaturalPkUser(CrudParams):
                crudsettings = CrudSettings(Model=User, natural_primary_key=True)

            api = MutateApi(ssn, NaturalPkUser())

            insert(ssn, User, dict(id=1, is_admin=False))
            # sqlalchemy.exc.IntegrityError: (psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint "u_pkey"
            with pytest.raises(apiens.exc.ValueConflict) as e:
                api.create({'id': 1, 'is_admin': False})
            assert e.value.column_names == []  # NOTE: cannot find the key because it does not have an explicit name in the table
            ssn.rollback()


    # CRUD params
    @dataclass
    class UserCrudParams(CrudParams):
        crudsettings = CrudSettings(Model=User, debug=True)
        id: Optional[int] = None

    # Run
    with db_create():
        main()


def test_crud_create_api():
    """ Test CRUD API: mutation: create """
    def main():
        # === Test: create
        input_user = {'is_admin': True, 'login': 'john1', 'name': 'John'}

        expected_result = {'user': {'id': 1}}
        assert client.post('/user', json={'user': input_user}).json() == expected_result

        expected_result = {'createUser': 2}
        assert gql_schema.q('mutation ($user: UserCreate!) { createUser(user: $user) }', user=input_user) == expected_result

        assert all_users() == [
            ObjectMatch(id=1, is_admin=True, login='john1', name='John'),
            ObjectMatch(id=2, is_admin=True, login='john1', name='John'),
        ]
        db_cleanup()

        # === Test: create, returning
        q = qop({'select': ['id', 'login', 'name']})
        input_user = {'is_admin': True, 'login': 'john2', 'name': 'John'}

        expected_result = {'user': {'id': 1, 'login': 'john2', 'name': 'John'}}
        assert client.post('/userF', params=q, json={'user': input_user}).json() == expected_result

        expected_result = {'createUserF': {'id': 2, 'login': 'john2', 'name': 'John'}}
        assert gql_schema.q('mutation ($user: UserCreate!) { createUserF(user: $user) { id login name } }', user=input_user) == expected_result

        assert all_users() == [
            ObjectMatch(id=1, is_admin=True, login='john2', name='John'),
            ObjectMatch(id=2, is_admin=True, login='john2', name='John'),
        ]


    # CRUD params
    @dataclass
    class UserCrudParams(CrudParams):
        crudsettings = CrudSettings(Model=User, debug=True)

    @dataclass
    class UserIdCrudParams(UserCrudParams):
        id: Optional[int] = None

    # CRUD
    class UserQueryApi(QueryApi):
        pass

    class UserMutateApi(MutateApi):
        pass

    class UserReturningMutateApi(ReturningMutateApi):
        pass

    # Response models
    class UserGetResponse(pd.BaseModel):
        user: UserDbPartial

    # FastAPI
    app = fastapi.FastAPI()
    client = fastapi.testclient.TestClient(app=app)

    @app.post('/user', response_model=UserGetResponse, response_model_exclude_unset=True)
    def create_user(user: UserCreate = fastapi.Body(..., embed=True),
                    ssn: sa.orm.Session = fastapi.Depends(dep.db_ssn)):
        """ Create user CRUD, returning PK """
        params = UserCrudParams()
        api = UserMutateApi(ssn, params)
        with db_transaction(ssn):
            res = api.create(user.dict(exclude_unset=True))
        return {'user': res}

    @app.post('/userF', response_model=UserGetResponse, response_model_exclude_unset=True)
    def create_userF(user: UserCreate = fastapi.Body(..., embed=True),
                     ssn: sa.orm.Session = fastapi.Depends(dep.db_ssn),
                     query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        """ Create user CRUD, returning full object with JessiQL support """
        params = UserIdCrudParams()
        api = UserReturningMutateApi(ssn, params, query_object=query_object)
        with db_transaction(ssn):
            res = api.create(user.dict(exclude_unset=True))
        return {'user': res}

    # GraphQL
    gql_schema = schema_prepare()

    @resolves(gql_schema, 'Mutation', 'createUser')
    def resolve_create_user(root, info: graphql.GraphQLResolveInfo, user: dict):
        """ Create user CRUD, returning PK """
        with Session() as ssn:
            return create_user(UserCreate.parse_obj(user), ssn)['user']['id']

    @resolves(gql_schema, 'Mutation', 'createUserF')
    def resolve_create_userF(root, info: graphql.GraphQLResolveInfo, user: dict):
        """ Create user CRUD, returning full object with JessiQL support """
        query_object = query_object_for(info, has_query_argument=False)
        with Session() as ssn:
            return create_userF(UserCreate.parse_obj(user), ssn, query_object)['user']

    # Run
    with db_create():
        main()


def test_crud_update():
    """ Test CRUD: mutation: create() """
    def main():
        # Test: update(), update_id()
        with Session() as ssn:
            # Create a user
            insert(ssn, User, dict(id=1, is_admin=False))

            # === Test: update_id
            api = MutateApi(ssn, UserIdCrudParams(id=1))

            res = api.update_id({'login': 'john1'})  # change login
            assert res == {'id': 1}
            assert all_users(ssn) == [
                ObjectMatch(id=1, login='john1'),
            ]

            # === Test: update
            res = api.update({'id': 1, 'login': 'john2'})  # change login
            assert res == {'id': 1}
            assert all_users(ssn) == [
                ObjectMatch(id=1, login='john2')
            ]

            # === Test: attempt update PK
            api.params.id = 1
            res = api.update_id({'id': 999})
            assert res == {'id': 1}

            assert all_users(ssn) == [
                ObjectMatch(id=1, login='john2'),
            ]

            # === Test: update 404
            # sqlalchemy.exc.NoResultFound: No row was found when one was required
            with pytest.raises(apiens.exc.NoResultFound):
                api.update({'id': 777})
            ssn.rollback()

            db_cleanup(ssn)

        # Test: update, returning
        with Session() as ssn:
            # Create a user
            insert(ssn, User, dict(id=1, is_admin=False))

            # === Test: update
            q = {'select': ['id', 'name', 'login']}
            api = ReturningMutateApi(ssn, UserIdCrudParams(id=1), q)
            input_user = {'login': 'john', 'name': 'John'}
            res = api.update_id(input_user)
            assert res == {'id': 1, 'login': 'john', 'name': 'John'}

        # Test: create_or_update()
        with Session() as ssn:
            api = MutateApi(ssn, UserIdCrudParams())

            # === Test: create-or-update
            res = api.create_or_update({'login': 'john1', 'is_admin': False})
            assert res == {'id': 1}

            res = api.create_or_update({'id': 1, 'login': 'john2'})  # update login
            assert res == {'id': 1}

            assert all_users(ssn) == [
                ObjectMatch(id=1, login='john2'),  # login updated
            ]

        # Test: update, filter
        with Session() as ssn:
            api = MutateApi(ssn, UserIdCrudParams())

            # Create an inaccessible user
            insert(ssn, User, dict(id=1, is_admin=True, login='john'))

            # Try to modify it
            api = MutateApi(ssn, UserIdCrudParams())  # non-admin
            with pytest.raises(apiens.exc.NoResultFound):
                api.update({'id': 1, 'login': 'jack'})

            # Become an admin and modify it
            api = MutateApi(ssn, UserIdCrudParams(i_am_admin=True))
            res = api.update({'id': 1, 'login': 'jack'})
            assert res == {'id': 1}

    # CRUD params
    @dataclass
    class UserIdCrudParams(CrudParams):
        crudsettings = CrudSettings(Model=User, debug=True)
        id: Optional[int] = None

        i_am_admin: bool = False

        def filter(self) -> abc.Iterable[sa.sql.elements.BinaryExpression]:
            # Only admins can modify admins
            if self.i_am_admin:
                return ()
            else:
                return (User.is_admin == False,)

    # Run
    with db_create():
        main()


def test_crud_update_api():
    """ Test CRUD API: mutation: create """
    def main():
        with Session() as ssn:
            insert(ssn, User, dict(id=1, is_admin=False))
            ssn.commit()

        # === Test: update
        input_user = {'id': 1, 'login': 'john1'}

        expected_result = {'user': {'id': 1}}
        assert client.post('/user', json={'user': input_user}).json() == expected_result

        expected_result = {'updateUser': 1}
        assert gql_schema.q('mutation ($user: UserUpdate!) { updateUser(user: $user) }', user=input_user) == expected_result

        assert all_users() == [
            ObjectMatch(id=1, login='john1')
        ]

        # === Test: update by id
        input_user = {'login': 'john2'}

        expected_result = {'user': {'id': 1}}
        assert client.post('/user/1', json={'user': input_user}).json() == expected_result

        expected_result = {'updateUserId': 1}
        assert gql_schema.q('mutation ($id: Int!, $user: UserUpdate!) { updateUserId(id: $id, user: $user) }', id=1, user=input_user) == expected_result

        assert all_users() == [
            ObjectMatch(id=1, login='john2')
        ]

        # === Test: update, returning
        q = qop({'select': ['id', 'login', 'name']})
        input_user = {'id': 1, 'login': 'john3', 'name': 'John'}

        expected_result = {'user': {'id': 1, 'login': 'john3', 'name': 'John'}}
        assert client.post('/userF', params=q, json={'user': input_user}).json() == expected_result

        expected_result = {'updateUserF': expected_result['user']}
        assert gql_schema.q('mutation ($user: UserUpdate!) { updateUserF(user: $user) { id name login } }', user=input_user) == expected_result

        assert all_users() == [
            ObjectMatch(id=1, login='john3')
        ]

        # === Test: update by id, returning
        input_user = {'login': 'john4'}

        expected_result = {'user': {'id': 1, 'login': 'john4', 'name': 'John'}}
        assert client.post('/userF/1', params=q, json={'user': input_user}).json() == expected_result

        expected_result = {'updateUserIdF': expected_result['user']}
        assert gql_schema.q('mutation ($id: Int!, $user: UserUpdate!) { updateUserIdF(id: $id, user: $user) { id name login } }', id=1, user=input_user) == expected_result

        assert all_users() == [
            ObjectMatch(id=1, login='john4')
        ]

    # CRUD params
    @dataclass
    class UserCrudParams(CrudParams):
        crudsettings = CrudSettings(Model=User, debug=True)

    @dataclass
    class UserIdCrudParams(UserCrudParams):
        id: Optional[int] = None

    # CRUD
    class UserQueryApi(QueryApi):
        pass

    class UserMutateApi(MutateApi):
        pass

    class UserReturningMutateApi(ReturningMutateApi):
        pass

    # Response models
    class UserUpdateResponse(pd.BaseModel):
        user: UserDbPartial

    # FastAPI
    app = fastapi.FastAPI()
    client = fastapi.testclient.TestClient(app=app)

    @app.post('/user', response_model=UserUpdateResponse, response_model_exclude_unset=True)
    def update_user(user: UserUpdate = fastapi.Body(..., embed=True),
                    ssn: sa.orm.Session = fastapi.Depends(dep.db_ssn)):
        """ Update user CRUD, id embedded into the object, returning PK """
        params = UserIdCrudParams()
        api = UserMutateApi(ssn, params)
        with db_transaction(ssn):
            res = api.update(user.dict(exclude_unset=True))
        return {'user': res}

    @app.post('/user/{id}', response_model=UserUpdateResponse, response_model_exclude_unset=True)
    def update_user_id(id: int,
                       user: UserUpdate = fastapi.Body(..., embed=True),
                       ssn: sa.orm.Session = fastapi.Depends(dep.db_ssn)):
        """ Update user CRUD, id provided separately, returning PK """
        params = UserIdCrudParams(id=id)
        api = UserMutateApi(ssn, params)
        with db_transaction(ssn):
            res = api.update_id(user.dict(exclude_unset=True))
        return {'user': res}

    @app.post('/userF', response_model=UserUpdateResponse, response_model_exclude_unset=True)
    def update_userF(user: UserUpdate = fastapi.Body(..., embed=True),
                     ssn: sa.orm.Session = fastapi.Depends(dep.db_ssn),
                     query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        """ Update user CRUD, id embedded into the object, returning PK """
        params = UserIdCrudParams()
        api = UserReturningMutateApi(ssn, params, query_object)
        with db_transaction(ssn):
            res = api.update(user.dict(exclude_unset=True))
        return {'user': res}

    @app.post('/userF/{id}', response_model=UserUpdateResponse, response_model_exclude_unset=True)
    def update_userF_id(id: int,
                        user: UserUpdate = fastapi.Body(..., embed=True),
                        ssn: sa.orm.Session = fastapi.Depends(dep.db_ssn),
                        query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        """ Update user CRUD, id provided separately, returning PK """
        params = UserIdCrudParams(id=id)
        api = UserReturningMutateApi(ssn, params, query_object)
        with db_transaction(ssn):
            res = api.update_id(user.dict(exclude_unset=True))
        return {'user': res}

    # GraphQL
    gql_schema = schema_prepare()

    @resolves(gql_schema, 'Mutation', 'updateUser')
    def resolve_update_user(root, info: graphql.GraphQLResolveInfo, user: dict):
        with Session() as ssn:
            return update_user(UserUpdate.parse_obj(user), ssn)['user']['id']

    @resolves(gql_schema, 'Mutation', 'updateUserId')
    def resolve_update_user_id(root, info: graphql.GraphQLResolveInfo, id: int, user: dict):
        with Session() as ssn:
            return update_user_id(id, UserUpdate.parse_obj(user), ssn)['user']['id']

    @resolves(gql_schema, 'Mutation', 'updateUserF')
    def resolve_update_userF(root, info: graphql.GraphQLResolveInfo, user: dict):
        query_object = query_object_for(info, has_query_argument=False)
        with Session() as ssn:
            return update_userF(UserUpdate.parse_obj(user), ssn, query_object)['user']

    @resolves(gql_schema, 'Mutation', 'updateUserIdF')
    def resolve_update_userF_id(root, info: graphql.GraphQLResolveInfo, id: int, user: dict):
        query_object = query_object_for(info, has_query_argument=False)
        with Session() as ssn:
            return update_userF_id(id, UserUpdate.parse_obj(user), ssn, query_object)['user']

    # Run
    with db_create():
        main()


def test_crud_create_or_update():
    def main():
        # === Test: create_or_update()
        with Session() as ssn:
            api = MutateApi(ssn, UserCrudParams())

            # Create
            res = api.create_or_update({'login': 'john', 'is_admin': False})
            assert res == {'id': 1}

            # Update
            res = api.create_or_update({'id': 1, 'login': 'jack'})
            assert res == {'id': 1}

            # Check?
            user = ssn.query(User).one()
            assert user.login == 'jack'  # updated

        # === Test: create_or_update(), with natural_primary_key
        with Session() as ssn:
            api = MutateApi(ssn, UserNaturalPkCrudParams())

            # Create
            res = api.create_or_update({'id': 999, 'login': 'john', 'is_admin': False})
            assert res == {'id': 999}

            # Update
            res = api.create_or_update({'id': 999, 'login': 'jack'})
            assert res == {'id': 999}

            # Check
            user = ssn.query(User).one()
            assert user.login == 'jack'

    # CRUD params
    @dataclass
    class UserCrudParams(CrudParams):
        crudsettings = CrudSettings(Model=User, debug=True)
        id: Optional[int] = None

    @dataclass
    class UserNaturalPkCrudParams(CrudParams):
        crudsettings = CrudSettings(Model=User, debug=True, natural_primary_key=True)
        id: Optional[int] = None

    # Run
    with db_create():
        main()


def test_crud_delete():
    """ Test CRUD: mutation: delete() """
    def main():
        with Session() as ssn:
            insert(ssn, User,
                   dict(id=1, is_admin=False),
                   dict(id=2, is_admin=False),
                   )

            # === Test: delete
            api = MutateApi(ssn, UserIdCrudParams(id=1))
            res = api.delete_id()
            assert res == {'id': 1}

            # === Test: delete returning
            q = {'select': ['id', 'name', 'login']}
            api = ReturningMutateApi(ssn, UserIdCrudParams(id=2), q)
            res = api.delete_id()
            assert res == {'id': 2, 'login': None, 'name': None}

            # Really removed
            assert all_users(ssn) == []

    # CRUD params
    @dataclass
    class UserIdCrudParams(CrudParams):
        crudsettings = CrudSettings(Model=User, debug=True)
        id: Optional[int] = None

    # Run
    with db_create():
        main()


def test_crud_delete_api():
    """ Test CRUD API: mutation: delete """
    def main():
        with Session() as ssn:
            insert(ssn, User,
                   dict(id=1, is_admin=False, login=None, name=None),
                   dict(id=2, is_admin=False, login=None, name=None),
                   dict(id=3, is_admin=False, login='john3', name='John'),
                   dict(id=4, is_admin=False, login='john4', name='John'),
                   )
            ssn.commit()

        # === Test: delete
        expected_result = {'user': {'id': 1}}
        assert client.delete('/user/1').json() == expected_result

        expected_result = {'deleteUser': 2}
        assert gql_schema.q('mutation ($id: Int!) { deleteUser(id: $id) }', id=2) == expected_result

        # === Test: delete, returning
        q = qop({'select': ['id', 'login', 'name']})
        expected_result = {'user': {'id': 3, 'login': 'john3', 'name': 'John'}}
        assert client.delete('/userF/3', params=q).json() == expected_result

        expected_result = {'deleteUserF': {'id': 4, 'login': 'john4', 'name': 'John'}}
        assert gql_schema.q('mutation ($id: Int!) { deleteUserF(id: $id) { id login name } }', id=4) == expected_result

        # Actually deleted
        assert all_users() == []
        db_cleanup()

    # CRUD params
    @dataclass
    class UserIdCrudParams(CrudParams):
        crudsettings = CrudSettings(Model=User, debug=True)
        id: Optional[int] = None

    # Response models
    class UserDeleteResponse(pd.BaseModel):
        user: UserDbPartial

    # FastAPI
    app = fastapi.FastAPI()
    client = fastapi.testclient.TestClient(app=app)

    @app.delete('/user/{id}', response_model=UserDeleteResponse, response_model_exclude_unset=True)
    def delete_user(id: int,
                    ssn: sa.orm.Session = fastapi.Depends(dep.db_ssn),
                    ):
        params = UserIdCrudParams(id=id)
        api = MutateApi(ssn, params)
        with db_transaction(ssn):
            res = api.delete_id()
        return {'user': res}

    @app.delete('/userF/{id}', response_model=UserDeleteResponse, response_model_exclude_unset=True)
    def delete_userF(id: int,
                     ssn: sa.orm.Session = fastapi.Depends(dep.db_ssn),
                     query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        params = UserIdCrudParams(id=id)
        api = ReturningMutateApi(ssn, params, query_object)
        with db_transaction(ssn):
            res = api.delete_id()
        return {'user': res}

    # GraphQL
    gql_schema = schema_prepare()

    @resolves(gql_schema, 'Mutation', 'deleteUser')
    def resolve_delete_user(root, info: graphql.GraphQLResolveInfo, id: int):
        with Session() as ssn:
            return delete_user(id, ssn)['user']['id']

    @resolves(gql_schema, 'Mutation', 'deleteUserF')
    def resolve_delete_userF(root, info: graphql.GraphQLResolveInfo, id: int):
        query_object = query_object_for(info, has_query_argument=False)
        with Session() as ssn:
            return delete_userF(id, ssn, query_object)['user']

    # Run
    with db_create():
        main()


# STUB
# def test_crud_delete():
#     """ Test CRUD: mutation: delete() """
#     def main():
#         with Session() as ssn:
#             api = MutateApi(ssn, UserIdCrudParams)
#
#             # === Test: update
#
#     # CRUD params
#     @dataclass
#     class UserIdCrudParams(CrudParams):
#         crudsettings = CrudSettings(Model=User, debug=True)
#         id: Optional[int] = None
#
#     # Run
#     with db_create():
#         main()
#
#
# def test_crud_delete_api():
#     """ Test CRUD API: mutation: delete """
#     def main():
#         # === Test: update
#         input_user = {}
#
#         expected_result = {}
#         # assert client.post('/user', json={'user': input_user}).json() == expected_result
#
#         expected_result = {}
#         # assert gql_schema.q('', user=input_user) == expected_result
#
#         assert all_users() == []
#         db_cleanup()
#
#     # CRUD params
#     @dataclass
#     class UserIdCrudParams(CrudParams):
#         crudsettings = CrudSettings(Model=User, debug=True)
#         id: Optional[int] = None
#
#     # Response models
#     class UserUpdateResponse(pd.BaseModel):
#         user: UserDbPartial
#
#     # FastAPI
#     app = fastapi.FastAPI()
#     client = fastapi.testclient.TestClient(app=app)
#
#     # GraphQL
#     gql_schema = schema_prepare()
#
#     # Run
#     with db_create():
#         main()


def test_mutation_saves_custom_fields():
    """ Test CRUD: @saves_relations with create() and update() """
    def main():
        # Define a class
        class UserMutateApi(MutateApi):
            # Implement a method for saving articles
            @saves_custom_fields('articles', 'new_articles')
            def save_articles(self, /, new: User, prev: User = None, *, articles: list[dict] = MISSING, new_articles: list[dict] = MISSING):
                if new_articles is not MISSING:
                    # Always add articles, do not replace.
                    # This is to simplify the implementation for the sake of tests
                    articles = new_articles

                if articles is not MISSING:
                    # Assume: not deleting
                    assert new is not None

                    # Create articles: add
                    new.articles.extend((  # associate with the User
                        Article(**article_dict)
                        for article_dict in articles
                    ))

        with Session() as ssn:
            # === Test: create a user with articles
            input_user = {
                'id': 1, 'is_admin': False, 'login': 'john',
                'articles': [
                    {'slug': 'article-1', 'text': 'First article'},
                ]
            }
            expected_result = {'id': 1}
            api = UserMutateApi(ssn, UserCrudParams())
            assert api.create(input_user) == expected_result
            ssn.flush()

            # Check created
            user = ssn.query(User).get(1)
            assert user == ObjectMatch(id=1, login='john')
            assert user.articles == [
                ObjectMatch(user_id=1, slug='article-1'),  # Article created, user assigned
            ]

            # === Test: update a user with articles
            input_user = {
                'id': 1,
                'new_articles': [
                    {'slug': 'article-2', 'text': 'Second article'},
                ]
            }
            api = UserMutateApi(ssn, UserIdCrudParams(id=None))
            assert api.update(input_user) == expected_result
            ssn.flush()
            ssn.refresh(user)

            assert sorted(user.articles, key=lambda a: a.id) == [
                ObjectMatch(user_id=1, slug='article-1'),
                ObjectMatch(user_id=1, slug='article-2'),  # added another one
            ]

    # CRUD params
    @dataclass
    class UserCrudParams(CrudParams):
        crudsettings = CrudSettings(Model=User, debug=True)

    @dataclass
    class UserIdCrudParams(UserCrudParams):
        id: Optional[int] = None

    # Run
    with db_create():
        main()


def test_crud_query():
    """ Test CRUD: query: list() get() count() """
    def main():
        # === Test: basic query
        with Session() as ssn:
            # Create some users
            insert(ssn, User,
                   dict(id=1, is_admin=False, login='one'),
                   dict(id=2, is_admin=False, login='two'),
                   )

            # === Test: list, get
            q = dict(select=['id', 'login'])
            api = QueryApi(ssn, UserCrudParams(), query_object=q)

            assert api.list() == [
                {'id': 1, 'login': 'one'},
                {'id': 2, 'login': 'two'},
            ]

            # === Test: get()
            api = QueryApi(ssn, UserIdCrudParams(id=1), query_object=q)
            assert api.get() == {'id': 1, 'login': 'one'}

            # === Test: get() 404
            api = QueryApi(ssn, UserIdCrudParams(id=999), query_object=q)
            assert api.get() is None

            # === Test: count()
            assert api.count() == 2

        # === Test: filtering
        with Session() as ssn:
            insert(ssn, User,
                   dict(id=1, is_admin=True, login='root'),
                   dict(id=2, is_admin=True, login='admin'),
                   dict(id=3, is_admin=False, login='john'),
                   dict(id=4, is_admin=False, login='jack'),
                   )

            # === Test: list() with filter
            api_admin = QueryApi(ssn, SecureUserParams(show_admins=True),  {'sort': ['id+']})
            api_user = QueryApi(ssn,  SecureUserParams(show_admins=False), {'sort': ['id+']})

            assert api_admin.list() == [{'id': 1}, {'id': 2}, {'id': 3}, {'id': 4}]
            assert api_user.list() == [{'id': 3}, {'id': 4}]

            # === Test: count() with filter
            assert api_admin.count() == 4
            assert api_user.count() == 2

            # === Test: update() also gets filtering
            api = MutateApi(ssn, SecureUserIdParams(show_admins=False, id=None))

            # Non-admin user: found ok
            expected_result = {'id': 3}  # ok
            assert api.update({'id': 3, 'login': 'new-john'}) == expected_result

            # Admin user: excluded, not found
            with pytest.raises(apiens.exc.NoResultFound):
                api.update({'id': 1})

        # === Test: pagination
        with Session() as ssn:
            insert(ssn, User, *[
                dict(is_admin=False)
                for i in range(5)
            ])

            # === Test: list() pagination
            # First page
            api = QueryApi(ssn, UserCrudParams(), {'select': ['id'], 'limit': 2, 'sort': ['id+']})

            expected_result = [{'id': 1}, {'id': 2}]
            assert api.list() == expected_result

            links = api.query.page_links()
            assert links.prev is None
            assert links.next.startswith('keys:')  # "keyset" cursor!

            # Second page
            api = QueryApi(ssn, UserCrudParams(), {'select': ['id'], 'skip': links.next, 'limit': 2, 'sort': ['id+']})

            expected_result = [{'id': 3}, {'id': 4}]
            assert api.list() == expected_result
            links = api.query.page_links()
            assert links.next.startswith('keys:')  # "keyset" cursor!

            # Third page
            api = QueryApi(ssn, UserCrudParams(), {'select': ['id'], 'skip': links.next, 'limit': 2, 'sort': ['id+']})

            expected_result = [{'id': 5}]
            assert api.list() == expected_result



    # CRUD params
    @dataclass
    class UserCrudParams(CrudParams):
        crudsettings = CrudSettings(Model=User, debug=True)

    @dataclass
    class UserIdCrudParams(UserCrudParams):
        id: Optional[int] = None

    # Filtering CRUD params
    @dataclass
    class SecureUserParams(UserCrudParams):
        show_admins: bool

        def filter(self) -> abc.Iterable[sa.sql.elements.BinaryExpression]:
            return (
                True if self.show_admins else User.is_admin == False,
                *super().filter(),
            )

    @dataclass
    class SecureUserIdParams(SecureUserParams):
        id: int

    # Run
    with db_create():
        main()


def test_crud_query_api():
    """ Test CRUD: query: list() get() count() """
    def main():
        with Session() as ssn:
            insert(ssn, User,
                   dict(id=1, is_admin=False),
                   dict(id=2, is_admin=False),
                   dict(id=3, is_admin=False),
                   )
            ssn.commit()

        # === Test: list
        q = qop({'select': ['id'], 'sort': ['id+']})
        expected_result = {
            'users': [{'id': 1}, {'id': 2}, {'id': 3}],
            'next': None,
            'prev': None,
        }
        assert client.get('/user/', params=q).json() == expected_result

        expected_result = {
            'listUsers': {
                'users': [{'id': 1}, {'id': 2}, {'id': 3}],
                'next': None,
                'prev': None,
            }
        }
        assert gql_schema.q('query { listUsers { users { id } next prev } }') == expected_result

        # === Test: count
        expected_result = {'count': 3}
        assert client.get('/user/count').json() == expected_result

        # === Test: get
        expected_result = {'user': {'id': 1}}
        assert client.get('/user/1').json() == expected_result

        # === Test: list, pagination
        # First page
        q = qop({'select': ['id'], 'sort': ['id+'], 'limit': 2})
        expected_result = {
            'users': [{'id': 1}, {'id': 2}],
            'prev': None,
            'next': (next := Parameter())
        }
        assert client.get('/user/', params=q).json() == expected_result
        assert next.value.startswith('keys:')  # keyset pagination!

        # Next page
        q = qop({'select': ['id'], 'sort': ['id+'], 'limit': 2, 'skip': next.value})
        expected_result = {
            'users': [{'id': 3}],
            'prev': Parameter(),
            'next': (next := Parameter())
        }
        assert client.get('/user/', params=q).json() == expected_result


    # CRUD params
    @dataclass
    class UserCrudParams(CrudParams):
        crudsettings = CrudSettings(Model=User, debug=True)

    @dataclass
    class UserIdCrudParams(UserCrudParams):
        id: Optional[int] = None

    # Response Models
    class UserListResponse(pd.BaseModel):
        users: list[UserDbPartial]

    class UserPageListResponse(pd.BaseModel):
        users: list[UserDbPartial]
        prev: Optional[str]
        next: Optional[str]

    class UserGetResponse(pd.BaseModel):
        user: UserDbPartial

    class CountResponse(pd.BaseModel):
        count: int

    # FastAPI
    app = fastapi.FastAPI()
    client = fastapi.testclient.TestClient(app=app)

    @app.get('/user', response_model=UserPageListResponse, response_model_exclude_unset=True)
    def list_users(ssn: sa.orm.Session = fastapi.Depends(dep.db_ssn),
                   query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        api = QueryApi(ssn, UserCrudParams(), query_object)
        users = api.list()
        links = api.query.page_links()
        return {
            'users': users,
            'next': links.next,
            'prev': links.prev,
        }

    @app.get('/user/count', response_model=CountResponse, response_model_exclude_unset=True)
    def count_users(ssn: sa.orm.Session = fastapi.Depends(dep.db_ssn),
                    query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        api = QueryApi(ssn, UserCrudParams(), query_object)
        return {'count': api.count()}

    @app.get('/user/{id}', response_model=UserGetResponse, response_model_exclude_unset=True)
    def get_user(id: int, ssn: sa.orm.Session = fastapi.Depends(dep.db_ssn),
                 query_object: Optional[QueryObject] = fastapi.Depends(query_object)):
        api = QueryApi(ssn, UserIdCrudParams(id=id), query_object)
        return {'user': api.get()}

    # GraphQL
    gql_schema = schema_prepare()

    @resolves(gql_schema, 'Query', 'listUsers')
    def resolve_list_users(root, info: graphql.GraphQLResolveInfo):
        query_object = query_object_for(info, nested_path=('users',))
        with Session() as ssn:
            return list_users(ssn, query_object)  # reuse

    @resolves(gql_schema, 'Query', 'getUser')
    def resolve_get_user(root, info: graphql.GraphQLResolveInfo, id: int):
        query_object = query_object_for(info, nested_path=())
        with Session() as ssn:
            return get_user(id, ssn, query_object)['user']  # reuse

    @resolves(gql_schema, 'Query', 'countUsers')
    def resolve_count_users(root, info: graphql.GraphQLResolveInfo):
        query_object = query_object_for(info, nested_path=())
        with Session() as ssn:
            return count_users(ssn, query_object)['count']  # reuse

    # Run
    with db_create():
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
    # rw ; +ro, const fields, +relations
    id: int
    is_admin: bool

    articles: list[ArticleDb]

    # A field that is available but is never used (to test field exclusion)
    extra_field: str


@partial
class UserDbPartial(UserDb):
    pass


class UserCreate(UserBase):
    # rw ; +const fields, +relations
    is_admin: bool

    # NOTE: we do not use `ArticleCreate` because it requires a user_id
    articles: list[ArticleBase] = pd.Field(None)


class UserUpdate(UserBase):
    # rw ; +const fields, +relations; +skippable PK
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


@partial
class ArticleDbPartial(ArticleDb):
    pass


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

type UserBase {
    # rw fields
    login: String!
    name: String!
}

type User @inherits(type: "UserBase") {
    # rw ; +ro, const fields, +relations
    id: Int!
    is_admin: Boolean!
    # articles: [Article]
}

input UserCreate @inherits(type: "UserBase") {
    # rw ; +const fields, +relations
    is_admin: Boolean!
    articles: [ArticleCreateForUser]
}

input UserUpdate @partial @inherits(type: "UserBase") {
    # rw ; +const fields, +relations; +skippable PK
    id: Int!
    new_articles: [ArticleCreateForUser]!
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


def schema_prepare() -> graphql.GraphQLSchema:
    """ Build a GraphQL schema for testing JessiQL queries """
    from jessiql.integration.graphql.schema import graphql_jessiql_schema
    from apiens.tools.graphql.directives import inherits, partial
    schema_sdl = '\n'.join((
        GQL_SCHEMA,
        # Directives
        inherits.DIRECTIVE_SDL,
        partial.DIRECTIVE_SDL,
        # QueryObject and QueryObjectInput
        graphql_jessiql_schema,
    ))

    # Build
    schema = graphql.build_schema(schema_sdl)

    # Register directives
    inherits.install_directive_to_schema(schema)
    partial.install_directive_to_schema(schema)

    # Helper: query
    def gq(query: str, **variable_values):
        """ Make a GraphqQL query """
        return graphql_query_sync(schema, query, **variable_values)

    schema.q = gq

    # Done
    return schema

# endregion

# region: DB tools

# DB Engine
engine = sa.engine.create_engine(DATABASE_URL)


@contextmanager
def Session() -> sa.orm.Session:
    """ DB Session as a context manager """
    ssn = sa.orm.Session(bind=engine, autoflush=True, future=True)

    try:
        yield ssn
    finally:
        ssn.close()

class dep:
    @staticmethod
    def db_ssn() -> sa.orm.Session:
        """ FastAPI Dependency: SqlAlchemy Session """
        with Session() as ssn:
            yield ssn


@contextmanager
def db_create():
    with jessiql.testing.created_tables(engine, Base.metadata):
        yield


def db_cleanup(ssn: sa.orm.Session = None):
    jessiql.testing.truncate_db_tables(ssn.connection() if ssn else engine, Base.metadata)


def all_users(ssn: sa.orm.Session = None) -> list[User]:
    """ Load all users from the database, return """
    stack = ExitStack()
    if not ssn:
        ssn = stack.enter_context(Session())

    with stack:
        return ssn.query(User).order_by(User.id.asc()).all()

def all_articles(ssn: sa.orm.Session) -> list[Article]:
    return ssn.query(Article).order_by(Article.id.asc()).all()

# endregion
