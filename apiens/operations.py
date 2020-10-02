from __future__ import annotations

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

    # The name of the field used for its return value.
    return_name: Optional[str]

    # Operation function's signature: argument types, defaults, etc
    signature: SIGNATURE_CLS

    # Extra, custom, information about the operation
    info: dict

    def __init__(self,
                 operation_id: Optional[Union[str, Hashable]] = None,
                 return_name: Optional[str] = None,
                 **info):
        """

        Args:
            id: Operation id. Can be a string name, or a tuple of multiple names to mimic a tree-like structure.
                When `None`, is taken from the function's name
            return_name: Name of the field used for its return value.
                When `None`, no field is added, and the function's return value is used as is.
            **info: Additional information to associate with this operation. Arbitrary.
        """
        super().__init__()
        self.operation_id = operation_id
        self.return_name = return_name

        # Custom extra info
        self.info: dict = info

    def decorator(self, func: Callable):
        # `id` defaults to function name
        if self.operation_id is None:
            self.operation_id = func.__name__

        # Read function signature into information
        self.signature = self.SIGNATURE_CLS(func)

        # Done
        return super().decorator(func)
