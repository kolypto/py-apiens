""" Async tools """

from __future__ import annotations

import functools
from collections import abc
from typing import TypeVar, Any

from starlette.concurrency import run_in_threadpool


def runs_in_threadpool(function: abc.Callable[..., T]) -> abc.Callable[..., abc.Coroutine[Any, Any, T]]:
    """ Decorator to make a function async by executing it in a threadpool.

    How expensive is that? Well, quite cheap: it takes ~ 0.1ms to do so.
    Benchmark: https://gist.github.com/kolypto/2bb6e98aca4cbb6eee42492be880812f

    Example:
        @runs_in_threadpool
        def load_from_database(...):
            ...

        await load_from_database(...)

    Note: this idea is not new. The whole FastAPI framework is built around this idea: every endpoint or dependency
    is either async, or is "converted" to async using this technique. This way, any function can be run within
    the ASGI event loop.
    """
    @functools.wraps(function)
    async def wrapper(*args, **kwargs):
        return await run_in_threadpool(function, *args, **kwargs)
    return wrapper


T = TypeVar("T")
