""" CRUD exceptions """

from collections import abc
from contextlib import contextmanager
from typing import Union

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

    def __init__(self, msg: str, *, model: str):
        super().__init__(msg)
        self.model = model


class MultipleResultsFound(NoResultFound):
    """ Too many results found """


class ValueConflict(BaseCrudError):
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
def converting_sa_errors(*, Model: SAModelOrAlias):
    """ Convert SqlAlchemy errors into apiens.crud errors 
    
    This means that unlike other SA errors, CRUD errors would be converted into proper classes.
    """
    try:
        yield
    except sa.orm.exc.NoResultFound as e:
        model_name = sa.orm.class_mapper(Model).class_.__name__
        raise NoResultFound('No result found', model=model_name) from e
    except sa.orm.exc.MultipleResultsFound as e:
        model_name = sa.orm.class_mapper(Model).class_.__name__
        raise MultipleResultsFound('Too many results found', model=model_name) from e
    except sa.exc.IntegrityError as e:
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            failed_column_names = extract_postgres_unique_violation_column_names(e, Model.metadata)  # type: ignore[union-attr]
            raise ValueConflict(column_names=failed_column_names) from e
        #elif isinstance(e.orig, psycopg2.errors.NotNullViolation):
        #    breakpoint()  # TODO: NotNull errors? contraint errors?
        else:
            raise
