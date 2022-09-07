from redis import Redis, ConnectionPool

from app.globals.config import settings


# Pool of Redis connections
connection_pool = ConnectionPool.from_url(
    settings.REDIS_CONNECT_URL,
    health_check_interval=60,
)


def get_redis() -> Redis:
    """ Get a new Redis connection

    NOTE: don't forget to close() the connection!

    Example:
    >>> with get_redis() as redis:
    >>>     ...
    """
    return Redis(connection_pool=connection_pool)


# In testing, make sure that every connection is properly closed
if settings.is_testing:
    # Track every open session
    from apiens.tools.sqlalchemy.session.session_tracking import ActiveObjectsRegistry
    active_sessions = ActiveObjectsRegistry(weak=False)

    _original_get_redis = get_redis
    def get_redis() -> Redis:
        redis = _original_get_redis()
        active_sessions.add_and_decorate(redis, 'close')
        return redis

    # Define a function for unit-tests: check that all Sessions were properly close()d
    def assert_no_active_redis_sessions():
        active_sessions.assert_no_active_objects()
