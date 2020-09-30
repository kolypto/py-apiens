""" A default set of errors for your convenience. Use it if you will. """

from typing import Iterable, List, Union


# Init translations
# TODO: will this work with lazy translations?
import gettext
try:
    translation = gettext.translation('apiens')
except FileNotFoundError:
    translation = gettext.NullTranslations()
_ = translation.gettext


from .errors import BaseApplicationError


HTTP_400_BAD_REQUEST = 400
HTTP_401_UNAUTHORIZED = 401
HTTP_403_FORBIDDEN = 403
HTTP_404_NOT_FOUND = 404
HTTP_405_METHOD_NOT_ALLOWED = 405
HTTP_409_CONFLICT = 409
HTTP_500_INTERNAL_SERVER_ERROR = 500
HTTP_501_NOT_IMPLEMENTED = 501


# region HTTP 400 Client Errors

# region 400 Bad Request

class E_BAD_API_REQUEST(BaseApplicationError):
    """ Wrong usage of the API due to technical reasons

    Unlike most other errors, this is a technical error that the user cannot fix.
    """
    httpcode = HTTP_400_BAD_REQUEST
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
    httpcode = HTTP_400_BAD_REQUEST
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
    httpcode = HTTP_400_BAD_REQUEST
    title = _('Incorrect action')


class E_CLIENT_VALIDATION(BaseApplicationError):
    """ Validation errors on the provided data

    This is a user input error that the user can understand and fix.

    Info:
        model: The Model the error was found with. Example: 'User'
        errors: The list of errors
    """
    httpcode = HTTP_400_BAD_REQUEST
    title = _('Input validation error')

    def __init__(self, /, error: str = None, fixit: str = None, *, model: str, errors: List[dict], **info):
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
    def from_pydantic_validation_error(cls, pydantic_exception: 'pydantic.ValidationError', error: str = None, fixit: str = None, **info):
        """ Create from Pydantic validation error """
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
    httpcode = HTTP_401_UNAUTHORIZED
    title = _('Authentication required')


class E_AUTH_CREDENTIALS(BaseApplicationError):
    """ Failed to authenticate the user because of bad input on their side

    This may mean that the login, the password, or whatever else, was invalid.
    """
    httpcode = HTTP_401_UNAUTHORIZED
    title = _('Invalid authentication credentials')


class E_AUTH_USER_DEACTIVATED(BaseApplicationError):
    """ The user account is disabled and cannot be accessed """
    httpcode = HTTP_401_UNAUTHORIZED
    title = _('User account disabled')

# endregion


# region 403 Forbidden

class E_FORBIDDEN(BaseApplicationError):
    """ Trying to perform an action that is forbidden for this user account.

    This error means that the user is signed in, but the action they requested is not allowed for their account.
    """
    httpcode = HTTP_403_FORBIDDEN
    title = _('Action forbidden for this user account')


class E_ROLE_REQUIRED(BaseApplicationError):
    """ Action forbidden because the user does not not have the required role.

    For instance, this error is reported when a non-admin user tries to perform an admin action.
    """
    httpcode = HTTP_403_FORBIDDEN
    title = _('Role required')

    def __init__(self, /, error: str, fixit: str = None, *, required_roles: Iterable[str], **info):
        """
        Args:
            role: The user account type required to access this resource
        """
        super().__init__(error, fixit, required_roles=required_roles, **info)


class E_PERMISSION_REQUIRED(BaseApplicationError):
    """ Action forbidden because the user lacks a permission

    For instance, this error is reported when a user tries to perform an action that requires a special permission to do so.
    """
    httpcode = HTTP_403_FORBIDDEN
    title = _('Permission required')

    def __init__(self, /, error: str, fixit: str = None, *, required_permissions: Iterable[str], **info):
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
    httpcode = HTTP_404_NOT_FOUND
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
    httpcode = HTTP_409_CONFLICT
    title = _('Conflict')


class E_CONFLICT_DUPLICATE(E_CONFLICT):
    """ Duplicate id: attempting to create an object with a duplicate field value

    This happens, for instance, when you are trying to create an account with a duplicate phone number
    while the application does not allow that.
    """
    httpcode = HTTP_409_CONFLICT
    title = _('Duplicate entry')


# endregion


# region HTTP 500 Server Errors

class E_FAIL(BaseApplicationError):
    """ Generic server error """
    httpcode = HTTP_500_INTERNAL_SERVER_ERROR
    title = _('Generic server error')


class E_UNEXPECTED_ERROR(BaseApplicationError):
    """ Unexpected error, probably signifying an error in the code or other sort of malfunction """
    httpcode = HTTP_500_INTERNAL_SERVER_ERROR
    title = _('Generic server error')

    @classmethod
    def from_exception(cls, unexpected_exception: BaseException, error: str = None, fixit: str = None, **info):
        """

        Args:
            unexpected_exception: The error that the application did not expect.
        """
        e = cls(
            error or str(unexpected_exception),
            fixit or _('Please try again in a couple of minutes. '
                       'If the error does not go away, contact support and describe the issue'),
            # Adding a `debug` field.
            # It will only be included in non-production mode
            debug_unexpected_exception=str(unexpected_exception),
            **info
        )

        # Link
        return exception_from(e, unexpected_exception)


class E_NOT_IMPLEMENTED(BaseApplicationError):
    """ The method is not yet implemented. """
    httpcode = HTTP_501_NOT_IMPLEMENTED
    title = _('Not implemented')

# endregion


def exception_from(new_exception: BaseException, cause_exception: BaseException):
    """ Link one exception to another to show causal relationship """
    new_exception.with_traceback(cause_exception.__traceback__)
    new_exception.__cause__ = cause_exception
    return new_exception
