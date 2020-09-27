""" Lighweight dependency injection """

from .injector import Injector
from .markers import kwargs, depends, signature

from .const import InjectFlags
from .defs import InjectionToken, Resolvable, Provider, Dependency, Dependency
from .exc import BaseInjectorError, NoProviderError, ClosedInjectorError

# Shortcuts
DEFAULT = InjectFlags.DEFAULT
SELF = InjectFlags.SELF
SKIP_SELF = InjectFlags.SKIP_SELF
OPTIONAL = InjectFlags.OPTIONAL