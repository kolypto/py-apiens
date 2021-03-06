from contextlib import contextmanager

import mongosql
import pydantic
import pytest
import sa2schema as sa2
import sqlalchemy as sa
import sqlalchemy.orm
from sa2schema import loads_attributes_readcode
from sqlalchemy.ext.declarative.api import declarative_base
from typing import List

from apiens.views.crud import CrudSettings, CrudBase, saves_custom_fields
from apiens.views.mongoquery_crud.mongocrud_settings import MongoCrudSettings
from apiens.views.mongoquery_crud.mongocrudbase import MongoCrudBase
from apiens.testing.object_match import DictMatch, Parameter


@pytest.mark.usefixtures('sample_users_articles')
def test_user_crud_basic(ssn: sa.orm.Session):
    ABSENT = object()

    class UserCrud(MongoCrudBase[User]):
        crudsettings = MongoCrudSettings(
            User,
            # Proper schemas
            ResponseSchema=schemas.load.User,
            CreateSchema=schemas.modify.User,
            UpdateSchema=schemas.modify.User,
        ).query_defaults(
            # Put a {limit:1} just to test that it works
            limit=1,
        ).mongosql_config(
            # Mimic GraphQL: very very few fields by default
            default_projection=('id',),
            # Only one relationship is allowed
            allowed_relations=('articles',),
            # Tell them everything about properties
            bundled_project={
                'age_in_100_years': ['age'],
            },
            # Configure related objects
            related={
                'articles': mongosql.MongoQuerySettingsDict(
                    default_projection=('id',),
                    allowed_relations=('author',),
                    related={
                        'author': mongosql.MongoQuerySettingsDict(
                            default_projection=('id',),
                        )
                    }
                )
            },
            # Absolute limit
            max_items=10,
        ).create_or_update_config(
            # Enable create_or_update()
            CreateOrUpdateSchema=schemas.modify.User,
        ).exclude_config(
            create_and_update=('articles',),
        ).debug(True)

        # One special field handled by saves_custom_fields()

        @saves_custom_fields('passwd')
        def save_passwd(self, /, new: User, prev: User = None, *, passwd: str = ABSENT):
            if passwd is not ABSENT:
                new.passwd = f'hash({passwd})'  # fake hashing function

    # Validate
    UserCrud.crudsettings.test_crud_configuration(UserCrud)

    # === Test: list()
    list_users = lambda **query_object: list(UserCrud(ssn, query_object=query_object).list())

    # Query as is. The default `limit=1` applies
    with session_reset(ssn):
        users = list(UserCrud(ssn).list())
        assert len(users) == 1  # only 1 user, because {limit: 1} is the default
        assert users[0] == {
            'id': 1,  # only one field is loaded! (default projection)
        }

    # Query with limit=2
    with session_reset(ssn):
        users = list_users(limit=2)
        assert len(users) == 2  # 2 users now

    # Query with filter
    with session_reset(ssn):
        users = list_users(limit=100, filter={'age': {'$lte': 20}})
        assert len(users) == 2  # only 2 users that young


    # === Test: count()
    count_users = lambda **query_object: UserCrud(ssn, query_object=query_object).count()

    # Query as is.
    # See that the limit does not apply
    with session_reset(ssn):
        n = count_users()
        assert n == 5  # all users are seen, without limits

    # Query with filter
    with session_reset(ssn):
        n = count_users(filter={'age': {'$lte': 20}})
        assert n == 2  # only 2 users that young

    # === Test: get()
    get_user = lambda kwargs, **query_object: (
        UserCrud(ssn, query_object=query_object)
            .get(**kwargs)
    )

    # Query as is
    with session_reset(ssn):
        assert get_user({'id': 1}, project=['id', 'name']) == {'id': 1, 'name': 'John'}

    # Try: query with insufficient information
    # It should NOT raise a KeyError. It should just fail to find anything
    # (because internally, it will try to find a row with PK=None)
    with session_reset(ssn):
        with pytest.raises(sa.orm.exc.NoResultFound):
            get_user({'name': 'hey'})

    # Try: relationships
    with session_reset(ssn):
        assert get_user({'id': 1}, join={'articles': {'project': ['id', 'author']}}) == {
            'id': 1,
            'articles': [
                {'id': 1, 'author': {'id': 1}},
                {'id': 2, 'author': {'id': 1}},
            ]
        }

    # Try: @property
    with session_reset(ssn):
        assert get_user({'id': 1}, project=['age_in_100_years']) == {
            # 'id': 1,  # not included because not requested!
            'age_in_100_years': 18 + 100,  # yeah, loaded!
        }


    # === Prepare two crud handlers:
    # One that only returns the `id`
    crud = UserCrud(ssn, query_object=dict(project=['id']))
    # One that does not return the `id`, but gives you the `name` and the `age`
    crud_fields = UserCrud(ssn, query_object=dict(project=['name', 'age']))

    # well, actually, those crud handlers aren't supposed to be reused.
    # but currently, there is nothing that prevents us from doing so.
    # So... why not?


    # === Test: create()
    # Create with minimum fields
    user = crud.create({'name': 'Bird'})
    assert user == {
        'id': (bird_id := Parameter()),  # projected
        # nothing else is included, because not set.
    }

    # Create with a writable @property
    # This is only possible because schemas.create was configured to include attributes
    user = crud.create({'name': 'Turtle', 'age_in_100_years': 169})
    assert user == {
        'id': (turtle_id := Parameter()),
    }
    assert crud_fields.get(id=turtle_id.value) == {
        'name': 'Turtle',
        'age': 69,
    }

    # Create: try to set a primary key. Ignored.
    user = crud.create({'id': 1000, 'name': 'Lion'})
    assert user == {
        'id': (lion_id := Parameter()),  # projected
    }
    assert lion_id.value != 1000
    assert crud_fields.get(id=lion_id.value) == {
        'name': 'Lion',
        'age': None,
    }

    # Create: try to set an unknown attribute (fail)
    with pytest.raises(pydantic.ValidationError) as e:
        crud.create({'name': 'Godzilla', 'power': 'plasma-beam'})

    assert e.value.errors() == [
        DictMatch({'loc': ('power',), 'type': 'value_error.extra'})
    ]

    # Create: @saves_custom_fields()
    user = crud.create({'name': 'Human', 'passwd': 'qwerty'})
    assert user == {
        'id': (human_id := Parameter()),

    }
    assert crud_fields.get(id=human_id.value) == {
        'name': 'Human',
        'age': None,
    }

    assert len(saves_custom_fields.all_decorated_from(UserCrud)) == 1  # found our decorated objecr

    passwd = ssn.query(User).get(human_id.value).passwd
    assert passwd == 'hash(qwerty)'  # custom handler worked!

    # Commit
    crud.commit()  # it won't commit automatically



    # === Test: update()
    # Update a column
    bird = crud_fields.update({'age': 3}, id=bird_id.value)
    assert bird == {
        'name': 'Bird',
        'age': 3,
    }

    # Update the primary key (ignored)
    bird = crud_fields.update({'id': 300, 'age': 6}, id=bird_id.value)
    assert bird == {
        'name': 'Bird',
        'age': 6,  # modified
    }

    # Provide the primary key in the input
    bird = crud_fields.update({'id': bird_id.value, 'age': 16})
    assert bird == {
        'name': 'Bird',
        'age': 16,  # updated
    }

    # Provide the wrong PK in the input
    with pytest.raises(sa.orm.exc.NoResultFound):
        crud.update({'id': 1000})

    # Do not provide the PK
    with pytest.raises(sa.orm.exc.NoResultFound):
        crud.update({})  # no PK -> not found


    # === Test: delete()
    # Delete
    bird = crud_fields.delete(id=bird_id.value)
    assert bird == {
        'name': 'Bird',
        'age': 16,
    }

    # Deleted
    assert ssn.query(User).filter_by(id=bird_id.value).one_or_none() is None


    # === Test: create_or_update()
    # Try update(): pk provided, but not found. Error.
    with pytest.raises(sa.orm.exc.NoResultFound):
        lizard = crud.create_or_update({'id': 1000, 'name': 'Lizard'})

    # Try create(): pk not provided, created ok
    lizard = crud.create_or_update({'name': 'Lizard'})
    assert lizard == {
        'id': (lizard_id := Parameter()),
    }
    assert crud_fields.get(id=lizard_id.value) == {
        'name': 'Lizard',
        'age': None,
    }

    # Try update() again
    lizard = crud_fields.create_or_update({'id': lizard_id.value, 'age': 15})
    assert lizard == {
        'name': 'Lizard',
        'age': 15,  # updated
    }


    # === Test: commit()
    ssn.commit()  # just to make sure we haven't done anything wrong


