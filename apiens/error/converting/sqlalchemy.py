from typing import Optional
from contextlib import contextmanager

import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.orm.exc
import psycopg2

from apiens.tools.sqlalchemy.postgres.pg_integrity_error import extract_postgres_unique_violation_column_names
from apiens.util.exception import exception_from
from apiens.error import exc 
from .exception import convert_unexpected_error


@contextmanager  # and a decorator
def converting_sa_errors(*, Model: type, exc=exc, _=exc._):
    """ Convert common SqlAlchemy errors into human-friendly Application Errors

    SqlAlchemy raises errors that are cryptic to the end-user.
    Convert them into something readable.

    Raises:
        exc.E_NOT_FOUND: when not found
        exc.E_NOT_FOUND: when multiple found
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
            _('Cannot find {object}'),
            _('Make sure you have entered a correct URL with a valid id'),
            object=Model.__name__,
        )
        return exception_from(e, error)

    # MultipleResultsFound
    if isinstance(error, sa.orm.exc.MultipleResultsFound):
        e = exc.E_NOT_FOUND.format(
            _('Several {object}s found'),
            _('Make sure you have entered a correct URL with a valid id'),
            object=Model.__name__,
        )
        return exception_from(e, error)

    # IntegrityError
    if isinstance(error, sa.exc.IntegrityError):
        # Check: unique violation errors
        if isinstance(error.orig, psycopg2.errors.UniqueViolation):
            # NOTE: this function will only find the column name if your unique indexes have explicit names!!
            failed_column_names = extract_postgres_unique_violation_column_names(error, Model.metadata)  # type: ignore[attr-defined]

            if failed_column_names:
                e = exc.E_CONFLICT_DUPLICATE(
                    # We use a custom format() because we want comma-separated column names
                    _('Conflicting {object} object found for {failed_columns}').format(
                        failed_columns=', '.join(failed_column_names),
                        object=Model.__name__,
                    ),
                    _('Please choose something unique for {failed_columns}'),
                    failed_columns=failed_column_names,
                    object=Model.__name__,
                )
            else:
                e = exc.E_CONFLICT_DUPLICATE.format(
                    _('Conflicting {object} object found'),
                    _('Please choose something unique'),
                    object=Model.__name__,
                    failed_columns=None,
                )

            return exception_from(e, error)
        # Reraise as a server error
        else:
            raise convert_unexpected_error(error, exc=exc)

    # Otherwise
    return None
