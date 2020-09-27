""" Hierarchical Injector """

from __future__ import annotations

import functools
import warnings
from contextlib import ExitStack
from threading import RLock
from typing import Optional, Dict, Any, ContextManager, Union, Callable, Iterable, Set

from .const import InjectFlags, MISSING
from .defs import InjectionToken, ProviderFunction, ProviderContextManager
from .defs import Provider, Dependency, Resolvable
from .exc import NoProviderError, ClosedInjectorError
from .markers import resolvable_marker


class Injector:
    """ An injector is a provider for your code's dependencies.

    Modelled after Angular, this Injector keeps track of what your code might need, and initializes it on demand:

        root = di.Injector()
        root.provide(Application, get_application)
        root.provide(DbConnection, get_database_connection)

    It is hierarchical: you may define values on a per-request basis:

        with di.Injector(parent=root) as request:
            request.provide(DbSession, get_database_session)
            request.provide(AuthenticatedUser, get_authenticated_user)

    Then, in your code, you can fetch those values as needed:

        request.get(AuthenticatedUser, default=None)

    Of course, you don't have to be so low-level. Declare your dependencies for a function in advance:

        @di.kwargs(ssn=DbSession)
        def save_user(user, ssn: DbSession):
            ssn.save(user)

    And your `DbSession` will be provided automatically when you use the injector to call it:

        request.invoke(save_user, user)

    Or, to use FastAPI-style dependencies where functions act as injection tokens, do just that:

        @di.kwargs()
        def get_db_session():
            return ...

        @di.kwargs(ssn=get_db_session)
        def save_user(user, ssn: DbSession):
            ssn.save(user)

        ...

        with di.Injector() as root:
            root.provide(get_db_session, get_db_session)
    """
    # TODO: asyncio
    # TODO: with asyncio, implement parallel dependency provision using layered tree traversal
    # TODO: with asyncio, don't use RLock() for the whole process of dependency creation.
    #   Instead, create some sort of promise and quickly release the lock.

    # TODO: perhaps, implement dependency tracking so that you actually can override values from lower levels?
    #   E.g. temporarily switch to another user account.
    #   Can be done this way: when a new provider is registered, and its name overrides something, call provider reset
    #   for the token it provides. This shall go through all the registered instances and invalidate those that depended on it.

    def __init__(self, *, parent: Injector = None):
        # Parent injector
        self._parent: Optional[Injector] = parent or _none_injector

        # Providers: {injection-token => provider}
        self._providers: Dict[InjectionToken, Provider] = {}

        # Already created instances
        self._instances: Dict[InjectionToken, Any] = {}

        # Locking mechanism to prevent multiple threads from accidentally creating multiple instances
        # It is acquired while a provider is creating an instance.
        self._instance_create_lock = RLock()

        # The stack of entered contexts
        self._entered = ExitStack()

        # Whether the injector is done working and will not want to restart
        self._closed: bool = False

    __slots__ = '_providers', '_instances', '_instance_create_lock', '_parent', '_entered', '_closed'

    def provide(self, token: InjectionToken, provider: Union[ProviderFunction, ProviderContextManager, Resolvable]):
        """ Register a provider function for some dependency identified by `token`

        Example:

            @di.signature()
            @contextmanager
            def db_session(connection: DbConnection) -> DbSession:
                session = ...

                try:
                    yield session
                finally:
                    session.close()

            ...

            with di.Injector() as root:
                root.provide(DbSession, db_session)

        Args:
            token: The token that identifies what this provider can provide.
                Usually, it's the class name, and the `provider` is the constructor.
                But it can be anything. For instance, a static string, like 'current_user'.
                Or to have FastAPI-style dependencies, use `provide(authenticated, authenticated)`
                to have a function itself work as a dependency.
            provider: A callable function that returns some value to be used when `token` is requested.
                Also, it can be a ContextManager which does some clean-up upon exit.
        """
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
        """ Register a constant value to be returned for everyone requesting `token`

        Example:
            with di.Injector() as root:
                root.provide_value(AuthenticatedUser, User(email=...))

                ...

                root.get(AuthenticatedUser)  #-> User(email=...)

        Args:
            token: The token that identifies what is provided by this value. Normally a class name.
            value: The value to provide when `token` is requested
        """
        self.register_provider(Provider(token, lambda: value))
        self._register_instance(token, value)
        return self

    def invoke(self, func: Callable, *args, **kwargs) -> Any:
        """ Invoke a function, provide it with dependencies

        Example:

            @di.signature()
            def send_email_to_current_user(current_user: AuthenticatedUser):
                ...

            with di.Injector() as root:
                root.provide_value(AuthenticatedUser, User(email=...))

                root.invoke(send_email_to_current_user)

        Args:
            func: The function to call
            *args: Additional arguments to provide
            **kwargs: Additional keyword arguments to provide
                Note that you can override a dependency here, if it has the same name.

        Raises:
            NoProviderError: no provider found for a dependency
        """
        marker = resolvable_marker.get_from(func)
        if marker is None:
            raise ValueError('A function must be decorated with a @di.signature(), @di.kwargs(), or others')
        else:
            resolvable = marker.resolvable

        return self.resolve_and_invoke(resolvable, *args, **kwargs)

    def partial(self, func: Callable, *args, **kwargs):
        """ Get a partial for `func` with all dependencies provided by this Injector. Useful for passing callbacks.

        Args:
            func: The function to make a partial() of
            *args: Additional arguments to provide
            **kwargs: Additional keyword arguments to provide
        """
        return functools.partial(self.invoke, func, *args, **kwargs)

    def get(self, token: InjectionToken, flags: InjectFlags = InjectFlags.DEFAULT, *, default: Any = MISSING) -> Any:
        """ Obtain an instance from this injector. Keep looking at the parent injector.

        Example:
            with di.Injector() as root:
                root.provide(DbSession, get_database_session)

                ...

                session = root.get(DbSession)

        Args:
            token: The token to find the provider for. Normally a class name.
            flags: How to look the value up.
                For instance, you can limit the search only to this injector (`SELF`), or go directly to the parent.
            default: The default value to provide if no provider is found.
                The default behavior is to fail with `NoProviderError`.

        Raises:
            NoProviderError: no provider found for a dependency
        """
        # If a default is given, become optional.
        # That's a shortcut.
        if default is not MISSING:
            flags |= InjectFlags.OPTIONAL

        # Skip this injector? Go to parent, but remove the `SKIP_SELF` flag
        if flags & InjectFlags.SKIP_SELF:
            return self._parent.get(token, flags ^ InjectFlags.SKIP_SELF, default=default)

        # Get from self
        with self._instance_create_lock:
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
        """ Check if `token` can be provided by this injector or its parents. Respects `flags`

        Args:
            token: The token to find the provider for. Normally a class name.
            flags: How to look the value up.
        """
        return self.get_provider_for(token, flags | InjectFlags.OPTIONAL) is not None

    # region Low-level interface

    def register_provider(self, provider: Provider):
        """ A low-level method to register a provider

        The provider is represented by an instance of `Provider()` that contains the token,
        the function, and its dependency information.
        """
        # Token already used
        assert provider.token not in self._providers, (
            'Provider overrides are not allowed. '
            'If you want an override, create a child injector and provide your overrides there'
        )

        # Register
        self._providers[provider.token] = provider
        return self

    def resolve_and_invoke(self, resolvable: Resolvable, *args, **kwargs) -> Any:
        """ A low-level method to invoke a function after resolving its dependencies

        The function is represented by an instance of `Resolvable()` that contains the function
        and its dependency information.
        """
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
        """ Create an instance and remember it at this injector """
        if self._closed:
            raise ClosedInjectorError('Cannot fetch objects from a closed injector because clean-up procedures have already taken place. '
                                      'Create a new injector, or copy() it to create an identical one.')

        # Get a value from the provider
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
        """ Register a provided instance at this injector """
        # Store the instance by token
        self._instances[token] = instance

        # Done
        return instance

    def _register_context_manager(self, token: InjectionToken, instance_context_manager: ContextManager[Any]) -> Any:
        """ Register a created instance context manager, get the instance, return

        This context manager will do the clean-up when the injector is closed.
        """
        # Get the instance by entering the context manager.
        # Add the entered context manager into the `_entered` ExitStack to make sure __exit__() will be called.
        # This will call all the proper clean-up
        instance = self._entered.enter_context(instance_context_manager)

        # Store the instance by token
        self._register_instance(token, instance)

        # Done
        return instance

    def get_provider_for(self, token: InjectionToken, flags: InjectFlags = InjectFlags.DEFAULT) -> Optional[Provider]:
        """ Find a provider for the `token`

        Args:
            token: The injection token to find a provider for
            flags: Lookup flags
        """
        # Skip this injector? Go to parent, but remove the `SKIP_SELF` flag
        if flags & InjectFlags.SKIP_SELF:
            return self._parent.get_provider_for(token, flags ^ InjectFlags.SKIP_SELF)
        # Do we have a provider for it?
        elif token in self._providers:
            return self._providers[token]
        # If `SELF` prevents us from going upwards, fail immediately
        elif flags & InjectFlags.SELF:
            return _none_injector.get_provider_for(token, flags ^ InjectFlags.SELF)
        # Otherwise, go up the injector tree and try there
        else:
            return self._parent.get_provider_for(token, flags)

    def get_recursive_providers_for(self, token: InjectionToken, flags: InjectFlags = InjectFlags.DEFAULT, _map: dict = None) -> Dict[InjectionToken, Provider]:
        """ Resolve dependencies for `token` recursively and get a map of { token => Provider } for every dependency

        Args:
            token: The initial injection token to find the providers for.
            flags: Lookup flags
        """
        # Prepare the dict for recursion
        if _map is None:
            _map = {}

        # Find the provider and remember it
        provider = self.get_provider_for(token, flags)
        _map[token] = provider

        # Now get providers for every dependency
        all_dependencies: Iterable[Dependency] = [] + list(provider.deps_nopass) + list(provider.deps_kw.values())
        for dependency in all_dependencies:
            # Recurse. Use the same memo `_map` to collect values
            self.get_recursive_providers_for(dependency.token, dependency.flags, _map)

        # Done
        return _map

    # endregion

    def __enter__(self):
        """ Enter the injector """
        if self._closed:
            raise ClosedInjectorError("Cannot restart an Injector that's already done working.")
        return self

    def close(self):
        """ Close the injector and let every provider do the clean-up """
        # Invoke all clean-ups
        self._entered.close()
        # Forget instances
        self._instances.clear()
        # Done
        self._closed = True

    def __exit__(self, *exc):
        self.close()

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
            self._provider_not_found(token)

    def get_provider_for(self, token: InjectionToken, flags: InjectFlags) -> Optional[Provider]:
        if flags & InjectFlags.OPTIONAL:
            return None
        else:
            self._provider_not_found(token)

    def _provider_not_found(self, token: InjectionToken):
        raise NoProviderError(f'Could not find any provider for {token}', token=token)


_none_injector = NoneInjector()
