import graphql
from collections import abc
from inspect import isawaitable

from apiens.error import exc
from apiens.error.converting.exception import convert_unexpected_error


def unexpected_errors_middleware(exc=exc):
    """ Middleware that converts unxpected Python exceptions into exc.F_UNEXPECTED_ERROR """
    async def middleware(*args, **kwargs):
        return await unexpected_errors_middleware_impl(exc, *args, **kwargs)
    return middleware


async def unexpected_errors_middleware_impl(exc, next: abc.Callable, root, info: graphql.GraphQLResolveInfo, /, **kwargs):
    """ Convert unexpected errors into F_UNEXPECTED_ERROR """
    try:
        res = next(root, info, **kwargs)
        if isawaitable(res):
            res = await res
        return res
    except Exception as e:
        if isinstance(e, graphql.GraphQLError):
            raise e
        else:
            raise convert_unexpected_error(e, exc=exc)
