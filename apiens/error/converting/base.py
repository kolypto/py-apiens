""" Protocol for exception classes that know how to convert into ApplicationErrors """

import abc
import typing
from typing import Optional

from apiens.error.base import BaseApplicationError


@typing.runtime_checkable
class ConvertsToBaseApiExceptionInterface(typing.Protocol, metaclass=abc.ABCMeta):
    """ Interface: defines how an exception is converted into a BaseApiException

    This protocol defines a method for your exceptions.

    If a Python exception has this method, then it's going to be used to convert it into an ApplicationError.
    See ./exception.py
    """

    # NOTE: typing.Protocol enables duck-typing for this class:
    # that is, any class that has `default_api_error()` is an implicit subclass.
    # That's how `abc.Sized` and other types work.

    @abc.abstractmethod
    def default_api_error(self) -> Optional[BaseApplicationError]:
        """ Convert this error to an API error, if possible

        Returns:
            Exception: The new API error object
            None: When conversion is not possible
        """
        raise NotImplementedError