def test_user_crud_configurations():
    """ Test miscellaneous CrudSettings configurations """
    Response = dict(
        ResponseSchema=schemas.load.User,
        CreateSchema=schemas.modify.User,
        UpdateSchema=schemas.modify.User,
    )

    # === Test: default CrudSettings
    class UserCrud(CrudBase):
        crudsettings = CrudSettings(User, **Response)

        @saves_custom_fields('articles')  # got to provide it ; otherwise, it complains
        def save_articles(self): raise NotImplementedError

    # Nothing special about it; primary key will be excluded by default
    UserCrud.crudsettings.test_crud_configuration(UserCrud)  # no error
    assert UserCrud.crudsettings._primary_key == ('id',)
    assert UserCrud.crudsettings._exclude_on_create == frozenset(['id'])
    assert UserCrud.crudsettings._exclude_on_update == frozenset(['id'])

    # === Test: CrudSettings.primary_key_config()
    class UserCrud(CrudBase):
        crudsettings = CrudSettings(User, **Response).primary_key_config(
            primary_key=['id', 'login'],
        )

        @saves_custom_fields('articles')  # got to provide it ; otherwise, it complains
        def save_articles(self): raise NotImplementedError

    UserCrud.crudsettings.test_crud_configuration(UserCrud)  # no error
    assert UserCrud.crudsettings._primary_key == ('id', 'login')
    assert UserCrud.crudsettings._exclude_on_create == frozenset(['id', 'login'])
    assert UserCrud.crudsettings._exclude_on_update == frozenset(['id', 'login'])


    # === Test: CrudSettings.primary_key_config(natural_primary_key=True)
    class UserCrud(CrudBase):
        crudsettings = CrudSettings(User, **Response).primary_key_config(
            primary_key=['login'],
            natural_primary_key=True
        )

        @saves_custom_fields('articles')  # got to provide it ; otherwise, it complains
        def save_articles(self): raise NotImplementedError

    UserCrud.crudsettings.test_crud_configuration(UserCrud)  # no error
    assert UserCrud.crudsettings._primary_key == ('login',)
    assert UserCrud.crudsettings._exclude_on_create == frozenset()
    assert UserCrud.crudsettings._exclude_on_update == frozenset()


    # === Test: field_names_config()
    class UserCrud(CrudBase):
        crudsettings = CrudSettings(User, **Response).field_names_config(
            ro_fields=('id', 'articles', 'age_in_100_years'),
            rw_fields=('id', 'name', 'login', 'passwd', 'age'),
        )

        @saves_custom_fields('articles')  # got to provide it ; otherwise, it complains
        def save_articles(self): raise NotImplementedError

    UserCrud.crudsettings.test_crud_configuration(UserCrud)  # no error
    assert UserCrud.crudsettings._exclude_on_create == frozenset(['id', 'articles', 'age_in_100_years'])
    assert UserCrud.crudsettings._exclude_on_update == frozenset(['id', 'articles', 'age_in_100_years'])


    # === Test: field_names_config(const_fields)
    class UserCrud(CrudBase):
        crudsettings = CrudSettings(User, **Response).field_names_config(
            ro_fields=('id', 'age_in_100_years'),
            rw_fields=('id', 'name', 'passwd', 'age'),
            rw_relations=('articles',),
            const_fields=('login',),
        )

        @saves_custom_fields('articles')  # got to provide it ; otherwise, it complains
        def save_articles(self): raise NotImplementedError

    UserCrud.crudsettings.test_crud_configuration(UserCrud)  # no error
    assert UserCrud.crudsettings._exclude_on_create == frozenset(['id', 'age_in_100_years'])
    assert UserCrud.crudsettings._exclude_on_update == frozenset(['id', 'age_in_100_years', 'login'])



    # === Test: field_names_config(const_fields) + exclude_config()
    class UserCrud(CrudBase):
        crudsettings = CrudSettings(User, **Response).field_names_config(
            ro_fields=('id',),
            rw_fields=('id', 'name', 'passwd', 'age'),
            const_fields=('login',),
        ).exclude_config(
            create_and_update=('articles', 'age_in_100_years',),
        )

    UserCrud.crudsettings.test_crud_configuration(UserCrud)  # no error
    assert UserCrud.crudsettings._exclude_on_create == frozenset(['id', 'articles', 'age_in_100_years'])
    assert UserCrud.crudsettings._exclude_on_update == frozenset(['id', 'articles', 'age_in_100_years', 'login'])


    # === Test: @saves_custom_fields()
    class UserCrud(CrudBase):
        crudsettings = CrudSettings(User, **Response).field_names_config(
            ro_fields=('id', 'age_in_100_years'),
            rw_fields=('id', 'name', 'passwd', 'age'),
            rw_relations=('articles',),
            const_fields=('login',),
        )

        @saves_custom_fields('articles')
        def saves_articles(self, new: User, prev: User = None, articles: List[Article] = None):
            pass

    UserCrud.crudsettings.test_crud_configuration(UserCrud)  # no error
    assert UserCrud.crudsettings._exclude_on_create == frozenset(['id', 'age_in_100_years'])
    assert UserCrud.crudsettings._exclude_on_update == frozenset(['id', 'age_in_100_years', 'login'])


