import os
from pydantic import PostgresDsn
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from typing import Callable


engine: Engine = create_engine(
    PostgresDsn.build(
        scheme="postgresql",
        user=os.getenv("POSTGRES_USER", 'postgres'),
        password=os.getenv("POSTGRES_PASSWORD", 'postgres'),
        host=os.getenv("POSTGRES_HOST", 'localhost'),
        path=f"/{os.getenv('POSTGRES_DB', 'test_apiens')}",
    )
)


# Type: any callable that returns a new SqlAlchemy Session
SessionMakerCallable = Callable[[], Session]

# Session maker: create a new Session object
SessionMaker: SessionMakerCallable = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def recreate_db_tables(engine: Engine, *, Base):
    """ DROP all tables, then CREATE all tables """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def db_session() -> Session:
    """ Get a database Session """
    session = SessionMaker()

    try:
        yield session
    finally:
        session.close()
