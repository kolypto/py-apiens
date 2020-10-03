import pytest
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import load_only

from apiens.views.crud import InstanceHistoryProxy
from tests.lib.query_logger import ExpectedQueryCounter


def test_columns(ssn: sa.orm.Session):
    """ Simple test of InstanceHistoryProxy with columns """
    # Prepare
    ssn.add(User(id=1, name='John', age=18))
    ssn.commit()

    # Check initial state
    user: User = ssn.query(User).get(1)
    old_user: User = InstanceHistoryProxy(user)  # noqa

    def old_user_is_correct():
        assert old_user.id == 1
        assert old_user.name == 'John'
        assert old_user.age == 18

    # Modify
    user.id = 1000
    user.name = 'CHANGED'
    user.age = 1800
    old_user_is_correct()  # still good

    # Flush
    ssn.flush()
    old_user_is_correct()  # still good


def test_property(ssn: sa.orm.Session):
    """ Test getting historical @property values through an InstanceHistoryProxy """
    # Prepare
    ssn.add(User(id=1, name='John', age=18))
    ssn.commit()

    # Load
    user: User = ssn.query(User).get(1)
    old_user: User = InstanceHistoryProxy(user)  # noqa

    # @property access
    assert user.age_in_100_years == 118
    assert old_user.age_in_100_years == 118

    # Modify
    user.age = 20
    assert old_user.age_in_100_years == 118  # still good


def test_relationship(ssn: sa.orm.Session):
    """ Test getting historical relationship values through an InstanceHistoryProxy """
    # Prepare
    ssn.add(User(id=1, name='John', age=18))
    ssn.add(User(id=2, name='Jack', age=18))
    ssn.add(Article(id=1, title='Python', author_id=1))
    ssn.commit()

    # Users
    john = ssn.query(User).get(1)
    jack = ssn.query(User).get(2)

    # Article
    article: Article = ssn.query(Article).get(1)
    old_article: Article = InstanceHistoryProxy(article)  # noqa

    assert article.author == john  # load it
    assert old_article.author == john  # works

    # Modify
    article.author = jack
    assert old_article.author == john  # still works

    # Flush
    ssn.flush()
    assert old_article.author == john  # still works


def test_does_not_lose_history(ssn: sa.orm.Session):
    """ Extensive test of InstanceHistoryProxy with query counters and lazy loads """
    assert ssn.autoflush == False, 'this test relies on Session.autoflush=False'
    engine = ssn.get_bind()

    # Prepare
    ssn.add(User(id=1, name='John', age=18))
    ssn.add(Article(id=1, title='Python', author_id=1))
    ssn.commit()



    # === Test 1: ModelHistoryProxy does not lose history when flushing a session
    ssn.expunge_all()  # got to reset; otherwise, the session might reuse loaded objects
    user = ssn.query(User).get(1)

    with ExpectedQueryCounter(engine, 0, 'Expected no queries here'):
        old_user_hist = InstanceHistoryProxy(user)  # issues no queries

        # Modify
        user.name = 'CHANGED'

        # History works
        assert old_user_hist.name == 'John'

    # Flush
    ssn.flush()

    # History is NOT broken!
    assert old_user_hist.name == 'John'

    # Change another column after flush; history is still NOT broken!
    user.age = 1800
    assert old_user_hist.age == 18  # correct

    # Undo
    ssn.rollback()



    # === Test 1: ModelHistoryProxy does not lose history when lazyloading a column
    ssn.expunge_all()  # got to reset; otherwise, the session might reuse loaded objects
    user = ssn.query(User).options(load_only('name')).get(1)

    with ExpectedQueryCounter(engine, 0, 'Expected no queries here'):
        old_user_hist = InstanceHistoryProxy(user)  # issues no queries
        user.name = 'CHANGED'
        assert old_user_hist.name == 'John'

    # Load a column
    with ExpectedQueryCounter(engine, 1, 'Expected 1 lazyload query'):
        user.age  # get an unloaded column

    # History is NOT broken!
    assert old_user_hist.name == 'John'



    # === Test 2: ModelHistoryProxy does not lose history when lazyloading a one-to-many relationship
    ssn.expunge_all()  # got to reset; otherwise, the session might reuse loaded objects
    user = ssn.query(User).get(1)

    with ExpectedQueryCounter(engine, 0, 'Expected no queries here'):
        old_user_hist = InstanceHistoryProxy(user)
        user.name = 'CHANGED'
        assert old_user_hist.name == 'John'  # History works

    # Load a relationship
    with ExpectedQueryCounter(engine, 1, 'Expected 1 lazyload query'):
        list(user.articles)

    # History is NOT broken!
    assert old_user_hist.name == 'John'



    # === Test 3: ModelHistoryProxy does not lose history when lazyloading a one-to-one relationship
    ssn.expunge_all()  # got to reset; otherwise, the session might reuse loaded objects
    article = ssn.query(Article).get(1)

    with ExpectedQueryCounter(engine, 0, 'Expected no queries here'):
        old_article_hist = InstanceHistoryProxy(article)
        article.title = 'CHANGED'
        assert old_article_hist.title == 'Python'  # works

    # Load a relationship
    with ExpectedQueryCounter(engine, 1, 'Expected 1 lazyload query'):
        article.author

    # History is NOT broken!
    assert old_article_hist.title == 'Python'  # works






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
    age = sa.Column(sa.Integer)

    articles = sa.orm.relationship(lambda: Article, back_populates='author')

    @property
    def age_in_100_years(self):
        return self.age + 100


class Article(Base):
    __tablename__ = 'a'

    id = sa.Column(sa.Integer, nullable=False, primary_key=True)
    title = sa.Column(sa.String)

    author_id = sa.Column(sa.ForeignKey(User.id))
    author = sa.orm.relationship(User, back_populates='articles')
