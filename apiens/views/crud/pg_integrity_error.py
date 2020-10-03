import psycopg2
import psycopg2.errors
import psycopg2.extensions
from functools import lru_cache
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.sql.schema import UniqueConstraint, Table, Column, Index
from typing import Optional, Union, Tuple


# TODO: handle other errors?
# Class 23 — Integrity Constraint Violation
# 23000	    integrity_constraint_violation  IntegrityConstraintViolation
# 23001	    restrict_violation              RestrictViolation
# 23502	    not_null_violation              NotNullViolation
# 23503	    foreign_key_violation           ForeignKeyViolation
# 23505	    unique_violation                UniqueViolation
# 23514	    check_violation                 CheckViolation
# 23P01	    exclusion_violation             ExclusionViolation


def extract_postgres_unique_violation_columns(err: sa_exc.IntegrityError, Base: DeclarativeMeta) -> Tuple[Column]:
    """ Having an IntegrityError with a unique index violation, extract the list of offending columns

    Args:
        err: The IntegrityError exception

    Returns:
        The list of columns involved in a unique index violation. Typically just one.

    Raises:
        ValueError: not a unique index violation
    """
    assert isinstance(err.orig, psycopg2.errors.UniqueViolation)

    # Get diagnostic info
    diag: psycopg2.extensions.Diagnostics = err.orig.diag

    # Find the schema item
    # Whatever this `schema_item` object is, it has a `.columns` property
    table: Table = Base.metadata.tables[diag.table_name]
    schema_item = get_unique_constraint_or_index_by_name(table, diag.constraint_name)

    # List those columns
    return tuple(schema_item.columns)


# Whatever this object is, it has the `.columns` property
SchemaItemWithColumnsProperty = Union[UniqueConstraint, Index]  # SchemaItem, ColumnCollectionMixin


@lru_cache()
def get_unique_constraint_or_index_by_name(table: Table, name: str) -> SchemaItemWithColumnsProperty:
    """ Find a UniqueConstraint or a unique Index by name

    When an IntegrityError is raised, it does not report a column name; it reports a constraint name, like this:

        (psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint "uq__users__login"

    The postgres error object, however, contains the constraint name:

        diag: psycopg2.extensions.Diagnostics = err.orig.diag
        diag.constraint_name

    This function takes this name, and tries to find a corresponding SQLALchemy schema element,
    either UniqueConstraint or Index.

    Usage:

        schema_item = get_unique_constraint_or_index_by_name(models.User.__table__, 'uq__users__login')
        schema_item.columns

    Raises:
        KeyError: no constraint or index is found
    """
    # Try to find a constraint
    constraint = _get_unique_constraint_by_name(table, name)
    if constraint:
        return constraint

    # Try to find a unique index
    index = _get_unique_index_by_name(table, name)
    if index:
        return index

    # Not found
    raise KeyError(name)


def _get_unique_constraint_by_name(table: Table, constraint_name: str) -> Optional[UniqueConstraint]:
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint) and constraint.name == constraint_name:
            return constraint
    return None


def _get_unique_index_by_name(table: Table, index_name: str) -> Optional[Index]:
    for index in table.indexes:
        if index.unique and index.name == index_name:
            return index
    return None
