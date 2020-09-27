""" DI errors """

from apiens.di.defs import InjectionToken, Provider


class BaseInjectorError(Exception):
    """ Base for injector errors """


class NoProviderError(BaseInjectorError):
    """ No provider has been found for an injection token

    This error is raised when a dependency is required, but no provider has been found.
    Make sure you've used the correct `token`, and defined a provider for it.
    """

    def __init__(self, message: str, token: InjectionToken):
        super().__init__(message)
        self.token = token


class ClosedInjectorError(BaseInjectorError):
    """ An attempt to operate on an Injector that has already been closed """
