from contextlib import contextmanager
from typing import Union

import mongosql
import psycopg2
import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.orm.exc

from apiens.tools.sqlalchemy import extract_postgres_unique_violation_column_names
from apiens.structure.error import exc


@contextmanager
def converting_unexpected_errors(, *, exc=exc):
    """ Convert unexpected exceptions to F_UNEXPECTED_ERROR

    This function is a catch-all: every expected error should be an instance of `exc.BaseApplicationError`.
    Every other Python error is considered to be unexpected and wrapped into an `exc.F_UNEXPECTED_ERROR`

    Raises:
        exc.F_UNEXPECTED_ERROR: for unexpected Python errors
    """
    try:
        yield
    except Exception as e:
        raise convert_unexpected_errors(e, exc=exc)


def convert_unexpected_errors(error: Union[Exception, exc.BaseApplicationError], *, exc=exc):
    """ Given an exception, convert it into a `F_UNEXPECTED_ERROR` if it's not a BaseApplicationError already """
    # `exc.BaseApplicationError` remain as they are
    if isinstance(error, exc.BaseApplicationError):
        return error

    # All other errors are unexpected
    return exc.F_UNEXPECTED_ERROR.from_exception(error)


@contextmanager  # and a decorator
def converting_sa_errors(Model: type, *, exc=exc, _=exc._):
    """ Handle common SqlAlchemy errors in API operations

    SqlAlchemy raises errors that are cryptic to the end-user.
    Convert them into something readable:

    Raises:
        exc.E_NOT_FOUND: when one() fails
        exc.E_CONFLICT_DUPLICATE: for unique index violations
    """
    try:
        yield
    # `NoResultFound` is raised by: get(), update(), delete()
    # It normally means that there was no object for the provided primary key
    except sa.orm.exc.NoResultFound:
        raise exc.E_NOT_FOUND.format(
            _('Cannot find {object} by id'),
            _('Make sure you have entered a correct URL with a valid id'),
            object=Model.__name__,
        )
    # `IntegrityError` is raised by: create(), update()
    # It normally means that saving failed because of a constraint or a unique index violation
    except sa.exc.IntegrityError as e:
        # Check: unique violation errors
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            failed_column_names = extract_postgres_unique_violation_column_names(e, Model.Base.metadata)
            raise exc.E_CONFLICT_DUPLICATE(
                _('Duplicate entry for {failed_columns}').format(failed_columns=', '.join(failed_column_names)),
                _('Provide a unique value for {failed_columns}'),
                failed_columns=failed_column_names,
            )
        # Reraise as a server error
        else:
            raise convert_unexpected_errors(e, exc=exc)


@contextmanager  # and a decorator
def converting_mongosql_errors(*, exc=exc, _=exc._):
    """ Handle MongoSql errors

    Convert MongoSQL errors into readable application errors

    Raises:
        exc.F_BAD_API_REQUEST: query object failures: invalid columns and relationships
        exc.F_BAD_API_REQUEST: other mongosql errors
    """
    try:
        yield
    # `InvalidColumnError` and `InvalidRelationError` when a typo is made in the MongoSql QueryObject
    except (mongosql.exc.InvalidColumnError, mongosql.exc.InvalidRelationError) as e:
        raise exc.F_BAD_API_REQUEST.format(
            _('QueryObject error: {error_message}'),
            error_message=str(e),
            # Fields common to InvalidColumnError and InvalidRelationError
            query_field=e.where,
            column_name=e.column_name,
            model_name=e.model,
        ) from e
    except mongosql.exc.BaseMongoSqlException as e:
        raise exc.F_BAD_API_REQUEST.format(
            _('MongoSql query error: {error_message}'),
            error_message=str(e),
        ) from e
