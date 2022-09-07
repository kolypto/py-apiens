from collections import abc
import sqlalchemy as sa

from apiens.tools.settings import unit

# Import settings
from app.globals.config import settings


# Prepare some units for readability
min = unit('minute')
sec = unit('second')

# Initialize SqlAlchemy Engine: the connection pool
engine: sa.engine.Engine = sa.create_engine(
    # Use settings
    settings.POSTGRES_URL,
    future=True,
    # Configure the pool of connections
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    # Use `unit` to make the value more readable
    pool_recycle=10 * min >> sec,
)

# Initialize the SessionMaker: the way to get a SqlAlchemy Session
from sqlalchemy.orm import Session
SessionMakerFn = abc.Callable[[], Session]

SessionMaker: SessionMakerFn = sa.orm.sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# In testing, make sure that every connection is properly closed.
if settings.is_testing:
    # Prepare a new SessionMaker that tracks every opened connection
    from apiens.tools.sqlalchemy.session.session_tracking import TrackingSessionMaker
    SessionMaker = TrackingSessionMaker(class_=SessionMaker.class_, **SessionMaker.kw)

    # Define a function for unit-tests: check that all Sessions were properly close()d
    def assert_no_active_sqlalchemy_sessions():
        SessionMaker.assert_no_active_sessions()  
