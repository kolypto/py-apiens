from dataclasses import dataclass
from typing import Optional

from apiens.testing.object_match import DictMatch
from apiens.testing.models_match.match import match


def test_typed_dict():
    from typing import TypedDict

    # === Test: Typed Dict
    class User(TypedDict):
        id: int
        login: str
        name: Optional[str]

    assert match(User).jsonable() == USER_MATCH

    # === Test: partial Typed Dict
    class PartialUser(TypedDict, total=False):
        id: int
        login: str
        name: Optional[str]

    assert match(PartialUser).jsonable() == USER_PARTIAL_MATCH


def test_dataclass():
    from dataclasses import dataclass

    # === Test: dataclass
    @dataclass
    class User:
        id: int
        login: str
        name: Optional[str]

    assert match(User).jsonable() == USER_MATCH


def test_pydantic():
    import pydantic as pd

    # === Test: Pydantic
    class User(pd.BaseModel):
        id: int
        login: str
        name: Optional[str] = ...

    assert match(User).jsonable() == USER_MATCH

    # === Test: Pydantic required-optional
    class User(pd.BaseModel):
        # Required, Non-Nullable
        id: int

        # Skippable, nullable
        name: Optional[str]

        # Required-Optional: "a field that can take a None value while still being required"
        age: Optional[int] = ...

        # Partial objects.
        # Pydantic does not support skippable fields.
        # See: apiens.tools.pydantic.partial

    assert match(User).jsonable() == {
        'fields': {
            'id': DictMatch(required=True, nullable=False),
            'name': DictMatch(required=False, nullable=True),
            'age': DictMatch(required=True, nullable=True),
        }
    }


def test_sqlalchemy():
    import sqlalchemy as sa
    import sqlalchemy.orm
    from jessiql.util.sacompat import declarative_base

    # === Test: SqlAlchemy
    Base = declarative_base()

    class User(Base):
        __tablename__ = 'u'

        id = sa.Column(sa.Integer, primary_key=True)
        login = sa.Column(sa.String, nullable=False)
        name = sa.Column(sa.String)

    assert match(User).jsonable() == {
        'fields': {
            **USER_MATCH['fields'],
            'name': {**USER_MATCH['fields']['name'], 'required': False},
        }
    }


def test_graphql():
    import graphql

    # === Test: graphql
    # language=graphql
    schema = graphql.build_schema('''
        type User {
            id: Int!
            login: String!
            name: String
        }
        
        input UserInput {
            id: Int!
            login: String!
            name: String
        }
    ''')

    assert match(schema.type_map['User']).jsonable() == USER_UNKREQUIRED_MATCH  # there's no "required" with GraphQL
    assert match(schema.type_map['UserInput']).jsonable() == USER_MATCH


# Classic matches
USER_MATCH = {
    'fields': {
        # required=True: every field
        # nullable: only Optional[] fields are nullable
        'id': {'name': 'id', 'type': None, 'required': True, 'nullable': False, 'aliases': set()},
        'login': {'name': 'login', 'type': None, 'required': True, 'nullable': False, 'aliases': set()},
        'name': {'name': 'name', 'type': None, 'required': True, 'nullable': True, 'aliases': set()},
    }
}

USER_PARTIAL_MATCH = {
    'fields': {
        # required=False: every field
        # nullable: only Optional[] fields are nullable
        name: {**field, 'required': False}
        for name, field in USER_MATCH['fields'].items()
    }
}

USER_UNKREQUIRED_MATCH = {
    'fields': {
        # required=None: every field
        name: {**field, 'required': None}
        for name, field in USER_MATCH['fields'].items()
    }
}
