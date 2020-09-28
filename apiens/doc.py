from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Type, Any, Union

from apiens import di
from apiens.operations import operation
from apiens.errors import BaseApplicationError
from apiens.util import decomarker


class doc(decomarker):
    """ Document an operation

    Usage:
        from apiens import operation, doc, di

        @operation()
        @doc.function('...', '...')
        @doc.parameter('id', '...', '...')
        @doc.result('...', '...')
        @doc.error(E_NOT_FOUND, '...', '...')
        @di.signature('ssn')
        def get_user(id: int, ssn: Session):
            ...
    """

    function_doc: Optional[FunctionDoc]
    parameters_doc: Dict[str, ParameterDoc]
    result_doc: Optional[ResultDoc]
    errors_doc: Dict[Type[BaseApplicationError], ErrorDoc]

    def __init__(self):
        """ Provide documentation for the function """
        super().__init__()
        self.function_doc = None
        self.parameters_doc = {}
        self.result_doc = None
        self.errors_doc = {}

    @classmethod
    def function(cls, summary: str, description: str = None):
        """ Document the function itself, what it does

        Args:
            summary: Short summary text
            description: Longer description
        """
        marker = cls()
        marker.function_doc = FunctionDoc(summary=summary, description=description)
        return marker

    @classmethod
    def parameter(cls, name: str, summary: str, description: str = None):
        """ Document a function's parameter

        Args:
            name: The parameter name
            summary: Short summary text
            description: Longer description
        """
        marker = cls()
        marker.parameters_doc[name] = ParameterDoc(name=name, summary=summary, description=description)
        return marker

    @classmethod
    def result(cls, summary: str, description: str = None):
        """ Document the function's return value

        Args:
            summary: Short summary text
            description: Longer description
        """
        marker = cls()
        marker.result_doc = ResultDoc(summary=summary, description=description)
        return marker

    @classmethod
    def error(cls, error: Type[BaseApplicationError], summary: str, description: str = None):
        """ Document an expected error that may be returned by this fucntion

        Args:
            error: A subclass of BaseApplicationError that implements some error
            summary: Short summary text
            description: Longer description
        """
        marker = cls()
        marker.result_doc = ErrorDoc(error=error, summary=summary, description=description)
        return marker

    def decorator(self, func: Callable):
        # If the function is decorated multiple times, merge
        marker = self.get_from(func)
        if marker is not None:
            self.function_doc = marker.function_doc or self.function_doc
            self.parameters_doc.update(marker.parameters_doc)
            self.result_doc = marker.result_doc or self.result_doc
            self.errors_doc.update(marker.errors_doc)

        # Done
        return super().decorator(func)

    def validate(self):
        """ Check that all documentations make sense """
        # Check that every documented parameter is actually a known parameter
        documented_parameter_names = set(self.parameters_doc)
        function_parameter_names = set(inspect.signature(self.func).parameters)
        mistaken_parameter_names = documented_parameter_names - function_parameter_names
        assert not mistaken_parameter_names, (
            f'Unknown names given to @doc.parameter(): {mistaken_parameter_names}. '
            f'This is probly a typo. Please document this function properly: {self.func}.'
        )

    def assert_is_fully_documented(self):
        """ Check that the function is fully documented. Used in projects by documenting freaks.

        It will test that:

        * The function is documented
        * Every parameter and the return value are both annotated and documented

        Raises:
            AssertionError if anything failed.
        """
        errors = []

        # Check that the function itself is documented
        if not self.function_doc:
            errors.append(f"Please put a @doc.function('', ''). The function is not documented.")
        # Check that its return value is documented
        if not self.result_doc:
            errors.append(f"Please put a @doc.result('', ''). The return value is not documented.")

        # Get its signature
        signature = operation.get_from(self.func).signature

        # Check that its return value is typed
        if signature.return_type is Any:
            errors.append(f"Please provide a return type annotation. The type is currently unknown.")

        # Check every parameter's type and documentation
        for name, type_ in signature.arguments.items():
            if type_ is Any:
                errors.append(f"Please put a @doc.parameter({name!r}, '', '')")
            if name not in self.parameters_doc:
                errors.append(f"Please put type annotation on parameter `{name}`. Its type is unknown.")

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

    @di.kwargs()  # so that it can be used as a context manager
    def error_validation_context_initializer(self):
        """ Create a context manager that will make sure the function only raises documented errors """
        return ErrorValidationContextManager(self)


@dataclass
class Documentation:
    # A short, one-line summary
    summary: str

    # A longer description
    description: Optional[str]


@dataclass
class FunctionDoc(Documentation):
    """ Documentation for a function """


@dataclass
class ParameterDoc(Documentation):
    """ Documentation for a parameter """
    # Parameter name
    name: str


@dataclass
class ResultDoc(Documentation):
    """ Documentation for the return value """


@dataclass
class ErrorDoc(Documentation):
    """ Documentation for a known exception """
    error: Type[BaseApplicationError]


class ErrorValidationContextManager:
    """ A context manager that will make sure that every error raised by the function is documented """

    def __init__(self, doc_: doc):
        self.doc = doc_

    def __enter__(self):
        return self

    def __exit__(self, exc_type: Type[Exception], exc_val: Union[Exception, BaseApplicationError], exc_tb):
        if isinstance(exc_val, BaseApplicationError):
            if exc_type not in self.doc.errors_doc:
                raise AssertionError(
                    f"Function {self.doc.func} raised an undocumented error: {exc_val.name!r}. "
                    f"Please put a @doc.error({exc_val.name!r}, '', '') on the function and document it."
                ) from exc_val
