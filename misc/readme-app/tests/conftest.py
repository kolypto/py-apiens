from contextlib import contextmanager
import pytest

from jessiql.testing.recreate_tables import (
    truncate_db_tables,
    recreate_db_tables,
    check_recreate_necessary,
)

# Prepare DB
from app.globals.postgres import SessionMaker, Session

@pytest.fixture()
def ssn(_prepare_clean_database) -> Session:
    with SessionMaker() as ssn:
        yield ssn


@pytest.fixture(autouse=True)
def _assert_no_active_sessions():
    """ Make sure that every session is properly closed """
    from app.globals.postgres import assert_no_active_sqlalchemy_sessions
    assert_no_active_sqlalchemy_sessions()


@pytest.fixture(scope='session')
def _recreate_database_if_necessary():
    """ Prepare database structure """
    # Make sure we only destroy data in the test DB
    assert 'test_apiens' == engine.url.database

    # Recreate if necessary
    metadata = models.Base.metadata
    if check_recreate_necessary(engine, metadata):
        recreate_db_tables(engine, metadata)


@pytest.fixture()
def _prepare_clean_database(_recreate_database_if_necessary):
    """ Prepare a working database for the application """
    truncate_db_tables(engine, models.Base.metadata)

# Test client
from app.expose.fastapi.app import asgi_app
from app.expose.graphql.schema import app_schema

from apiens.tools.fastapi.test_client import TestClient
from apiens.tools.graphql.testing import test_client, test_client_api


class ApiClient(test_client_api.GraphQLClientMixin, TestClient):
    GRAPHQL_ENDPOINT = '/graphql/'

@pytest.fixture()
def api_client() -> ApiClient:
    """ Test client for FastAPI, with GraphQL capabilities """
    with ApiClient(asgi_app) as c:
        yield c

class GraphQLClient(test_client.GraphQLTestClient):
    def __init__(self):
        super().__init__(schema=app_schema, debug=True)

    # The GraphQL unit test needs to initialize its own context for the request.
    @contextmanager
    def init_context_sync(self):
        yield {}

@pytest.fixture()
def graphql_client() -> GraphQLClient:
    """ Test client for GraphQL schema """
    with GraphQLClient() as c:
        yield c


# Network gag
from apiens.testing.network_gag_conftest import stop_all_network, unstop_all_network
