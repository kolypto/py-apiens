from __future__ import annotations
from collections import abc

import types
from typing import Any, Union, TypeVar
from functools import update_wrapper

import sqlalchemy as sa
import sqlalchemy.orm.util



def singledispatch_model_type(func: T) -> T:
    """ @singledispatch for SqlAlchemy types, which can be aliased

    Credit for reference implementation: @vdmit11
    """
    registry: dict[type, Any] = {}

    def dispatch(Model: Union[type, sa.orm.util.AliasedClass]):
        # unalias_class()
        BaseModel = sa.orm.class_mapper(Model).class_

        # Lookup
        if BaseModel in registry:
            return registry[BaseModel]
        else:
            return func

    def register(Model: type, func=None):
        if func is None:
            return lambda f: register(Model, f)
        registry[Model] = func
        return func

    def wrapper(*args, **kw):
        return dispatch(args[0])(*args, **kw)

    registry[object] = func
    wrapper.register = register  # type: ignore[attr-defined]
    wrapper.dispatch = dispatch  # type: ignore[attr-defined]
    wrapper.registry = types.MappingProxyType(registry)  # type: ignore[attr-defined]
    update_wrapper(wrapper, func)
    return wrapper  # type: ignore[return-value]


T = TypeVar('T', bound=abc.Callable[..., Any])
