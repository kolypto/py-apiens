import inspect
import typing
from typing import Callable, Mapping, Union, Any, Set, FrozenSet

from apiens import di


class Signature:
    """ A function's type signature: the information about its input and output types

    This signature information can be used to generate validation schemas, e.g. attrs or pydantic.
    """

    # Function info: arguments that will be provided by the DI Injector
    provided_arguments: Mapping[str, Union[type, Any]]

    # Function info: arguments that must be provided by the caller
    arguments: Mapping[str, Union[type, Any]]

    # Function info: argument and their default values
    argument_defaults: Mapping[str, Any]

    # Function info: return value type, as read from the function's signature
    return_type: Union[type, Any]

    def __init__(self, func: Callable):
        # Get all annotations.
        # Note that un-annotated parameters will be missing.
        parameter_annotations = typing.get_type_hints(func)
        self.return_type = parameter_annotations.pop('return', Any)

        # Get the names of dependencies that will be provided
        provided_names = get_provided_names(func)

        # Prepare
        self.provided_arguments: dict = {}
        self.arguments: dict = {}
        self.argument_defaults: dict = {}

        # Read every parameter from the function
        for name, parameter in inspect.signature(func).parameters.items():
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
