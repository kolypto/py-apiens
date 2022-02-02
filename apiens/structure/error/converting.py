from contextlib import contextmanager
from typing import Union, Optional

import abc
import typing

import apiens.crud.exc
import jessiql
import psycopg2
import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.orm.exc

from apiens.tools.sqlalchemy.pg_integrity_error import extract_postgres_unique_violation_column_names
from . import exc
from .base import BaseApplicationError
from apiens.tools.errors import exception_from


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


@contextmanager
def converting_unexpected_errors(*, exc=exc):
    """ Convert unexpected exceptions to F_UNEXPECTED_ERROR

    This function is a catch-all: every expected error should be an instance of `exc.BaseApplicationError`.
    Every other Python error is considered to be unexpected and wrapped into an `exc.F_UNEXPECTED_ERROR`

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
        if new_error:
            return new_error

    # All other errors are unexpected
    return exc.F_UNEXPECTED_ERROR.from_exception(error)


@contextmanager  # and a decorator
def converting_sa_errors(*, Model: type, exc=exc, _=exc._):
    """ Handle common SqlAlchemy errors in API operations

    SqlAlchemy raises errors that are cryptic to the end-user.
    Convert them into something readable:

    Raises:
        exc.E_NOT_FOUND: when one() fails
        exc.E_CONFLICT_DUPLICATE: for unique index violations
    """
    try:
        yield
    except sa.exc.SQLAlchemyError as e:
        new_error = convert_sa_error(e, Model=Model, exc=exc, _=_)
        raise new_error or e


def convert_sa_error(error: Exception, *, Model: type, exc=exc, _=exc._) -> Optional[exc.BaseApplicationError]:
    """ Given a SqlAlchemy exception, convert it to `exc` API exceptions """
    # NoResultFound
    if isinstance(error, sa.orm.exc.NoResultFound):
        e = exc.E_NOT_FOUND.format(
            _('Cannot find {object} by id'),
            _('Make sure you have entered a correct URL with a valid id'),
            object=Model.__name__,
        )
        return exception_from(e, error)

    # MultipleResultsFound
    if isinstance(error, sa.orm.exc.MultipleResultsFound):
        e = exc.E_NOT_FOUND.format(
            _('Too many {object}s found'),
            _('Make sure you have entered a correct URL with a valid id'),
        )
        return exception_from(e, error)

    # IntegrityError
    if isinstance(error, sa.exc.IntegrityError):
        # Check: unique violation errors
        if isinstance(error.orig, psycopg2.errors.UniqueViolation):
            failed_column_names = extract_postgres_unique_violation_column_names(error, Model.metadata)  # type: ignore[attr-defined]
            e = exc.E_CONFLICT_DUPLICATE(
                _('Conflicting object found for {failed_columns}').format(failed_columns=', '.join(failed_column_names)),
                _('Provide a unique value for {failed_columns}'),
                failed_columns=failed_column_names,
            )
            return exception_from(e, error)
        # Reraise as a server error
        else:
            raise convert_unexpected_error(error, exc=exc)

    # Otherwise
    return None


@contextmanager  # and a decorator
def converting_jessiql_errors(*, exc=exc, _=exc._):
    """ Handle JessiQL errors

    Convert JessiQL errors into readable application errors

    Raises:
        exc.E_API_ARGUMENT: query object failures: invalid columns and relationships
        exc.F_BAD_API_REQUEST: other query errors, e.g. wrong use of cursors
    """
    try:
        yield
    except jessiql.exc.BaseJessiqlException as e:
        new_error = convert_jessiql_error(e, exc=exc, _=exc._)
        raise new_error or e


def convert_jessiql_error(error: jessiql.exc.BaseJessiqlException, *, exc=exc, _=exc._):
    """ Given a JessiQL exception, convert it into a `exc` API exception """
    if isinstance(error, jessiql.exc.QueryObjectError):
        e = exc.E_API_ARGUMENT(
            _('Query Object error: {message}').format(message=str(error)),
            _('Report this issue to the developer in order to have this query fixed'),
            name='query',
        )
        return exception_from(e, error)

    elif isinstance(error, jessiql.exc.InvalidColumnError):
        e = exc.E_API_ARGUMENT(
            _('Invalid column "{column_name}" for "{model}" specified in {where}'),
            _('Report this issue to the developer in order to have this query fixed'),
            name=error.where,
        ).format(
            column_name=error.column_name,
            model=error.model,
            where=error.where,
        )
        return exception_from(e, error)
    elif isinstance(error, jessiql.exc.InvalidRelationError):
        e = exc.E_API_ARGUMENT(
            _('Invalid relation "{column_name}" for "{model}" specified in {where}'),
            _('Report this issue to the developer in order to have this query fixed'),
            name=error.where,
        ).format(
            column_name=error.column_name,
            model=error.model,
            where=error.where,
        )
        return exception_from(e, error)
    elif isinstance(error, jessiql.exc.RuntimeQueryError):
        e = exc.F_BAD_API_REQUEST(
            _('JessiQL failed: {message}'),
            _('Report this issue to the developer in order to have this query fixed'),
        ).format(message=str(error))
        return exception_from(e, error)


@contextmanager  # and a decorator
def converting_apiens_error(*, exc=exc, _=exc._):
    """ Handle apiens errors

    Convert our errors into readable application errors
    """
    try:
        yield
    except apiens.crud.exc.BaseCrudError as e:
        new_error = convert_apiens_error(e, exc=exc, _=_)
        raise new_error or e


def convert_apiens_error(error: apiens.crud.exc.BaseCrudError, *, exc=exc, _=exc._):
    if isinstance(error, apiens.crud.exc.NoResultFound):
        e = exc.E_NOT_FOUND(
            _('Object not found'),
            _('Please check if your URL and input are correct')
        )
        return exception_from(e, error)
    elif isinstance(error, apiens.crud.exc.ValueConflict):
        e = exc.E_CONFLICT_DUPLICATE(
            _('Conflicting object found for {failed_columns}').format(failed_columns=', '.join(error.column_names)),
            _('Provide a unique value for {failed_columns}'),
            failed_columns=error.column_names,
        )
        return exception_from(e, error)
