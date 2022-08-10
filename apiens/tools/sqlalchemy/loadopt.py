""" Loader options """

from sqlalchemy.orm import Load, raiseload, defaultload


def dummyload():
    """ A loadopt that does nothing. Use it when you need a placeholder for an if-else clause.

    Example:
        ssn.query(...).options(
            raiseload() if ... else dummyload()
        )
    """
    return defaultload([])


def loadif(condition: bool, loadopt: Load) -> Load:
    """ Apply `loadopt` only if `condition` is true

    Example:
        ssn.query(...).options(
            loadif('devices' in fields, joinedload(models.User.devices))
        )
    """
    if condition:
        return loadopt
    else:
        return dummyload()


def raiseload_in_testing(is_testing: bool):
    """ Apply raiseload(*), but only in testing

    Use it to make sure that all relationships are explicitly loaded to prevent N+1 problems.

    Example:
         ssn.query(...).options(
            # Load relationships that I'm going to use
            joinedload(...),
            # Fail unit-test the code loads anything else.
            raiseload_in_testing()
         )
    """
    if is_testing:
        return raiseload('*')
    else:
        return dummyload()
