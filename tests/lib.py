import sqlalchemy as sa
import sqlalchemy.orm

from contextlib import contextmanager
from jessiql.sainfo.version import SA_13, SA_14
from jessiql.util.sacompat import declarative_base  # noqa: shortcut 
from jessiql.testing import insert, created_tables, truncate_db_tables  # noqa: shortcut

from tests.conftest import DATABASE_URL



# SqlAlchemy connection engine
engine = sa.engine.create_engine(DATABASE_URL)


@contextmanager
def Session() -> sa.orm.Session:
    """ DB Session as a context manager """
    if SA_13:
        ssn = sa.orm.Session(bind=engine, autoflush=True)
    elif SA_14:
        ssn = sa.orm.Session(bind=engine, autoflush=True, future=True)
    else:
        raise NotImplementedError

    try:
        yield ssn
    finally:
        ssn.close()