@contextmanager
def session_reset(ssn: sa.orm.Session):
    """ Reset the session when done """
    yield
    ssn.rollback()
    ssn.expunge_all()


@pytest.fixture()
def sample_users_articles(ssn: sa.orm.Session):
    """ Create a database with sample users and articles """
    # Make some users
    ssn.add_all([
        User(name='John', login='john', passwd='1', age=18, articles=[
            Article(title='Jam'),
            Article(title='Jeep'),
        ]),
        User(name='Mark', login='mark', passwd='2', age=20, articles=[
            Article(title='Map'),
            Article(title='Mop'),
        ]),
        User(name='Nick', login='nick', passwd='3', age=25, articles=[
            Article(title='Nap'),
            Article(title='Nil'),
        ]),
        User(name='Kate', login='kate', passwd='4', age=30, articles=[]),
        User(name='Cary', login='cary', passwd='5', age=35, articles=[]),
    ])
    ssn.commit()


@pytest.fixture()
def ssn() -> sa.orm.Session:
    """ Provide: a database connection """
    from .db import engine, recreate_db_tables, db_session
    recreate_db_tables(engine, Base=Base)

    yield from db_session()


Base = declarative_base()


class User(Base):
    __tablename__ = 'u'

    id = sa.Column(sa.Integer, nullable=False, primary_key=True)

    name = sa.Column(sa.String)
    login = sa.Column(sa.String)
    passwd = sa.Column(sa.String)

    age = sa.Column(sa.Integer)

    articles = sa.orm.relationship(lambda: Article, back_populates='author')

    @property
    @loads_attributes_readcode()
    def age_in_100_years(self):
        return self.age + 100

    @age_in_100_years.setter
    def age_in_100_years(self, age_in_100_years: int):
        self.age = age_in_100_years - 100


