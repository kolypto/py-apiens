import pytest

from apiens.tools.python.lazy_init import lazy_init_threadsafe, lazy_init_async


def test_lazy_init_sync():
    """ Test @lazy_init_threadsafe """
    called_times = 0

    @lazy_init_threadsafe
    def create_object() -> dict:
        nonlocal called_times
        called_times += 1
        return {}

    # The same object is returned every time.
    # Because it's mutable, we can use it as storage
    o = create_object()
    o['a'] = 1
    o = create_object()
    o['b'] = 2
    assert o == {'a': 1, 'b': 2}

    # Initialized only once
    assert called_times == 1


@pytest.mark.asyncio
async def test_lazy_init_async():
    """ Test lazy_init_asyncio """

    called_times = 0

    @lazy_init_async
    async def create_object() -> dict:
        nonlocal called_times
        called_times += 1
        return {}

    # The same object is returned every time.
    # Because it's mutable, we can use it as storage
    o = await create_object()
    o['a'] = 1
    o = await create_object()
    o['b'] = 2
    assert o == {'a': 1, 'b': 2}

    # Initialized only once
    assert called_times == 1
