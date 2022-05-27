from __future__ import annotations

from typing import Optional
from collections import abc


# Predicate type
PredicateFn = abc.Callable[[str], bool]


class exclude:
    """ Filter field names: exclude those listed in `names` """
    def __init__(self, *names: str):
        self._names = frozenset(names)

    def include(self, field_name: str):
        return field_name not in self._names

    __call__ = include


class include_only:
    """ Filter field names: include only those listed in `names` """
    def __init__(self, *names: str):
        self._names = frozenset(names)

    def include(self, field_name: str):
        return field_name in self._names

    __call__ = include


# TODO: more predicates to: ignore types, ignore nullables, customize comparison on other ways, to make the matching more flexible.
#   For instance, some predicate that alters FieldInfo and removes typing information may be used to match fields
#   without considering their typing information. May come in handy with SqlAlchemy


def filter_by_predicate(field_name: str, predicate: Optional[abc.Callable]) -> bool:
    if not predicate:
        return True
    return predicate(field_name)
