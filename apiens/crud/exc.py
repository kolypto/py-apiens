""" CRUD exceptions """

from collections import abc
from contextlib import contextmanager

import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.orm
import psycopg2
from jessiql.typing import SAModelOrAlias

from apiens.tools.sqlalchemy.postgres.pg_integrity_error import extract_postgres_unique_violation_column_names


class BaseCrudError(Exception):
    """ Base for CRUD errors """


class NoResultFound(BaseCrudError):
    """ No result found

    Reported by:

    * get()
    * update()
    * delete()

    Cause: cannot find an object by id
    """


class MultipleResultsFound(NoResultFound):
    """ Too many results found """


class BaseFieldValueError(BaseCrudError):
    """ Base for field value erorrs: not null, not unique, foreign key, etc """


class ValueConflict(BaseFieldValueError):
    """ Conflicting value

    Reported by:

    * create()
    * update()

    Cause: unique key violation
    """

    column_names: list[str]

    def __init__(self, column_names: abc.Collection):
        self.column_names = list(column_names)
        column_names_str = ', '.join(self.column_names)
        super().__init__(f'Conflicting value for columns {column_names_str}')



@contextmanager  # and a decorator
def converting_sa_erorrs(*, Model: SAModelOrAlias):
    try:
        yield
    except sa.orm.exc.NoResultFound as e:
        raise NoResultFound('No result found') from e
    except sa.orm.exc.MultipleResultsFound as e:
        raise MultipleResultsFound('Too many results found') from e
    except sa.exc.IntegrityError as e:
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            failed_column_names = extract_postgres_unique_violation_column_names(e, Model.metadata)  # type: ignore[union-attr]
            raise ValueConflict(column_names=failed_column_names) from e
        #elif isinstance(e.orig, psycopg2.errors.NotNullViolation):
        #    breakpoint()  # TODO: NotNull errors? contraint errors?
        else:
            raise
