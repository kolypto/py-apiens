import os
import pytest
import sqlalchemy as sa


@pytest.fixture()
def engine() -> sa.engine.Engine:
    return sa.engine.create_engine(
        DATABASE_URL,
        # echo=True
    )


@pytest.fixture(scope='function')
def connection(engine: sa.engine.Engine) -> sa.engine.Connection:
    with engine.connect() as conn:
        yield conn


# URL of the database to connect to
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:postgres@localhost/test_apiens')
