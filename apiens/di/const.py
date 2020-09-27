""" DI constants """

from enum import Flag, auto
from typing import NewType, Hashable

# Injection token: the value by which dependency providers are found.
# Normally, a class (associated with its constructor callable)
InjectionToken = NewType('InjectionToken', Hashable)


class InjectFlags(Flag):
    """ Dependency resolution flags """
    # Search for a provider starting from this one, and upwards, towards the root injector
    DEFAULT = auto()

    # Only check the current injector for providers. Fail if not found.
    SELF = auto()

    # Do not check the current injector; start one level higher
    SKIP_SELF = auto()

    # Do not raise errors if no provider is found; return `None`
    OPTIONAL = auto()


# Indication that a value is not provided
MISSING = object()
