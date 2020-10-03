from __future__ import annotations

from dataclasses import dataclass

from typing import Optional, Callable, Dict, Type


@dataclass
class DocumentedFunction:
    """ All documentation for one particular function """
    # Doc: the function itself
    function: Optional[FunctionDoc]

    # Doc: every parameter
    parameters: Dict[str, ParameterDoc]

    # Doc: its result
    result: Optional[ResultDoc]

    # Doc: every error
    errors: Dict[Type[BaseException], ErrorDoc]

    # Doc: deprecation note
    deprecated: Optional[DeprecatedDoc]

    def merge(self, another: DocumentedFunction):
        """ Merge the documentation from another marker into this one """
        # Dicts: update()
        self.parameters.update(another.parameters)
        self.errors.update(another.errors)

        # Dataclasses: merge()
        self.function = self.function.merge(another.function) if self.function else another.function
        self.result = self.result.merge(another.result) if self.result else another.result
        self.deprecated = self.deprecated.merge(another.deprecated) if self.deprecated else another.deprecated

    def parse_from_function_docstring(self, func: Callable):
        """ Parse the function's documentation from its docstring """
        # Optional import of the `docstring_parser` library
        from docstring_parser import (
            DocstringParam,
            DocstringReturns,
            DocstringRaises,
            DocstringDeprecated,
        )
        from docstring_parser.google import parse

        # Parse the docstring
        parsed_docstring = parse(func.__doc__)

        # Parse: title & description
        if parsed_docstring.short_description or parsed_docstring.long_description:
            self.add_doc_for_function(
                summary=parsed_docstring.short_description,
                description=parsed_docstring.long_description or None,
            )

        # Parse: docstring sections
        for section in parsed_docstring.meta:
            # Parse: parameters
            if isinstance(section, DocstringParam):
                summary, _, description = section.description.partition('\n')
                self.add_doc_for_parameter(section.arg_name, summary, description or None)
            # Parse: return value
            elif isinstance(section, DocstringReturns):
                self.add_doc_for_result(section.description, None)
            # Parse: deprecation marker
            elif isinstance(section, DocstringDeprecated):
                self.add_doc_deprecated(section.version, section.description, None)
            # Parse: errors
            elif isinstance(section, DocstringRaises):
                self.add_doc_exception_name(func, section.type_name.strip(), section.description, None)
            # Parse: unknown sections
            else:
                self.add_doc_for_function(summary='', description=''.join(section.args) + ':\n' + section.description)

    def add_doc_for_function(self, summary: str, description: Optional[str]):
        """ Add function documentation """
        if not self.function:
            self.function = FunctionDoc('', None)
        self.function.merge(FunctionDoc(
            summary,
            description or None
        ))

    def add_doc_for_parameter(self, name: str, summary: str, description: Optional[str]):
        """ Add documentation for a parameter """
        self.parameters[name] = ParameterDoc(
            name=name,
            summary=summary,
            description=description or None,
        )

    def add_doc_for_result(self, summary: str, description: Optional[str]):
        """ Add documentation for the return value """
        if not self.result:
            self.result = ResultDoc('', None)
        self.result.merge(ResultDoc(
            summary=summary,
            description=description or None,
        ))

    def add_doc_deprecated(self, version: str, summary: str, description: Optional[str]):
        """ Add documentation for a deprecation """
        if not self.deprecated:
            self.deprecated = DeprecatedDoc('', None, '')
        self.deprecated.merge(DeprecatedDoc(
            version=version,
            summary=summary,
            description=description or None,
        ))

    def add_doc_exception(self, error_cls: Type[BaseException], summary: str, description: Optional[str]):
        """ Add documentation for an exception type """
        self.errors[error_cls] = ErrorDoc(
            error=error_cls,
            summary=summary,
            description=description,
        )

    def add_doc_exception_name(self, func: Callable, error_name: str, summary: str, description: Optional[str]):
        """ Add documentation for an exception by name """
        # A globally available exception type?
        if error_name in __builtins__:
            return __builtins__[error_name]

        # Resolve the error type using function's global namespace
        try:
            error_cls = find_object_in_namespace(func.__globals__, error_name)
        except (KeyError, AttributeError) as e:
            raise ValueError(
                f"The docstring for function {func} references an error named {error_name!r}, "
                f"but it cannot be found in the function's globals. Please make sure its available "
                f"either by its name (e.g. `E_FAIL`), or by reference (`exc.E_FAIL`). "
            ) from e

        # Document it
        self.add_doc_exception(error_cls, summary, description)


@dataclass
class DocBase:
    # A short, one-line summary
    summary: str

    # A longer description
    description: Optional[str]

    def merge(self, another: Optional[DocBase]) -> DocBase:
        if another:
            self.summary = (self.summary or '') + (another.summary or '')
            self.description = ((self.description or '') + (another.description or '')) or None
        return self


@dataclass
class FunctionDoc(DocBase):
    """ Documentation for a function """


@dataclass
class ParameterDoc(DocBase):
    """ Documentation for a parameter """
    # Parameter name
    name: str


@dataclass
class ResultDoc(DocBase):
    """ Documentation for the return value """


@dataclass
class ErrorDoc(DocBase):
    """ Documentation for a known exception """
    error: Type[BaseException]


@dataclass
class DeprecatedDoc(DocBase):
    """ Documentation for a function deprecation """
    # When was it deprecated
    version: str


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
