""" DI errors """

from apiens.di.defs import InjectionToken, Provider


class BaseInjectorError(Exception):
    """ Base for injector errors """


class NoProviderError(BaseInjectorError):
    """ No provider has been found for an injection token """

    def __init__(self, message: str, token: InjectionToken):
        super().__init__(message)
        self.token = token


class ClosedInjectorError(BaseInjectorError):
    """ An attempt to operate on an Injector that has already been closed """
