import logging
import sys
from contextlib import AbstractContextManager


class NamedExitStack:
    """ Exit stack with named context managers

    Why? Because the standard contextlib.ExitStack actually loses errors. In case of multiple clean-up errors,
    it only raises the first error, and all other errors go unreported.
    This is unacceptable in our case because we want to log them!

    With this context manager, you can exit them one by one and catch every error.

    Example:
        try:
            stack = NamedExitStack()
            stack.enter_context('db', ...)
            stack.enter_context('redis', ...)
        except:
            stack.emergency_exit_all_context_and_log(logger)

        ...

        for name in ['db', 'redis']:
            try:
                stack.exit_context('db')
            except:
                logger.exception(...)

        assert stack.properly_closed()
    """
    _stack: dict[str, AbstractContextManager]

    def __init__(self):
        self._stack = {}

    __slots__ = '_stack'

    def enter_context(self, name: str, cm: AbstractContextManager):
        """ Enter a context, give it a name """
        self._stack[name] = cm
        return cm.__enter__()

    def has_context(self, name: str):
        """ Check if a specific context has been entered and is still open """
        return name in self._stack

    def exit_context(self, name: str):
        """ Exit the context specified by name

        No exception is raised if the context isn't known.
        This approach makes it possible to exit contexts without checking if they have even been entered
        """
        # Get the context manager
        cm = self._stack.pop(name, None)

        # Exit it, if found
        if cm:
            cm.__exit__(*sys.exc_info())

    @property
    def properly_closed(self):
        """ Is the stack closed? That is, are there no remaining contexts to close? """
        return not bool(self._stack)

    def emergency_exit_all_context_and_log(self, logger: logging.Logger) -> list[Exception]:
        """ Exit all context managers; don't raise errors, but log them and return them """
        errors = []
        while self._stack:
            name, cm = self._stack.popitem()
            try:
                cm.__exit__(*sys.exc_info())
            except Exception as e:
                logger.exception('Clean-up error')
                errors.append(e)
        return errors
