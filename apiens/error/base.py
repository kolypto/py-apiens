from typing import ClassVar, Optional

from .error_object.python import ErrorObject


class BaseApplicationError(Exception):
    """ Base Exception class for your application's API exceptions

    These exceptions are meant to be displayed to the end-user and are therefore expected API behaviors.

    Features:
    * Message for both user and developer.
      `error`: negative message: what has gone wrong
      `fixit`: positive message: what to do to fix it (user-friendly)
    * `name`: unique name for every error.
      The UI can use it to tell one error from another and handle it.
    * `info`: raw, structured, context data.
    * Use `.format()` to record `info` data and also use it for message formatting

    Example:

        class E_NOT_FOUND(BaseApplicationError):
            httpcode = 404
            title = _('Not found')

        raise E_NOT_FOUND.format(
            _('Could not find the {object} by {field}'),
            _('Please make sure you have entered a valid email and try again'),
            object=_('User'),
            field=_('email'),
            email='kolypto@gmail.com',
        )

    Such an error should be reported to the API user as a JSON object:

        {
            "name": 'E_NOT_FOUND',
            "title": 'Not found',
            "error": 'Could not find the User by email',
            "fixit": 'Please make sure you have entered a valid email and try again',
            "info": {
                "object": 'User',
                "field": 'email',
                "email": 'kolypto@gmail.com',
            },
            "debug": {},
        }
    """

    # Every exception is mapped to an HTTP code
    # https://httpstatuses.com/
    httpcode: ClassVar[int]

    # Generic title of the error class in general
    title: ClassVar[str]

    # Message: what has gone wrong (message to the user)
    error: str

    # Message: how to fix it (message to the user)
    fixit: Optional[str]

    # Structured context info for the error
    info: dict

    # Debug information about the error.
    # Sensitive. Is not reported to the user. Only available in the server logs.
    # Usage: any **info field that starts with "debug_*" gets here
    debug: dict

    def __init__(self, error: str, fixit: str = None, **info):
        """ Report a failure

        Args:
            error: What has gone wrong (negative message)
            fixit: How to fix it (positive message)
            info: Additional information.
                Use "debug_*" to provide sensitive debugging information
        """
        super().__init__(error)

        self.error = error
        self.fixit = fixit or getattr(self, 'fixit', None)  # get the default from a class-level value, if any

        # Tell `info` and `debug` apart; remove 'debug_' prefixes
        self.info = {k: v for k, v in info.items() if not k.startswith('debug_')}
        self.debug = {k[6:]: v for k, v in info.items() if k.startswith('debug_')}

        # Special features
        self._response_headers: Optional[dict] = None

    @classmethod
    def format(cls, error: str, fixit: str = None, **info):
        """ Exception with placeholders from **info

        Example:
            raise E_NOTFOUND.format(
                _('Cannot find {object}'),
                object=object
            )
        """
        return cls(
            error.format(**info),
            fixit and fixit.format(**info),
            **info
        )

    @property
    def name(self):
        """ Name of the exception class """
        return self.__class__.__name__

    def headers(self, headers: dict):
        """ Additional headers to add to the HTTP response

        This is only supported if your exception-handling code uses it.
        """
        self._response_headers = headers
        return self

    def dict(self, include_debug_info: bool) -> ErrorObject:
        """ Convert to a JSON `ErrorObject`

        Args:
            include_debug_info: Include sensitive debug info?
                DON'T USE IN PRODUCTION!
        """
        return dict(
            name=self.name,
            title=str(self.title),
            httpcode=self.httpcode,
            error=str(self.error),
            fixit=str(self.fixit),
            info=self.info,
            debug=self.debug if include_debug_info else None,
        )
