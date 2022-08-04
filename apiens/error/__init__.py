""" Application errors: errors for the end-user.


In the API application, there are two sorts of exceptions:

* API exceptions

    These exceptions are converted into a JSON Error Object and are exposed to the end-user in the API response.
    This means that whenever you raise an API exception, the end-user is meant to see it.

* Python Runtime Exceptions

    Any other exception is seen as "Internal Server Error" and is not exposed to the end-user

This library provides classes for Application Errors.
Everything that's an application error will be returned to the user.
Everything that's not, will be converted into an F_UNEXPECTED_ERROR

Q: Why not just make everything a BaseApplicationError?
A: It will confuse the two error classes: internal errors become external.
    This make it impossible to i.e. change the wording, not to mention that we can't raise unexpected internal errors anymore.
    There must be a distinction between known external errors and unexpected internal errors.
"""

from .base import BaseApplicationError
from . import exc
