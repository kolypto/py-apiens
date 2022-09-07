from app.expose.graphql.schema import app_schema


def test_no_unmarked_resolvers():
    """ Test that every resolver is properly marked 
    
    This test requires that developers put one of the following markers on their resolvers:
    * resolves_in_threadpool()
    * resolves_nonblocking()    
    * resolves_async()
    """
    from apiens.tools.graphql.resolver.resolver_marker import assert_no_unmarked_resolvers

    assert_no_unmarked_resolvers(app_schema)
