from __future__ import annotations

import functools
import inspect
from typing import Hashable, Callable, Union, ClassVar, Optional, Any

from apiens.util import decomarker
from .errors import BaseApplicationError
from .signature import Signature
from .util.documented_function import DocumentedFunction


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

    # Operation's documentation
    doc: DocumentedFunction

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
        self.doc = DocumentedFunction(None, {}, None, {}, None)

        # Parse the docstring as soon as it becomes available
        self._parse_docstring = True

        # Custom extra info
        self.info: dict = info

    def decorator(self, func: Union[Callable, type]):
        # `id` defaults to function name
        if self.operation_id is None:
            self.operation_id = func.__name__

        # Read function signature into information
        self.signature = self.SIGNATURE_CLS(func)

        # Parse the function's docstring
        if self._parse_docstring:
            try:
                self.doc.parse_from_function_docstring(func)
            except Exception as e:
                raise ValueError(f'Error while parsing docstring of {func}') from e

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

    def check_operation_documentation(self, *, fully_documented: bool = True):
        """ Check that all documentations make sense """
        # Check that every documented parameter is actually a known parameter
        documented_parameter_names = set(self.doc.parameters)
        function_parameter_names = set(inspect.signature(self.func).parameters)
        mistaken_parameter_names = documented_parameter_names - function_parameter_names

        # Error message
        s = 's' if len(mistaken_parameter_names) > 1 else ''
        assert not mistaken_parameter_names, (
            f'Unknown parameter name{s} documented for the function: {mistaken_parameter_names}. '
            f'This is probably a typo. Please document this function properly: {self.func}.'
        )

        # Fully documented?
        if fully_documented:
            self._assert_is_fully_documented()

            # Also, wrap the function to check what sort of errors does it throw
            self.func = self.wrap_func_check_thrown_errors_are_documented(self.func)

    def _assert_is_fully_documented(self):
        """ Check that the function is fully documented. Used in projects by documenting freaks.

        It will test that:

        * The function is documented
        * Every parameter and the return value are both annotated and documented

        Args:
            as_class_method: Validate it as a class method (i.e. ignoring the first parameter)

        Raises:
            AssertionError if anything failed.
        """
        errors = []

        # Class? Drop a few checks.
        is_class = inspect.isclass(self.func)

        # Check that the function itself is documented
        if not self.doc.function:
            errors.append(f"The function is not documented. Please add a docstring.")

        # Check that its return value is documented
        if not is_class and not self.doc.result:
            errors.append(f"The return value is not documented. Please add the 'Returns' section.")

        # Get its signature
        signature = operation.get_from(self.func).signature

        # Check that its return value is typed
        if not is_class and signature.return_type is Any:
            errors.append(f"The return type is unknown. Please provide a return type annotation.")

        # Check every parameter's type and documentation
        for name, type_ in signature.arguments.items():
            if type_ is Any:
                errors.append(f"Parameter {name!r} type is unknown. "
                              f"Please put a type annotation on it.")
            if name not in self.doc.parameters:
                errors.append(f"Parameter {name!r} is not documented. "
                              f"Please add an 'Args' section for it")

        # We can't validate errors.
        # But error_validator_decorator() can make a wrapper that will validate them at runtime :)

        # Report errors
        if errors:
            errors_str = ''.join(f'\t* {error}\n' for error in errors)
            raise AssertionError(
                f'Function is not fully documented: {self.func}\n'
                f'Errors: \n'
                f'{errors_str}'
            )

    def wrap_func_check_thrown_errors_are_documented(self, func: Callable) -> Callable:
        """ A wrapper that will make sure that every error raised by the function is documented """
        # Wrap the function
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Call the function
            try:
                return func(*args, **kwargs)
            # Catch errors, see if they're documented
            except BaseApplicationError as e:
                if type(e) not in self.doc.errors:
                    raise AssertionError(
                        f"Function {func} raised an undocumented error: {e.name!r}. "
                        f"Please document the error in a `Raises:` docstring section"
                    ) from e
                raise

        # Done
        return wrapper
