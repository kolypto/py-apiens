""" Test: apiens/crud + apiens/tools/ariadne """

from contextlib import contextmanager
from dataclasses import dataclass

import graphql
import ariadne
import ariadne.asgi

import sqlalchemy as sa
import sqlalchemy.orm

import jessiql
import jessiql.integration.graphql

import apiens.crud
import apiens.tools.ariadne.directives
from apiens.tools.graphql.testing.query import graphql_query_sync
from apiens.tools.sqlalchemy.commit import db_transaction


def test_ariadne():
    """ Test CRUD API: create(), get() -- with errors returned as result payload """
    def main():
        # === Test: Create
        res = graphql_query_sync(schema,
                                 'mutation ($user: UserCreate!) { createUser(user: $user) { ok error { name } user { id } } }',
                                 user={'is_admin': False, 'login': 'root', 'name': 'Neo'})
        assert res['createUser'] == {
            'ok': True,
            'error': None,
            'user': {'id': 1},
        }

        # === Test: Query
        res = graphql_query_sync(schema, 'query ($id: Int!) { getUser(id: $id) { id login } }', id=1)
        assert res['getUser'] == {
            'id': 1, 'login': 'root',
        }

    # Crud Params
    @dataclass
    class UserIdParams(apiens.crud.CrudParams):
        crudsettings = apiens.crud.CrudSettings(Model=User, debug=True)

        id: int

    # Resolver: query
    query = ariadne.QueryType()

    @query.field('getUser')
    def resolve_get_user(_, info: graphql.GraphQLResolveInfo, id: int):
        query_object = jessiql.integration.graphql.query_object_for(info)
        with Session() as ssn:
            api = apiens.crud.QueryApi(ssn, UserIdParams(id=id), query_object)
            res = api.get()
            return res

    # Resolver: mutation
    mutation = ariadne.MutationType()

    @mutation.field('createUser')
    def resolve_create_user(_, info: graphql.GraphQLResolveInfo, user: dict):
        with Session() as ssn, db_transaction(ssn):
            api = apiens.crud.MutateApi(ssn, UserIdParams(id=None))
            res = api.create(user)
            return {'ok': True, 'error': None, 'user': res}

    # Schema
    schema = ariadne.make_executable_schema(
        [GQL_SCHEMA, *GQL_SCHEMAS()],
        # bindables
        query, mutation,
        ariadne.snake_case_fallback_resolvers,
        directives={
            **apiens.tools.ariadne.directives.directives_map,
        }
    )
    # app = ariadne.asgi.GraphQL(schema, debug=True)

    with db_create():
        main()

# GraphQL definitions

# language=graphql
GQL_SCHEMA = ariadne.gql('''
type Query {
    getUser(id: Int!, query: QueryObjectInput): User!
    listUsers(query: QueryObjectInput): [User!]!
}

type Mutation {
    createUser(user: UserCreate!): UserMutationPayload!
    updateUserId(id: Int, user: UserUpdate!): UserMutationPayload!
    deleteUser(id: Int!): UserMutationPayload!
}

type Payload {
    ok: Boolean!
    error: ErrorObject
}

type UserMutationPayload @inherits(type: "Payload") {
    user: User
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
}

input UserUpdate @partial @inherits(type: "UserBase") {
    # rw ; +const fields, +relations; +skippable PK
    id: Int!
}
''')


def GQL_SCHEMAS() -> list[str]:
    """ Additional schemas to load """
    import jessiql.integration.graphql
    import apiens.error
    from apiens.tools.graphql import directives

    return [
        ariadne.load_schema_from_path(*jessiql.integration.graphql.__path__),
        ariadne.load_schema_from_path(*apiens.error.__path__),
        directives.partial.DIRECTIVE_SDL,
        directives.inherits.DIRECTIVE_SDL,
    ]


# SqlAlchemy models
from tests.lib import engine, Session, created_tables, truncate_db_tables, declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = 'u'

    id = sa.Column(sa.Integer, primary_key=True)
    is_admin = sa.Column(sa.Boolean, nullable=False)
    login = sa.Column(sa.String)
    name = sa.Column(sa.String)

@contextmanager
def db_create():
    with created_tables(engine, Base.metadata):
        yield


def db_cleanup(ssn: sa.orm.Session = None):
    truncate_db_tables(ssn.connection() if ssn else engine, Base.metadata)
