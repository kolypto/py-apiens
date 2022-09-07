from .conftest import GraphQLClient, ApiClient

def test_hello(graphql_client: GraphQLClient):
    """ Test hello() on GraphQL schema """
    #language=GraphQL
    q_hello = """
        query {
            hello
        }
    """

    res = graphql_client.execute(q_hello)
    assert res['hello'] == 'Welcome'

def test_hello_api(api_client: ApiClient):
    """ Test hello() on FastAPI GraphQL endpoint """
    #language=GraphQL
    q_hello = """
        query {
            hello
        }
    """

    res = api_client.graphql_sync(q_hello)
    assert res['hello'] == 'Welcome'
