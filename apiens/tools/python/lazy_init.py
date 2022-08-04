""" Postpone the initialization of an object: so-called "lazy objects" """

from __future__ import annotations

import asyncio
from functools import wraps
import threading
from typing import Optional, TypeVar
from collections import abc


def lazy_init_threadsafe(factory_function: abc.Callable[[], T]) -> abc.Callable[[], T]:
    """ Decorator to lazily initialize an object, in a thread-safe manner'

    This allows to save some time during application start-up.

    Example:

        @lazy_init_threadsafe
        def get_database() -> sa.orm.Session:
            return Session(...)
    """
    # The initialized object
    created_object: Optional[T] = None

    # The lock we use to exclude race conditions
    lock = threading.Lock()

    @wraps(factory_function)
    def wrapper() -> T:
        nonlocal created_object

        # If the object is not initialized, enter the critical section, and initialize it.
        # The double "if" is required to prevent race conditions:
        # * many threads may wait at the outer "if"
        # * one thread will be creating the object inside the locked critical section
        # * all other threads will get unblocked and enter the section as well.
        #   They should not re-initialize the object.
        if created_object is None:
            with lock:
                if created_object is None:
                    created_object = factory_function()

        return created_object

    return wrapper


def lazy_init_async(factory_function: abc.Callable[[], abc.Awaitable[T]]) -> abc.Callable[[], abc.Awaitable[T]]:
    """ Decorator to lazily initialize an object, in non-concurrent async-safe manner """
    # Comments: see lazy_init_threadsafe()
    created_object: Optional[T] = None
    lock = asyncio.Lock()

    @wraps(factory_function)
    async def wrapper() -> T:
        nonlocal created_object

        if created_object is None:
            async with lock:
                if created_object is None:
                    created_object = await factory_function()

        return created_object

    return wrapper


T = TypeVar('T')
