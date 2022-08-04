""" Exception handling tools """

from typing import TypeVar


ExceptionT = TypeVar('ExceptionT', bound=BaseException)


def exception_from(new_exception: ExceptionT, cause_exception: BaseException) -> ExceptionT:
    """ Link the two exceptions to show that one is the result of another

    It works exactly like `raise new_exception from cause_exception`, but without raising it.
    """
    new_exception.with_traceback(cause_exception.__traceback__)
    new_exception.__cause__ = cause_exception
    return new_exception
