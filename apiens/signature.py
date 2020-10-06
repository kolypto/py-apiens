import inspect
import typing
from typing import Callable, Mapping, Union, Any, FrozenSet, Literal

from apiens import di
from dataclasses import dataclass


@dataclass
class Signature:
    """ A function's type signature: the information about its input and output types

    This signature information can be used to generate validation schemas, e.g. attrs or pydantic.
    """

    # Arguments that will be provided by the DI Injector
    # Mapping: { name => type }
    provided_arguments: Mapping[str, Union[type, Literal[Any]]]

    # Arguments that must be provided by the caller
    # Mapping: { name => type }
    arguments: Mapping[str, Union[type, Literal[Any]]]

    # Argument and their default values
    # Mapping: { name => default value }
    argument_defaults: Mapping[str, Any]

    # Return value type, as read from the function's signature
    # Value: type
    return_type: Union[type, Literal[Any]]

    def __init__(self, func: Callable):
        # Get the names of dependencies that will be provided
        provided_names = get_provided_names(func)

        # If it's a class, go to its constructor instead.
        # We only do this after `get_provided_names()` to make sure
        # we support both decorated classes and decorated constructors
        if inspect.isclass(func):
            func = func.__init__
            provided_names |= get_provided_names(func)

        # Get all annotations.
        # Note that un-annotated parameters will be missing.
        parameter_annotations = typing.get_type_hints(func)
        self.return_type = parameter_annotations.pop('return', Any)

        # Prepare
        self.provided_arguments: dict = {}
        self.arguments: dict = {}
        self.argument_defaults: dict = {}

        # Read every parameter from the function
        for name, parameter in inspect.signature(func).parameters.items():
            # Skip variadic arguments
            if parameter.kind in (parameter.VAR_KEYWORD, parameter.VAR_POSITIONAL):
                continue

            # Get the type. Default to `Any`
            type_ = parameter_annotations.get(parameter.name, Any)

            # Where does this argument go? `provided_arguments` or `arguments`?
            # An argument from the DI Injector
            if name in provided_names:
                self.provided_arguments[name] = type_
            # A user-provided argument
            else:
                self.arguments[name] = type_

                # Defaults
                if parameter.default is not parameter.empty:
                    self.argument_defaults[name] = parameter.default


def get_provided_names(func: Callable) -> FrozenSet[str]:
    """ Get names of the arguments that will be provided by the DI Injector """
    di_marker = di.resolvable_marker.get_from(func)
    if di_marker:
        return di_marker.resolvable.provided_names()
    else:
        return frozenset()
