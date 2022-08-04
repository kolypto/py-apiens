from typing import Optional
from xml.etree.ElementInclude import include

from apiens.testing.object_match import DictMatch
from apiens.testing import model_match


def test_typed_dict():
    from typing import TypedDict

    # === Test: Typed Dict
    class User(TypedDict):
        id: int
        login: str
        name: Optional[str]

    assert model_match.match(User).jsonable() == USER_MATCH

    # === Test: partial Typed Dict
    class PartialUser(TypedDict, total=False):
        id: int
        login: str
        name: Optional[str]

    assert model_match.match(PartialUser).jsonable() == USER_PARTIAL_MATCH


def test_dataclass():
    from dataclasses import dataclass

    # === Test: dataclass
    @dataclass
    class User:
        id: int
        login: str
        name: Optional[str]

    assert model_match.match(User).jsonable() == USER_MATCH


def test_pydantic():
    import pydantic as pd

    # === Test: Pydantic
    class User(pd.BaseModel):
        id: int
        login: str
        name: Optional[str] = ...

    assert model_match.match(User).jsonable() == USER_MATCH

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

    assert model_match.match(User).jsonable() == {
        'fields': {
            'id': DictMatch(required=True, nullable=False),
            'name': DictMatch(required=False, nullable=True),
            'age': DictMatch(required=True, nullable=True),
        }
    }


def test_sqlalchemy():
    import sqlalchemy as sa
    import sqlalchemy.orm
    from tests.lib import declarative_base

    # === Test: SqlAlchemy
    Base = declarative_base()

    class User(Base):
        __tablename__ = 'u'

        id = sa.Column(sa.Integer, primary_key=True)
        login = sa.Column(sa.String, nullable=False)
        name = sa.Column(sa.String)

    assert model_match.match(User).jsonable() == {
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

    assert model_match.match(schema.type_map['User']).jsonable() == USER_UNREQUIRED_MATCH  # there's no "required" with GraphQL
    assert model_match.match(schema.type_map['UserInput']).jsonable() == USER_MATCH


def test_transform():
    """ Test transformations """
    import sqlalchemy as sa
    from tests.lib import declarative_base

    Base = declarative_base()

    class User(Base):
        __tablename__ = 'u'

        id = sa.Column(sa.Integer, primary_key=True)
        login = sa.Column(sa.String)
        name = sa.Column(sa.String)

    user_match = model_match.match(User)


    # === Test: ModelInfo.nullable(), ModelInfo.required()
    assert user_match.nullable(True).required(False).jsonable() == {
        'fields': {
            'id': {'name': 'id', 'type': None, 'required': False, 'nullable': True, 'aliases': set()},
            'login': {'name': 'login', 'type': None, 'required': False, 'nullable': True, 'aliases': set()},
            'name': {'name': 'name', 'type': None, 'required': False, 'nullable': True, 'aliases': set()},
        },
    }


    # === Test: select
    assert model_match.select_fields(user_match, model_match.include_only('id')).jsonable() == {
        'fields': {
            'id': {'name': 'id', 'type': None, 'required': True, 'nullable': False, 'aliases': set()},
        }
    }

    # === Test: rename
    assert model_match.rename_fields_map(user_match, {'id': 'Id'}).jsonable() == {
        'fields': {
            # renamed
            'Id': DictMatch({'name': 'Id'}),
            # not renamed, not removed
            'login': DictMatch({'name': 'login'}),
            'name': DictMatch({'name': 'name'}),
        }
    }

    # === Test: JessiQL rewriter
    # This test only works if JessiQL is available
    try:
        import jessiql
    except ImportError:
        pass
    else:
        upper_case_rewrite = jessiql.rewrite.Transform(str.upper, str.lower)
        settings = jessiql.QuerySettings(
            rewriter=jessiql.rewrite.RewriteSAModel(upper_case_rewrite, Model=User),
        )

        assert model_match.jessiql_rewrite_api_to_db(user_match, settings.rewriter, context=jessiql.rewrite.FieldContext.SELECT).jsonable() == {
            'fields': {
                'ID': DictMatch({'name': 'ID'}),
                'LOGIN': DictMatch({'name': 'LOGIN'}),
                'NAME': DictMatch({'name': 'NAME'}),
            },
        }








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

USER_UNREQUIRED_MATCH = {
    'fields': {
        # required=None: every field
        name: {**field, 'required': None}
        for name, field in USER_MATCH['fields'].items()
    }
}
