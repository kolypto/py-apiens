""" A default set of errors for your convenience. Use it if you will. """

import gettext
from typing import Union
from collections import abc
from http import HTTPStatus

from apiens.util.errors import exception_from

from .base import BaseApplicationError


# Optional: pydantic
try:
    import pydantic
except ImportError:
    class pydantic:  # type: ignore[no-redef]
        class ValidationError(Exception):
            pass


# Init translations
# TODO: will this work with lazy translations?
try:
    translation = gettext.translation('apiens')
except FileNotFoundError:
    translation = gettext.NullTranslations()
_ = translation.gettext


# region HTTP 400 Client Errors

# region 400 Bad Request

class F_BAD_API_REQUEST(BaseApplicationError):
    """ Wrong usage of the API due to technical reasons

    Unlike most other errors, this is a technical error that the user cannot fix.
    """
    httpcode = HTTPStatus.BAD_REQUEST.value
    title = _('Bad API request')
    # Fixit message is common to all errors
    fixit = _('The application has made a wrong query request to the server. '
              'Please contact support and describe the issue.')


class E_API_ARGUMENT(BaseApplicationError):
    """ Wrong argument has been provided

    This is a user input error that the user can understand and fix.

    Args:
        name: The name of the failed argument
    """
    httpcode = HTTPStatus.BAD_REQUEST.value
    title = _('Invalid argument')

    def __init__(self, /, error: str, fixit: str = None, *, name: str, **info):
        """
        Args:
            name: The name of the argument whose value was wrong
        """
        super().__init__(error, fixit, name=name, **info)


class E_API_ACTION(BaseApplicationError):
    """ Wrong action has been requested

    This is a user input error that the user can understand and fix.
    """
    httpcode = HTTPStatus.BAD_REQUEST.value
    title = _('Incorrect action')


class E_CLIENT_VALIDATION(BaseApplicationError):
    """ Validation errors on the provided data

    This is a user input error that the user can understand and fix.

    Info:
        model: The Model the error was found with. Example: 'User'
        errors: The list of errors
            Example:
                [ { loc: ['user', 'guitars', 0, 'name'],
                    msg: 'none is not an allowed value',
                    type: 'type_error.none.not_allowed'},
                  ...
                ]
            Fields:
                loc: the path to the failed field
                msg: the error message
                type: the error message type.
    """
    httpcode = HTTPStatus.BAD_REQUEST.value
    title = _('Input validation error')

    def __init__(self, /, error: str = None, fixit: str = None, *, model: str, errors: list[dict], **info):
        """ Iniitialize a validation error

        Args:
            model: Name of the model that has erred
            errors: Errors description: [{ loc: Tuple[str], msg: str, type: str }]
        """
        super().__init__(
            error or _('Invalid input'),
            fixit or _('Please fix the data you have provided and try again'),
            model=model,
            errors=errors,
            **info
        )

    @classmethod
    def from_pydantic_validation_error(cls, pydantic_exception: pydantic.ValidationError, error: str = None, fixit: str = None, **info):
        """ Create from pydantic validation error """
        e = cls(
            error,
            fixit,
            model=pydantic_exception.model.__name__,
            errors=pydantic_exception.errors(),  # [ {loc: Tuple[str], msg: str, type; str} ]
            **info
        )
        return exception_from(e, pydantic_exception)


# region 401 Unauthorized

class E_AUTH_REQUIRED(BaseApplicationError):
    """ The resource requires authentication

    This error means that the user is trying to access a resource without being authenticated.
    They should go to the sign-in place and go through it.
    """
    httpcode = HTTPStatus.UNAUTHORIZED.value
    title = _('Authentication required')


class F_AUTH_FAILED(BaseApplicationError):
    """ Failed to authenticate the user because of some technical errors """
    httpcode = HTTPStatus.UNAUTHORIZED.value
    title = _('Authentication failed')


class E_AUTH_CREDENTIALS(BaseApplicationError):
    """ Failed to authenticate the user because of bad input on their side

    This may mean that the login, the password, or whatever else, was invalid.
    """
    httpcode = HTTPStatus.UNAUTHORIZED.value
    title = _('Invalid authentication credentials')


class E_AUTH_USER_DEACTIVATED(BaseApplicationError):
    """ The user account is disabled and cannot be accessed """
    httpcode = HTTPStatus.UNAUTHORIZED.value
    title = _('User account disabled')


