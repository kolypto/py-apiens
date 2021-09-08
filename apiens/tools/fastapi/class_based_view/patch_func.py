""" Tools for patching Python functions' arguments """

import types
import inspect
import functools

from typing import TypeVar, Any, Optional
from collections import abc

ClassmethodT = TypeVar('ClassmethodT', bound=classmethod)
MethodT = TypeVar('MethodT', bound=abc.Callable)


def set_parameter_default(func: MethodT, param: str, default: Any) -> MethodT:
    """ Set a default value for one function parameter; make all other defaults equal to `...`

    This function is normally used to set a default value for `self` or `cls`:
    weird magic that makes FastAPI treat the argument as a dependency.
    All other arguments become keyword-only, because otherwise, Python won't let this function exist.

    Example:
        set_parameter_default(Cls.method, 'self', Depends(Cls))
    """
    patch = patch_function_keyword_arguments(func)
    try:
        parameter: Optional[inspect.Parameter] = None
        while parameter := patch.send(parameter):  # type: ignore[arg-type]
            # For `name`, replace the default
            if parameter.name == param:
                parameter = parameter.replace(default=default)
    except StopIteration:
        pass

    return func


def patch_function_keyword_arguments(func: abc.Callable) -> abc.Generator[inspect.Parameter, inspect.Parameter, abc.Callable]:
    """ A generator for patching a function's parameters.

    NOTE: it makes every argument a keyword-only argument.

    Example:
        patch = patch_function_parameters(endpoint)
        try:
            parameter = None
            while True:
                parameter = parameter.replace(...)
                # Replace this parameter and get the next one
                parameter = patch.send(parameter)
        except StopIteration:
            pass  # Done
    """
    # Get the signature
    sig = inspect.signature(func)

    # Make a new parameter list
    new_parameters = []
    for name, parameter in sig.parameters.items():
        # yield it, and get it back
        parameter = yield parameter

        # make all arguments keyword-only.
        # this makes sure that if a default value has been added to any argument, the Python function will still make sense.
        if parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            # Make them keyword-only
            parameter = parameter.replace(kind=inspect.Parameter.KEYWORD_ONLY)

        # prepare to replace it
        new_parameters.append(parameter)

    # Replace the signature
    setattr(func, '__signature__', sig.replace(parameters=new_parameters))
    return func


def copy_func(f, name=None):
    """ Make a copy of a Python function

    Python copy() does not copy functions. This implementation does it.
    """
    g = types.FunctionType(f.__code__, f.__globals__, name=name or f.__name__, argdefs=f.__defaults__, closure=f.__closure__)
    g = functools.update_wrapper(g, f)  # updates __dict__ as well
    return g
