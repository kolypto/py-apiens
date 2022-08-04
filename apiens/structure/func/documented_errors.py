""" Functions with documented errors """

from __future__ import annotations

import functools
from collections import abc
from typing import Optional, Union
from dataclasses import dataclass

from apiens.util.decomarker import decomarker


class documented_errors(decomarker):
    """ Decorator for functions with documented errors

    Example:
        @documented_errors()
        def load_users():
            "
            Raises:
                exc.F_FAIL: Something went wrong
            "
    """

    # Doc: every error
    errors: dict[type, ErrorDoc]

    def __init__(self, errors: dict[type, str] = {}, *, docstring: bool = True, check: bool = True, bases: tuple[type, ...] = (BaseException,)):
        """ Document exceptions for a function

        Args:
            errors: dict { exception class => description string }
            docstring: parse exceptions from the docstring
            check: verify that every exception is documented (list of parent classes)
        """
        super().__init__()

        # Parse the docstring as soon as it becomes available
        self._parse_docstring = docstring

        # Check exceptions that go through it
        self._check_exceptions = check

        # Exception bases to work with
        self._exception_bases = bases
        self._include_builtins = Exception in bases or BaseException in bases

        # Document some errors
        self.errors = {}
        for Error, summary in errors.items():
            self.document_error(Error, summary)

    def document_error(self, Error: type, summary: str, description: str = None):
        """ Add another documented exception

        Args:
            Error: exception class to document
            summary: short one-line summary
            description: brief description text
        """
        self._set_error_doc(ErrorDoc(
            error=Error,
            name=Error.__name__,
            summary=summary,
            description=description,
        ))
        return self

    def decorator(self, func: Union[abc.Callable, type]):
        # Parse docstring?
        if self._parse_docstring:
            parsed_exceptions = _parse_exceptions_from_function_docstring(
                func,
                include_builtins=self._include_builtins,
                bases=self._exception_bases
            )
            for error_doc in parsed_exceptions:
                self._set_error_doc(error_doc)

        # Check exceptions?
        if self._check_exceptions:
            func = wrap_verify_exceptions(
                func,
                catch_builtins=self._include_builtins,
                exception_bases=self._exception_bases,
                known_exceptions=frozenset(self.errors)
            )

        # Done
        return super().decorator(func)

    def _set_error_doc(self, doc: ErrorDoc):
        if doc.error not in self.errors:
            self.errors[doc.error] = doc
        else:
            self.errors[doc.error].defaults_from(doc)


@dataclass
class ErrorDoc:
    """ Documented error """
    # Exception class
    error: type

    # Error name
    name: str

    # Short one-line summary
    summary: str

    # Brief description text
    description: Optional[str]

    def defaults_from(self, another: ErrorDoc):
        self.name = self.name or another.name
        self.summary = self.summary or another.summary or ''
        self.description = self.description or another.description or None


class UndocumentedError(Exception):
    """ Wrapper for undocumented errors """


def wrap_verify_exceptions(func: abc.Callable, catch_builtins: bool, exception_bases: tuple[type, ...], known_exceptions: abc.Container[type]):
    """ Return a wrapped version of `fund` that raises `UndocumentedError` for unknown errors """
    @functools.wraps(func)
    def wrapped_func(*args, **kwargs):
        # Call the function
        try:
            return func(*args, **kwargs)
        # Catch errors, see if they're documented
        except Exception as e:
            cls = type(e)

            # Do not check builtins
            if not catch_builtins and cls in __builtins__:
                raise

            # Make sure error is documented
            if isinstance(e, exception_bases) and cls not in known_exceptions:
                raise UndocumentedError(str(e)) from e

    return wrapped_func



def _parse_exceptions_from_function_docstring(func: abc.Callable, include_builtins: bool, bases: tuple[type, ...] = (BaseException,)) -> abc.Iterator[ErrorDoc]:
    """ Parse exceptions from a function's docstring

    Args:
        func: The function to parse
        include_builtins: Include docs for builtin classes like `KeyError`?
        bases: Only include subclasses of
    """
    # Optional import of the `docstring_parser` library
    from docstring_parser import DocstringRaises
    from docstring_parser.google import parse

    # Parse the docstring
    parsed_docstring = parse(func.__doc__ or '')

    # Parse: docstring sections
    for section in parsed_docstring.meta:
        # Parse "Raises:"
        if isinstance(section, DocstringRaises):
            if not section.type_name:
                continue

            # Find exception by name
            error_name = section.type_name.strip()
            error_cls = _exception_by_name(func, error_name, include_builtins=include_builtins)

            # Return
            if issubclass(error_cls, bases):
                yield ErrorDoc(
                    error=error_cls,
                    name=error_name,
                    summary=section.description or '',
                    description=None,
                )


def _exception_by_name(func: abc.Callable, error_name: str, include_builtins: bool) -> type:
    """ Add documentation for an exception by name """
    # A globally available exception type?
    if include_builtins:
        try:
            return __builtins__[error_name]  # type: ignore[index]
        except KeyError:
            pass

    # Resolve the error type using function's global namespace
    try:
        return find_object_in_namespace(func.__globals__, error_name)  # type: ignore[attr-defined]
    except (KeyError, AttributeError) as e:
        raise ValueError(
            f"The docstring for function {func} references an error named {error_name!r}, "
            f"but it cannot be found in the function's globals. Please make sure its available "
            f"either by its name (e.g. `F_FAIL`), or by reference (`exc.F_FAIL`). "
        ) from e


def find_object_in_namespace(namespace: dict, reference: str):
    """ Given a namespace (like globals()), get the object referenced by `reference`

    Example:
        find_object_in_namespace( func.__globals__, 'errors.E_UNEXPECTED_ERROR' )
    """
    # Support "object.name" attribute access
    name, _, attribute = reference.partition('.')

    # Get the object itself
    object = namespace[name]

    # Get the attribute, recursively
    while True:
        attribute, _, next_attribute = attribute.partition('.')
        object = getattr(object, attribute)
        if not next_attribute:
            break

    # Done
    return object
