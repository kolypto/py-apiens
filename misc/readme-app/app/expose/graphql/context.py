from __future__ import annotations

import graphql 


# Override ResolveInfo type annotations
class ResolveInfo(graphql.GraphQLResolveInfo):
    context: RequestContext


class RequestContext:
    """ Out custom context """
