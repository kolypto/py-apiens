import graphql
import ariadne

from apiens.tools.graphql.resolver.resolver_marker import (
    resolves_nonblocking,
    resolves_in_threadpool,
)
from app.expose.graphql.context import ResolveInfo


# Prepare the root Query
Query = ariadne.QueryType()

@Query.field('hello')
@resolves_nonblocking
def resolve_hello(_, info: ResolveInfo):
    return 'Welcome'


@Query.field('unexpected_error')
@resolves_nonblocking
def resolve_unexpected_error(_, info: ResolveInfo):
    raise RuntimeError('Fail')


from app import exc

@Query.field('app_error')
@resolves_nonblocking
def resolve_app_error(_, info: ResolveInfo):
    raise exc.E_API_ACTION(
        error="Something went wrong",
        fixit="Please try again",
    )