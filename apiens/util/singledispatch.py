from __future__ import annotations
from collections import abc

import types
from typing import Any, TypeVar
from functools import update_wrapper


def singledispatch_value(func: T) -> T:
    """ @singledispatch for literal values

    Credit for reference implementation: @vdmit11
    """
    registry: dict[Any, Any] = {}

    def dispatch(value: Any):
        try:
            return registry[value]
        except KeyError:
            return func

    def register(value: Any, func=None):
        if value is None:
            return lambda f: register(value, f)
        registry[value] = func
        return func

    def wrapper(*args, **kw):
        return dispatch(args[0])(*args, **kw)

    wrapper.register = register  # type: ignore[attr-defined]
    wrapper.dispatch = dispatch  # type: ignore[attr-defined]
    wrapper.registry = types.MappingProxyType(registry)  # type: ignore[attr-defined]
    update_wrapper(wrapper, func)
    return wrapper  # type: ignore[return-value]


T = TypeVar('T', bound=abc.Callable[..., Any])
