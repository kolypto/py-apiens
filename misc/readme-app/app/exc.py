import apiens.error.exc

# Base class for Application Errors
from apiens.error import BaseApplicationError


# region: 400 Client Errors
from apiens.error.exc import (
    E_API_ARGUMENT,
    E_API_ACTION,
    E_CLIENT_VALIDATION,
)

# endregion

# region: 401 Unauthorized

from apiens.error.exc import (
    E_AUTH_REQUIRED,
    F_AUTH_FAILED,
    E_AUTH_CREDENTIALS,
    E_AUTH_USER_DEACTIVATED,
    E_AUTH_USER_PASSWORD_EXPIRED,
)

# endregion

# region: 403 Access Denied

from apiens.error.exc import (
    E_FORBIDDEN,
    E_ROLE_REQUIRED,
    E_PERMISSION_REQUIRED,
)

# endregion

# region: 404 Not Found

from apiens.error.exc import (
    E_NOT_FOUND,
)

# endregion

# region: 409 Conflict

from apiens.error.exc import (
    E_CONFLICT,
    E_CONFLICT_DUPLICATE,
)

# endregion

# region: 500 Server Errors

from apiens.error.exc import (
    F_FAIL,
    F_UNEXPECTED_ERROR,
    F_NOT_IMPLEMENTED,
)

# endregion


def export_error_catalog() -> list[type[BaseApplicationError]]:
    """ Get the list of all defined errors """
    return apiens.error.exc.export_error_catalog(globals=globals())