class Article(Base):
    __tablename__ = 'a'

    id = sa.Column(sa.Integer, nullable=False, primary_key=True)
    title = sa.Column(sa.String)

    author_id = sa.Column(sa.ForeignKey(User.id))
    author = sa.orm.relationship(User, back_populates='articles')


class schemas:
    # Models for loading from DB
    # All optional except for the primary key, which must be always present
    # Included fields: readable, inc. relationships
    load = sa2.pydantic.Models(
        __name__,
        naming='{model}Load',
        types=sa2.AttributeType.ALL_LOCAL_FIELDS | sa2.AttributeType.ALL_RELATIONSHIPS,
        Base=sa2.pydantic.SALoadedModel,
        make_optional=True,
    )
    load.sa_model(User, exclude=('passwd',))
    load.sa_model(Article)
    load.update_forward_refs()

    # Models for creates & updates
    # All fields are optional, inc. the primary key (which will be ignored when appropriate)
    # Included fields: writable, inc. properties
    modify = sa2.pydantic.Models(
        __name__,
        naming='{model}Update',
        types=sa2.AttributeType.ALL_LOCAL_FIELDS | sa2.AttributeType.ALL_RELATIONSHIPS,
        Base=sa2.pydantic.SALoadedModel,
        make_optional=True,
    )
    modify.sa_model(User)
    modify.sa_model(Article)
    modify.update_forward_refs()