class E_AUTH_USER_PASSWORD_EXPIRED(BaseApplicationError):
    """ User's password has expired """
    httpcode = HTTPStatus.UNAUTHORIZED.value
    title = _('Password expired')

# endregion


# region 403 Forbidden

class E_FORBIDDEN(BaseApplicationError):
    """ Trying to perform an action that is forbidden for this user account.

    This error means that the user is signed in, but the action they requested is not allowed for their account.
    """
    httpcode = HTTPStatus.FORBIDDEN.value
    title = _('Action forbidden for this user account')


class E_ROLE_REQUIRED(BaseApplicationError):
    """ Action forbidden because the user does not not have the required role.

    For instance, this error is reported when a non-admin user tries to perform an admin action.
    """
    httpcode = HTTPStatus.FORBIDDEN.value
    title = _('Role required')

    def __init__(self, /, error: str, fixit: str = None, *, required_roles: abc.Iterable[str], **info):
        """
        Args:
            role: The user account type required to access this resource
        """
        super().__init__(error, fixit, required_roles=required_roles, **info)


class E_PERMISSION_REQUIRED(BaseApplicationError):
    """ Action forbidden because the user lacks a permission

    For instance, this error is reported when a user tries to perform an action that requires a special permission to do so.
    """
    httpcode = HTTPStatus.FORBIDDEN.value
    title = _('Permission required')

    def __init__(self, /, error: str, fixit: str = None, *, required_permissions: abc.Iterable[str], **info):
        """
        Args:
            role: The user account type required to access this resource
        """
        super().__init__(error, fixit, required_permissions=required_permissions, **info)

# endregion


# region 404 Not Found

class E_NOT_FOUND(BaseApplicationError):
    """ Object not found

    Info:
        object: The name of the object that was not found
    """
    httpcode = HTTPStatus.NOT_FOUND.value
    title = _('Not found')

    def __init__(self, /, error: str, fixit: str = None, *, object: Union[type, str], **info):
        """

        Args:
            object: The object that has not been found.
        """
        # Convert class names
        if isinstance(object, type):
            object = object.__name__

        # super()
        super().__init__(error, fixit, object=object, **info)


# endregion


# region 409 Conflict

class E_CONFLICT(BaseApplicationError):
    """ Action conflicts with something else """
    httpcode = HTTPStatus.CONFLICT.value
    title = _('Conflict')


class E_CONFLICT_DUPLICATE(E_CONFLICT):
    """ Duplicate id: attempting to create an object with a duplicate field value

    This happens, for instance, when you are trying to create an account with a duplicate phone number
    while the application does not allow that.
    """
    httpcode = HTTPStatus.CONFLICT.value
    title = _('Duplicate entry')


# endregion


# region HTTP 500 Server Errors

class F_FAIL(BaseApplicationError):
    """ Generic server error """
    httpcode = HTTPStatus.INTERNAL_SERVER_ERROR.value
    title = _('Generic server error')


class F_UNEXPECTED_ERROR(BaseApplicationError):
    """ Unexpected error, probably signifying an error in the code or other sort of malfunction """
    httpcode = HTTPStatus.INTERNAL_SERVER_ERROR.value
    title = _('Generic server error')

    @classmethod
    def from_exception(cls, unexpected_exception: BaseException, error: str = None, fixit: str = None, **info):
        """ Create from another Exception object

        Args:
            error: error message that overrides the default one
            fixit: fixit message that overrides the default one
            **info: extra info
        """
        e = cls(
            error or str(unexpected_exception),
            fixit or _('Please try again in a couple of minutes. '
                       'If the error does not go away, contact support and describe the issue'),
            debug_unexpected_exception=str(unexpected_exception),
            **info
        )
        return exception_from(e, unexpected_exception)


class F_NOT_IMPLEMENTED(BaseApplicationError):
    """ The method is not yet implemented. """
    httpcode = HTTPStatus.NOT_IMPLEMENTED.value
    title = _('Not implemented')

# endregion


def export_error_catalog():
    return [
        value
        for name, value in globals().items()
        if not name.startswith('_')
           and (isinstance(value, type) and issubclass(value, BaseApplicationError))
           and value not in (BaseApplicationError,)
    ]
