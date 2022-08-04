""" An ExitStack that allows you to de-initialize objects sequentially and catch errors """

from __future__ import annotations

import sys
import logging
from typing import TypeVar
from typing import ContextManager, AsyncContextManager


class _NamedExitStackBase:
    """ Features common to both sync and async stacks """

    def __init__(self):
        self._stack = {}

    def has_context(self, name: str) -> bool:
        """ Check if the context has been entered and is still open """
        return name in self._stack

    @property
    def properly_closed(self):
        """ Is the stack closed? That is, are there no remaining contexts to close? """
        return not bool(self._stack)


class NamedExitStack(_NamedExitStackBase):
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
    _stack: dict[str, ContextManager]
    __slots__ = '_stack'

    def enter_context(self, name: str, cm: ContextManager[T]) -> T:
        """ Enter a context, give it a name """
        self._stack[name] = cm
        return cm.__enter__()

    def exit_context(self, name: str):
        """ Exit the context specified by name, if exists

        If the context has not been entered, no error is raised:
        this behavior allows to exit contexts without checking whether they've been entered.
        """
        # Get the context manager
        cm = self._stack.pop(name, None)

        # Exit it, if found
        if cm is not None:
            cm.__exit__(*sys.exc_info())

    def emergency_exit_all_context_and_log(self, logger: logging.Logger) -> list[Exception]:
        """ Exit all context managers; don't raise errors, but log them and return them """
        errors = []
        while self._stack:
            name, cm = self._stack.popitem()
            try:
                cm.__exit__(*sys.exc_info())
            except Exception as e:
                logger.exception(f'Clean-up error for {name!r}')
                errors.append(e)
        return errors


class NamedAsyncExitStack(_NamedExitStackBase):
    """ Exit stack for async named context managers """

    _stack: dict[str, AsyncContextManager]
    __slots__ = '_stack'

    async def enter_async_context(self, name: str, cm: AsyncContextManager[T]) -> T:
        """ Enter a context, give it a name """
        self._stack[name] = cm
        return await cm.__aenter__()

    async def exit_async_context(self, name: str):
        """ Exit the context specified by name, if exists """
        cm = self._stack.pop(name, None)
        if cm is not None:
            await cm.__aexit__(*sys.exc_info())

    async def emergency_exit_all_async_contexts_and_log(self, logger: logging.Logger) -> list[Exception]:
        errors = []
        while self._stack:
            name, cm = self._stack.popitem()
            try:
                await cm.__aexit__(*sys.exc_info())
            except Exception as e:
                logger.exception(f'Clean-up error for {name!r}')
                errors.append(e)
        return errors


T = TypeVar('T')
