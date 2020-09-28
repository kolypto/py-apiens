from typing import ClassVar, Optional


class BaseApplicationError(Exception):
    """ Base Exception class for your application's exceptions

    It provides rich context both to the user and to the developer.
    Such errors are generally identified by name, which is their class name.

    It has the following special features:

    * Every error has a unique name. The UI will be able to tell one error condition from another and handle it.
      For instance, during signing in, a "E_AUTH_CREDENTIALS" may be handled differently from "E_AUTH_USER_DEACTIVATED".
    * Every error has two text messages:
      The "error" field tells what have gone wrong. It's a negative message.
      The "fixit" field tells what to do to fix it. It's a positive message.
    * Errors contain the "info" field with raw, unformatted, data, associated with the error.
      It is very convenient for the UI to have structured information about what went wrong.
    * Use the `.format()` method to insert the `info` into both the `error` and the `fixit`

    Example:

        class E_NOT_FOUND(BaseApplicationException):
            \""" Object not found \"""
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

    So this is what the UI has:

    * "name" lets them know what went wrong and use a specific handler
    * "error" tells what went wrong
    * "fixit" tells what to do
    * "info" contains structured error information
    * "debug" may contain technical error information
    """

    # Every exception is mapped to an HTTP code
    # https://httpstatuses.com/
    httpcode: ClassVar[int]

    # Generic title of the error class in general
    title: ClassVar[str]

    # Error message: what has gone wrong
    # (message to the user)
    error: str

    # Suggestion: what to do in order to fix it
    # (message to the user)
    fixit: Optional[str]

    # Additional information about the error
    info: dict

    # Debug information about the error.
    # This information is considered to be sensitive and is not reported to the user.
    # It's only available in the server logs.
    # Usage: provide `**info` fields named `debug_*` and they will go here
    debug: dict

    def __init__(self, /, error: str, fixit: str = None, **info):
        """
        Args:
            error: What has gone wrong (negative)
            fixit: What to do in order to fix it (positive)
            info: Additional information.
                Prefix fields with `debug_*` to provide sensitive debugging information
        """
        super().__init__(error)
        self.error = error
        self.fixit = fixit or getattr(self, 'fixit', None)  # get the default from a class-level value, if any
        self.info = info

        # Tell `info` and `debug` apart; remove 'debug_' prefixes
        self.info = {k: v for k, v in info.items() if not k.startswith('debug_')}
        self.debug = {k[6:]: v for k, v in info.items() if k.startswith('debug_')}

        # Special features
        self._response_headers = None

    @classmethod
    def format(cls, /, error: str, fixit: str = None, **info):
        """ Make an exception, format() data into `error` and `fixit` messages

        Example:
            E_NOTFOUND.format(
                _('Cannot find {object}'),
                object=object
            )
        """
        # apply format() to `error` and `fixit`, but only do it after the class' __init__ has gone through it and prepared it.
        e = cls(error, fixit, **info)
        e.error = e.error.format(**e.info)
        if e.fixit:
            e.fixit = e.fixit.format(**e.info)
        return e

    @property
    def name(self):
        """ Name of the exception class """
        return self.__class__.__name__

    def headers(self, headers: dict):
        """ Additional headers to add to the HTTP response """
        self._response_headers = headers
        return self
