""" Create dependencies from existing code """
from __future__ import annotations

from typing import Union, Callable, Container, Optional
from typing import get_type_hints

from apiens.util import decomarker
from .const import MISSING
from .defs import InjectionToken, Dependency, Resolvable


def signature(*include, exclude: Container[str] = None) -> Callable[[Callable], resolvable_marker]:
    """ Read dependencies from the function's signature. Every typed variable becomes a dependency.

    Args:
        *include: Argument names to include. All other arguments will be ignored.
    """
    # Make a decorator that will receive the function and read its signature
    def decorator(func) -> resolvable_marker:
        # Read a resolvable from the function
        resolvable = resolvable_from_function_signature(
            func,
            include_only_names=set(include) if include else None,
            exclude_names=set(exclude) if exclude else None,
        )

        # Start
        return resolvable_marker(resolvable).decorator(func)
    return decorator


def kwargs(**deps_kw: Union[InjectionToken, Dependency]) -> resolvable_marker:
    """ Describe the function's dependencies to be provided as keyword arguments

    Args:
        **deps_kw: {kwarg name => injection-token}, or the complete Dependency object for fine-tuning
    """
    return resolvable_marker(Resolvable(
        func=MISSING,
        deps_kw={
            name: Dependency.ensure_dependency(dependency)
            for name, dependency in deps_kw.items()
        },
    ))


def depends(*deps_nopass) -> resolvable_marker:
    """ List the function's dependencies to be resolved but not passed as arguments

    Args:
        **deps_nopass: injection tokens, or complete Dependency objects for fine-tuning
    """
    return resolvable_marker(Resolvable(
        func=MISSING,
        deps_nopass=[
            Dependency.ensure_dependency(dependency)
            for dependency in deps_nopass
        ]
    ))


class resolvable_marker(decomarker):
    """ A low-level decorator to describe a function's dependencies """

    resolvable: Resolvable

    def __init__(self, resolvable: Resolvable):
        super().__init__()
        self.resolvable = resolvable

        assert self.resolvable.func is MISSING  # the contract is to set it to MISSING because it's not yet known

    def decorator(self, func: Callable):
        # Bind the Resolvable to a function
        self.resolvable.func = func

        # See if the function is already decorated.
        # If so, merge
        marker = self.get_from(func)
        if marker is not None:
            self.resolvable.merge(marker.resolvable)

        # Done
        return super().decorator(func)


def resolvable_from_function_signature(func: Callable,
                                       include_only_names: Optional[Container[str]],
                                       exclude_names: Optional[Container[str]],
                                       ) -> Resolvable:
    """ Read keyword dependencies from the function's signature """
    return Resolvable(
        func=MISSING,
        deps_kw={
            name: Dependency(token=type)
            for name, type in get_type_hints(func).items()
            if name != 'return' and
               (include_only_names is None or name in include_only_names) and
               (exclude_names is None or name not in exclude_names)
        }
    )
