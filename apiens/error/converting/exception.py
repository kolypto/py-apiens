from contextlib import contextmanager
from typing import Union


from apiens.error import exc 
from .base import ConvertsToBaseApiExceptionInterface


@contextmanager
def converting_unexpected_errors(*, exc=exc):
    """ Convert unexpected Python exceptions into a human-friendly F_UNEXPECTED_ERROR Application Error
    
    This function is a catch-all: every expected error should be an instance of `exc.BaseApplicationError`.
    Every other Python error is considered to be unexpected and wrapped into an `exc.F_UNEXPECTED_ERROR`.

    If the exception defines the `default_api_error()` method, the method is used to convert it into a different error (!)

    Raises:
        exc.F_UNEXPECTED_ERROR: for unexpected Python errors
    """
    try:
        yield
    except Exception as e:
        raise convert_unexpected_error(e, exc=exc)


def convert_unexpected_error(error: Union[Exception, exc.BaseApplicationError], *, exc=exc) -> exc.BaseApplicationError:
    """ Given an exception, convert it into a `F_UNEXPECTED_ERROR` if it's not a BaseApplicationError already """
    # `exc.BaseApplicationError` remain as they are
    if isinstance(error, exc.BaseApplicationError):
        return error

    # Exception defines a way to convert into API error
    if isinstance(error, ConvertsToBaseApiExceptionInterface):
        new_error = error.default_api_error()
        if new_error is not None:
            return new_error

    # All other errors are unexpected
    return exc.F_UNEXPECTED_ERROR.from_exception(error)