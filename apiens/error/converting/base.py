import abc
import typing
from typing import Optional

from apiens.error.base import BaseApplicationError


@typing.runtime_checkable
class ConvertsToBaseApiExceptionInterface(typing.Protocol, metaclass=abc.ABCMeta):
    """ Interface: defines how an exception is converted into a BaseApiException

    In the API application, there are two sorts of exceptions:

    * API exceptions

        These exceptions are converted into a JSON Error Object and are exposed to the end-user in the API response.
        This means that whenever you raise an API exception, the end-user is meant to see it.

    * Python Runtime Exceptions

        Any other exception is seen as "Internal Server Error" and is not exposed to the end-user

    You may, however, want to expose some Python exceptions to the end user: in this case, we normally reraise them.
    This approach, however, takes some additional efforts to implement.

    For this reason, this duck-typing interface exists ("typing.Protocol"):
    any exception that has a `default_api_error()` method will be converted to an API error using it.

    Q: Why not just make everything a BaseApplicationError?
    A: It will confuse the two error classes: internal errors become external.
       This make it impossible to i.e. change the wording, not to mention that we can't raise unexpected internal errors anymore.
       There must be a distinction between known external errors and unexpected internal errors.
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
