""" Tools for fields and resolvers """

from __future__ import annotations

import ariadne
import functools
from typing import TypeVar
from collections import abc


def also_resolves(object: ariadne.ObjectType, field: str, **kwargs):
    """ Decorator for resolvers with partial arguments """
    def wrapper(resolver: ariadne.types.Resolver) -> ariadne.types.Resolver:
        object.set_field(field, partial_resolver(resolver, **kwargs))
        return resolver
    return wrapper


def partial_resolver(resolver: FT, *args, **kwargs) -> FT:
    """ partial() for resolvers

    You cannot use functools.partial() because it does not use update_wrapper() and as a result
    loses custom attributes that are essential to our implementation.

    This version is transparent to additional attributes.
    """
    f: FT = functools.partial(resolver, *args, **kwargs)  # type: ignore[assignment]
    functools.update_wrapper(f, resolver)
    return f



T = TypeVar("T")
FT = TypeVar('FT', bound=abc.Callable)
