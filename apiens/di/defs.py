""" Definitions """

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Collection, ContextManager, Any, Union

from .const import InjectionToken, InjectFlags, MISSING


@dataclass
class Resolvable:
    """ A function with dependency information

    The idea is simple: once dependencies are resolved, call `func()` and give it dependencies as `**kwargs`
    """
    __slots__ = 'func', 'deps_kw', 'deps_nopass'

    def __init__(self,
                 func: Callable,
                 deps_kw: Mapping[str, Dependency] = MISSING,
                 deps_nopass: Collection[Dependency] = MISSING):
        self.func = func
        self.deps_kw = deps_kw if deps_kw is not MISSING else {}
        self.deps_nopass = deps_nopass if deps_nopass is not MISSING else []

    # The function to call when the dependencies are resolved
    func: Callable

    # Dependencies to be passed as keyword arguments
    deps_kw: Mapping[str, Dependency]

    # Dependencies to be used without passing as arguments
    deps_nopass: Collection[Dependency]

    def merge(self, another: Resolvable):
        """ Merge another resolvable into this one. This function helps when a function is decorated multiple times. """
        self.deps_kw.update(another.deps_kw)
        self.deps_nopass.extend(another.deps_nopass)
        return self


ProviderFunction = Callable[..., Any]
ProviderContextManager = Callable[..., ContextManager[Any]]


@dataclass
class Provider(Resolvable):
    """ A provider for instances that can be obtained from an injector

    Example:
        Provider(
            token=Session,
            provider=get_session,
            deps_kw={
                'db_connection': Provider(...)
            }
        )
    """
    __slots__ = 'token',

    def __init__(self,
                 token: InjectionToken,
                 func: Callable,
                 deps_kw: Mapping[str, Dependency] = MISSING,
                 deps_nopass: Collection[Dependency] = MISSING):
        super().__init__(func=func, deps_kw=deps_kw, deps_nopass=deps_nopass)
        self.token = token

    # Injection token: the dependency it provides
    token: InjectionToken

    # Provider function: either
    # 1. a callable that returns the instance to be provided ; or
    # 2. A context manager, whose __enter__() value is the instance, and __exit__() cleans up when the injector exits
    func: Union[ProviderFunction, ProviderContextManager]

    @classmethod
    def from_resolvable(cls, token: InjectionToken, resolvable: Resolvable):
        """ Provider() from Resolvable() """
        return cls(
            token=token,
            func=resolvable.func,
            deps_kw=resolvable.deps_kw,
            deps_nopass=resolvable.deps_nopass,
        )


@dataclass
class Dependency:
    __slots__ = 'token', 'flags', 'default'

    def __init__(self,
                 token: InjectionToken,
                 flags: InjectFlags = InjectFlags.DEFAULT,
                 default: Any = MISSING):
        self.token = token
        self.flags = flags
        self.default = default

    # Injection token: what is required
    token: InjectionToken

    # Injector flags for dependency resolution
    flags: InjectFlags

    # Default value
    default: Any

    @classmethod
    def ensure_dependency(cls, arg: Union[InjectionToken, Dependency]) -> Dependency:
        """ Wrap injection tokens with Dependency() if necessary """
        if isinstance(arg, cls):
            return arg
        else:
            return cls(token=arg)
