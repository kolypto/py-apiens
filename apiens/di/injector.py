""" Hierarchical Injector """

from __future__ import annotations

import functools
import warnings
from contextlib import ExitStack
from typing import Optional, Dict, Any, ContextManager, Union, Callable

from .const import InjectFlags, MISSING
from .defs import Provider, InjectionToken, Resolvable, ProviderFunction, ProviderContextManager
from .exc import NoProviderError, ClosedInjectorError
from .markers import resolvable_marker


class Injector:
    """ An injector is a provider for your code's dependencies.

    Modelled after Angular.
    """

    # TODO: RLock? asyncio lock?
    # TODO: asyncio

    def __init__(self, *, parent: Injector = None):
        # Parent injector
        self._parent: Optional[Injector] = parent or _none_injector

        # Providers: {injection-token => provider}
        self._providers: Dict[InjectionToken, Provider] = {}

        # Already created instances
        self._instances: Dict[InjectionToken, Any] = {}

        # The stack of entered contexts
        self._entered = ExitStack()

        # Whether the injector is done working and will not want to restart
        self._closed: bool = False

    __slots__ = '_providers', '_instances', '_parent', '_entered', '_closed'

    def provide(self, token: InjectionToken, provider: Union[ProviderFunction, ProviderContextManager, Resolvable]):
        """ Register a provider function for some dependency identified by `token` """
        if isinstance(provider, Resolvable):
            resolvable = provider
        else:
            marker = resolvable_marker.get_from(provider)
            if marker is None:
                raise ValueError('Providers must be decorated with a @di.signature(), @di.kwargs(), or others')
            else:
                resolvable = marker.resolvable

        self.register_provider(Provider.from_resolvable(token, resolvable))
        return self

    def provide_value(self, token: InjectionToken, value: Any):
        """ Register a constant value to be returned for everyone requesting `token` """
        self._instances[token] = value
        return self

    def invoke(self, func: Callable, *args, **kwargs) -> Any:
        """ Invoke a function, provide it with dependencies """
        marker = resolvable_marker.get_from(func)
        if marker is None:
            raise ValueError('A function must be decorated with a @di.signature(), @di.kwargs(), or others')
        else:
            resolvable = marker.resolvable

        return self.resolve_and_invoke(resolvable, *args, **kwargs)

    def partial(self, func: Callable, *args, **kwargs):
        """ Get a partial for `func` with all dependencies provided by this Injector. Useful for passing callbacks. """
        return functools.partial(self.invoke, func, *args, **kwargs)

    def get(self, token: InjectionToken, flags: InjectFlags = InjectFlags.DEFAULT, *, default: Any = MISSING) -> Any:
        """ Obtain an instance from this injector. Keep looking at the parent injector. """
        # If a default is given, become optional.
        # That's a shortcut.
        if default is not MISSING:
            flags |= InjectFlags.OPTIONAL

        # Skip this injector? Go to parent, but remove the `SKIP_SELF` flag
        if flags & InjectFlags.SKIP_SELF:
            return self._parent.get(token, flags ^ InjectFlags.SKIP_SELF, default=default)

        # Get from self
        if token in self._instances:
            return self._instances[token]

        # If we have a provider, use it
        if token in self._providers:
            return self._create_instance(self._providers[token])

        # If `SELF` prevents us from going upwards, fail immediately
        if flags & InjectFlags.SELF:
            return _none_injector.get(token, flags ^ InjectFlags.SELF, default=default)
        # Otherwise, go upwards
        else:
            return self._parent.get(token, flags, default=default)

    def has(self, token: InjectionToken, flags: InjectFlags = InjectFlags.DEFAULT) -> bool:
        """ Check if `token` can be provided by this injector or its parents. Respects `flags` """
        # Skip this injector? Go to parent, but remove the `SKIP_SELF` flag
        if flags & InjectFlags.SKIP_SELF:
            return self._parent.has(token, flags ^ InjectFlags.SKIP_SELF)
        # Self only?
        elif flags & InjectFlags.SELF:
            return token in self._providers
        # No skipping -- check self, or go upwards (unless SELF)
        else:
            return token in self._providers or self._parent.has(token, flags)

    # region Low-level interface

    def register_provider(self, provider: Provider):
        """ A low-level method to register a provider """
        # Token already used
        assert provider.token not in self._providers, (
            'Provider overrides are not allowed. '
            'If you want an override, create a child injector and provide your overrides there'
        )

        # Register
        self._providers[provider.token] = provider
        return self

    def resolve_and_invoke(self, resolvable: Resolvable, *args, **kwargs) -> Any:
        """ A low-level method to invoke a function after resolving its dependencies """
        # Create quiet dependencies
        for dependency in resolvable.deps_nopass:
            self.get(dependency.token, dependency.flags, default=dependency.default)

        # Create kwargs dependencies (only those not overridden in kwargs)
        kwargs_dependencies = {
            name: self.get(dependency.token, dependency.flags, default=dependency.default)
            for name, dependency in resolvable.deps_kw.items()
            # Let the caller override dependencies by passing them as kwargs
            if name not in kwargs
        }

        # Invoke the function
        return resolvable.func(*args, **kwargs, **kwargs_dependencies)

    def _create_instance(self, provider: Provider, *args, **kwargs):
        """ Create an instance at this injector """
        return_value = self.resolve_and_invoke(provider, *args, **kwargs)

        # If a context manager, use it to get the value
        if isinstance(return_value, ContextManager):
            instance = self._register_context_manager(provider.token, return_value)
        # If not a context manager, just run it
        else:
            instance = self._register_instance(provider.token, return_value)

        # Done
        return instance

    def _register_instance(self, token: InjectionToken, instance: Any) -> Any:
        """ Register a provided instance """
        if self._closed:
            raise ClosedInjectorError('Cannot fetch objects from a closed injector because clean-up procedures have already taken place. '
                                      'Create a new injector, or copy() it to create an identical one.')

        # Store the instance by token
        self._instances[token] = instance

        # Done
        return instance

    def _register_context_manager(self, token: InjectionToken, instance_context_manager: ContextManager[Any]) -> Any:
        """ Register a created instance context manager, get the instance, return """
        # Get the instance by entering the context manager.
        # Add the entered context manager into the `_entered` ExitStack to make sure __exit__() will be called.
        # This will call all the proper clean-up
        instance = self._entered.enter_context(instance_context_manager)

        # Store the instance by token
        self._register_instance(token, instance)

        # Done
        return instance

    # endregion

    def __enter__(self):
        if self._closed:
            raise ClosedInjectorError("Cannot restart an Injector that's already done working.")
        self._entered.__enter__()
        return self

    def close(self):
        self.__exit__()

    def __exit__(self, *exc):
        # Invoke all clean-ups
        self._entered.close()
        # Forget instances
        self._instances.clear()
        # Done
        self._closed = True

    def __copy__(self):
        """ Reuse by making an injector with identical providers. Instances are not copied! """
        new = type(self)(parent=self._parent)
        new._providers = self._providers.copy()
        return new

    def __del__(self):
        if not self._closed:
            warnings.warn(
                f'Injector {self} has not been close()d. Providers could not do any clean-up, and you may have dangling resources out there. '
                f'Please call close() manually, or use the Injector as a context manager!'
            )


class NoneInjector(Injector):
    """ A fallback injector when no provider is found

    This injector always stays at the root of the injectors' tree and becomes a catch-all fallback:
    it receives get() requests for all dependencies that cannot be otherwise found.

    If a dependency is optional, it returns a default.
    If a dependency is not optional, it fails, because there's no other place to look for.
    """

    def __init__(self, *, parent: Injector = None):
        # Hack: give a value that is truthy but useless. We're not going to use it anyway.
        super().__init__(parent=MISSING)

    def get(self, token: InjectionToken, flags: InjectFlags = InjectFlags.DEFAULT, *, default = MISSING):
        # If optional, use default
        if flags & InjectFlags.OPTIONAL:
            return default
        # If not optional, raise an error
        else:
            raise NoProviderError(f'Could not find any provider for {token}', token=token)

    def has(self, *args, **kwargs) -> bool:
        return False


_none_injector = NoneInjector()
