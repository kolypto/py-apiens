from __future__ import annotations

import inspect

from typing import Hashable, Callable, Union, ClassVar, Optional

from apiens.util import decomarker
from .signature import Signature


class operation(decomarker):
    """ Decorator for functions that implement business-logic

    Example:

        from apiens import operation, di

        @operation()
        @di.kwargs(current_user=authenticated_user)
        def who_am_i(current_user: User):
            return current_user.login

    Example:

        @operation(id='user')
        @di.kwargs(ssn=Session)
        class UserLogic:
            def __init__(self, ssn: Session):
                self.ssn = ssn

            @operation()
            @di.signature()
            def list(self):
                return ssn.query(...)

            @operation()
            @di.signature()
            def create(self, user: schemas.User):
                ...

            @operation()
            @di.signature()
            def delete(self, id: int):
                ...
    """
    # The signature class to use
    SIGNATURE_CLS: ClassVar[type] = Signature

    # A unique name of this operation.
    # It will be used to call it as a function
    operation_id: Union[str, Hashable]

    # Operation function's signature: argument types, defaults, etc
    signature: SIGNATURE_CLS

    # Extra, custom, information about the operation
    info: dict

    def __init__(self,
                 operation_id: Optional[Union[str, Hashable]] = None,
                 **info):
        """

        Args:
            id: Operation id. Can be a string name, or a tuple of multiple names to mimic a tree-like structure.
                When `None`, is taken from the function's name3
            **info: Additional information to associate with this operation. Arbitrary.
        """
        super().__init__()
        self.operation_id = operation_id

        # Custom extra info
        self.info: dict = info

    def decorator(self, func: Callable):
        # `id` defaults to function name
        if self.operation_id is None:
            self.operation_id = func.__name__

        # Read function signature into information
        self.signature = self.SIGNATURE_CLS(func)

        # If we've decorated a class, go through every method and tell it about it
        if inspect.isclass(func):
            for method_operation in self.all_decorated_from(func, inherited=True):
                # Remove the first argument.
                # TODO: remove hardcoded "self" and support any name. Support @classmethod. Support @staticmethod.
                del method_operation.signature.arguments['self']

        # Done
        return super().decorator(func)

    def pluck_kwargs_from(self, kwargs: dict):
        """ Given a dict of many parameters, choose the ones that this operation needs

        This method is used with class-based views, where the input contains parameters for both
        the __init__() method of the class and the operation method.
        """
        return {
            name: kwargs[name]
            for name in self.signature.arguments
            if name in kwargs  # because some defaults might not be provided
        }
