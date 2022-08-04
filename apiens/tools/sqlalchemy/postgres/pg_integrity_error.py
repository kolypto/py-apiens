""" Extract information from Postgres errors """

from typing import Optional, Union
from functools import lru_cache

import sqlalchemy as sa
import sqlalchemy.exc
import sqlalchemy.ext.declarative

import psycopg2 as pg
import psycopg2.errors
import psycopg2.extensions


# TODO: handle other errors?
# Class 23 — Integrity Constraint Violation
# 23000	    integrity_constraint_violation  IntegrityConstraintViolation
# 23001	    restrict_violation              RestrictViolation
# 23502	    not_null_violation              NotNullViolation
# 23503	    foreign_key_violation           ForeignKeyViolation
# 23505	    unique_violation                UniqueViolation
# 23514	    check_violation                 CheckViolation
# 23P01	    exclusion_violation             ExclusionViolation


def extract_postgres_unique_violation_column_names(err: sa.exc.IntegrityError, metadata: sa.MetaData) -> frozenset[str]:
    """ Having an IntegrityError with a unique index violation, extract the list of offending column names """
    columns = extract_postgres_unique_violation_columns(err, metadata)
    return frozenset(col.key for col in columns if col.key is not None)


def extract_postgres_unique_violation_columns(err: sa.exc.IntegrityError, metadata: sa.MetaData) -> tuple[sa.Column, ...]:
    """ Having an IntegrityError with a unique index violation, extract the list of offending columns

    Postgres errors are unreadable to users: they report the index name, but the user wants to know
    which column contains a non-unique value. This function returns these columns.

    Note: in order for this function to work, all your indexes need to be explicitly named!
    If an index does not have a name, this function won't be able to recognize it.

    Example:

        try:
            ssn.flush()
        except sa.exc.IntegrityError as e:
            columns = extract_postgres_unique_violation_columns(e, Base.metadata)

    Args:
        err: The IntegrityError exception

    Returns:
        The list of columns involved in a unique index violation. Typically just one.
        Empty list, when index cannot be resolved to columns.

    Raises:
        ValueError: not a unique index violation
    """
    assert isinstance(err.orig, pg.errors.UniqueViolation)

    # Get diagnostic info
    diag: psycopg2.extensions.Diagnostics = err.orig.diag

    # No table info? Quit.
    if diag.table_name is None:
        return ()

    # Find the schema item
    # Whatever this `schema_item` object is, it has a `.columns` property
    table: sa.Table = metadata.tables[diag.table_name]
    try:
        schema_item = get_unique_constraint_or_index_by_name(table, diag.constraint_name)
    except KeyError:
        return ()

    # List those columns
    return tuple(schema_item.columns)


# Whatever this object is, it has the `.columns` property
ConstraintOrIndex = Union[sa.UniqueConstraint, sa.Index]  # SchemaItem, ColumnCollectionMixin


@lru_cache()
def get_unique_constraint_or_index_by_name(table: sa.Table, name: str) -> ConstraintOrIndex:
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


def _get_unique_constraint_by_name(table: sa.Table, constraint_name: str) -> Optional[sa.UniqueConstraint]:
    """ Given a constraint name, get the SA object """
    for constraint in table.constraints:
        if isinstance(constraint, sa.UniqueConstraint) and constraint.name == constraint_name:
            return constraint
    return None


def _get_unique_index_by_name(table: sa.Table, index_name: str) -> Optional[sa.Index]:
    """ Given a unique index name, get the SA object """
    for index in table.indexes:
        if index.unique and index.name == index_name:
            return index
    return None
