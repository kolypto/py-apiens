from typing import Union
import sqlalchemy as sa
import sqlalchemy.orm

from itertools import chain
from contextlib import contextmanager

# Shortcuts
from apiens.testing.recreate_tables import created_tables, truncate_db_tables
from apiens.tools.sqlalchemy.sainfo.version import SA_13, SA_14, SA_20
from tests.conftest import DATABASE_URL
try:
    # SA 1.4
    from sqlalchemy.orm import declarative_base, DeclarativeMeta
except ImportError:
    # 1.3
    from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta



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


# copy-pasted from jessiql/testing/table_data.py
def insert(connection: sa.engine.Connection, Model: Union[sa.sql.Selectable, type], *values: dict):
    """ Helper: run a query to insert many rows of Model into a table using low-level SQL statement

    Example:
        insert(connection, Model,
               dict(id=1),
               dict(id=2),
               dict(id=3),
        )
    """
    all_keys = set(chain.from_iterable(d.keys() for d in values))
    assert values[0].keys() == set(all_keys), 'The first dict() must contain all possible keys'

    stmt = sa.insert(Model).values(values)
    connection.execute(stmt)