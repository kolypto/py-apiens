""" SqlAlchemy Session tools related to saving things """

from collections import abc

import sqlalchemy as sa
import sqlalchemy.orm

from .expire import commit_no_expire


def db_flush(session: sa.orm.Session, *instances):
    """ Flush a number of instances to the database """
    session.add_all(instances)
    session.flush()


def db_save(session: sa.orm.Session, *instances):
    """ Commit a number of instances to the database

    Main feature: objects won't be "expired" after they're saved.
    """
    session.add_all(instances)
    commit_no_expire(session)

    # Done
    return instances


def db_save_refresh(session: sa.orm.Session, *instances):
    """ Commit a number of instances, then refresh() them from the database

    This makes sure that no object is expired, and also that they are up to date with the DB state.
    """
    # Save
    session.add_all(instances)
    session.commit()

    # Refresh
    instances = refresh_instances(session, instances)

    # Done
    return instances


def session_safe_commit(session: sa.orm.Session):
    """ Commit a session

    This function is useful when you don't know where the session came from.
    It may be in a non-active state, e.g. after an error. In this case, it cannot be committed.
    """
    try:
        # commit(), but only if the session is active
        if session.is_active:
            session.commit()
        # If a session is not active, some query has probably failed. Roll back.
        else:
            session.rollback()
    except:
        session.rollback()
        raise


def refresh_instances(session: sa.orm.Session, instances: abc.Iterable[object], loadopt: abc.Mapping[type, list] = {}):
    """ Refresh multiple instances at once

    This is much faster than doing `ssn.refresh()` in a loop.

    Consider using no_expire_on_commit(): in some cases, it may serve your purposes better

    Args:
        session: The session to use for querying
        instances: The list of instances to refresh
    """
    for mapper, states in _group_instances_by_mapper(instances).items():
        _refresh_multiple_instance_states(session, mapper, states, loadopt=loadopt.get(mapper.class_, ())).all()


def _refresh_multiple_instance_states(session: sa.orm.Session, mapper: sa.orm.mapper, states: list[sa.orm.state.InstanceState], loadopt=()) -> sa.orm.Query:
    """ Create a query to refresh multiple instance states at once

    Args:
        session: The session to use
        mapper: The mapper to load the instances for
        states: The list of instances to update

    Returns:
        a Query that will do it
    """
    # Collect instance identities
    identities = (state.identity for state in states)

    # Build a condition using primary keys
    pk_columns: tuple[sa.Column, ...] = mapper.primary_key
    condition = sa.tuple_(*pk_columns).in_(identities)

    # Execute one bulk query to load all instances at once.
    # This query will Session.merge() them into the Session, and thus, a bulk refresh is achieved.
    return session.query(mapper).options(*loadopt).filter(condition)


def _group_instances_by_mapper(instances: abc.Iterable[object]) -> dict[sa.orm.Mapper, list[sa.orm.state.InstanceState]]:
    """ Walk the list of instances and group them by Mapper """
    mappers_and_states: dict[sa.orm.Mapper, list[sa.orm.state.InstanceState]] = {}

    for instance in instances:
        # Get state, mapper
        state: sa.orm.state.InstanceState = sa.orm.base.instance_state(instance)
        mapper: sa.orm.Mapper = state.mapper

        # Group them
        if mapper not in mappers_and_states:
            mappers_and_states[mapper] = []
        mappers_and_states[mapper].append(state)

    return mappers_and_states
