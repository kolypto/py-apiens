from collections import abc
from typing import TypeVar, Any
from functools import partial

T = TypeVar('T')


class SuccessfulMixin:
    """ A mixin that allows any class to enter the "optimistic mode": expect the following action to be successful.

    It will run assertSuccessfulResult() against the result of every method's call and raise nice errors if anything went wrong.

    Example:

        test_client.successful().get(...)

    Motto: "If you trust before you try, you may repent before you die". So we check in the background.

    Example:
        class AppTestClient(TestClient, SuccessfulMixin):
            def assertSuccessfulResult(self, method_name: str, return_value: Response):
                json_response = return_value.json()
                assert 'error' not in json_response, json_response['error']
    """

    def successful(self: T) -> T:
        """ Assert that the following method will result in a success """
        return _SuccessfulWrapper(self)  # type: ignore[return-value,arg-type]

    def assertSuccessfulResult(self, method_name: str, return_value: Any):
        """ Implement: check that `result` was successful

        Args:
            method_name: name of the method called
            return_value: return value of the method
        Raises:
            AssertionError
        """
        raise NotImplementedError


class _SuccessfulWrapper:
    """ The wrapper object used by the successful() mode

    It intercepts the return value of every called method and runs assertSuccessfulResult() to check whether it was successful.
    Raises errors if not.
    """
    __slots__ = ('__object',)

    def __init__(self, object: SuccessfulMixin):
        self.__object = object

    # Method invocation
    def __getattr__(self, method_name: str):
        method = getattr(self.__object, method_name)
        return partial(self.__call_method, method_name, method)

    def __call_method(self, method_name: str, method: abc.Callable, *args, **kwargs):
        """ Call a method of the parent object, get its return value, and check it """
        # Exec the method
        return_value = method(*args, **kwargs)

        # Process result
        self.__object.assertSuccessfulResult(method_name, return_value)
        return return_value
