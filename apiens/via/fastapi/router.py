""" Bindings to the FastAPI framework """
import functools
from copy import copy

import fastapi
import inspect
from typing import List, Callable, Optional

from apiens import operation, di, doc, errors
from apiens.via.fastapi.error_schema import ErrorResponse


class OperationalApiRouter(fastapi.APIRouter):
    """ A FastAPI-compatible router to run your @operations """

    # The injector that's used to run your operations.
    # Don't forget to register your providers on it.
    # Note that this injector is just a template whose providers are used on actual endpoints
    injector: di.Injector

    # Flat operations: ordinary functions
    func_operations: List[Callable]

    # Class-based operations: classes
    class_operations: List[type]

    def __init__(self, debug: bool = False, fully_documented: bool = True, **kwargs):
        """

        Args:
            debug: Debug mode; will make extra consistency and quality checks
            fully_documented: Ensure that every function, parameter, and result, has a description and annotation.
                This parameter is dearly loved by documentation freaks, but is probably a curse to everyone else ... :)
            **kwargs: Keyword arguments for the APIRouter, if you for some reason want to tune it to your taste
        """
        super().__init__(**kwargs)

        # Debug mode
        self.debug: bool = debug

        # Do we want all operations fully documented?
        self.fully_documented: bool = fully_documented

        # Init
        self.injector = di.Injector()
        self.func_operations: List[Callable] = []
        self.class_operations: List[type] = []

    def add_flat_operations(self, *operations: Callable):
        """ Add flat operations: plain, @operation-decorated, functions.

        Use register_flat_operation() if you want to customize.

        Args:
            *operations: Functions. Decorated by @operation. Optionally decorated by @di.*.
        """
        for operation in operations:
            self.func_operations.append(
                self.register_flat_operation(operation)
            )
        return self

    def add_class_operations(self, *operations: type):
        for operation in operations:
            self.class_operations.append(
                self.register_class_operations(operation)
            )
        return self

    def register_flat_operation(self, func: Callable) -> Callable:
        """ Register a single flat operation

        Args:
            func: The function to register as an operation
        """
        # Get the operation
        func_op = operation.get_from(func)
        assert func_op is not None, f'Function {func} must be decorated with @operation'

        # Get the documentation for the operation
        func, func_doc = self._get_func_documentation(func)

        # Prepare the actual operation endpoint
        operation_endpoint = self._prepare_operation_endpoint_function(func, func_op, func_doc)

        # Register the route
        self.add_api_route(
            # Path: the operation id itself
            '/' + func_op.operation_id,
            # Func: the function to all
            operation_endpoint,
            # HTTP method. Always 'POST', to let us pass arguments of arbitrary complexity in the body as JSON
            methods=['POST'],
            # Use the same operation id: openapi-generator will find a good use to it
            operation_id=func_op.operation_id,
            name=func_op.operation_id,
            # Its return type: exactly what the function returns.
            # With some pydantic tuning.
            response_model=func_op.signature.return_type,
            response_model_exclude_unset=True,
            response_model_exclude_defaults=True,
            # Documentation.
            **self._route_documentation_kwargs(func_doc)
        )

        # Done
        return func

    def register_class_operations(self, class_: type) -> type:
        """ Register a single class-based operation with all of its sub-operations """
        # Get the class operation itself
        class_op = operation.get_from(class_)
        assert class_ is not None, f'Class {class_} must be decorated with @operation'

        # List its sub-operations
        for op in operation.all_decorated_from(class_, inherited=True):
            pass

        # Done
        return class_

    def _request_injector(self, func_op: operation) -> di.Injector:
        """ Create a di.Injector() for this request """
        # Init the request Injector by copy()ing the template injector that already has providers set up
        request_injector: di.Injector = copy(self.injector)

        # Provide a few contextual things:
        # * `operation`: the operation that is being run
        # * `di.Injector`: the injector itself, for low-level access
        request_injector.provide_value(operation, func_op)
        request_injector.provide_value(di.Injector, request_injector)

        return request_injector

    def _prepare_operation_endpoint_function(self, func: Callable, func_op: operation, func_doc: Optional[doc]) -> Callable:
        """ Prepare a function that will be used to call the operation """
        # Prepare the actual endpoint function
        def operation_endpoint(**kwargs):
            # Execute the function
            with self._request_injector(func_op) as request_injector:
                ret = request_injector.invoke(func, kwargs)

            # Return
            if func_op.return_name:
                return {
                    func_op.return_name: ret
                }
            else:
                return ret

        # Done
        self._prepare_operation_endpoint_signature(operation_endpoint, func_op, func_doc)
        return operation_endpoint

    def _prepare_operation_endpoint_signature(self, endpoint: Callable, op: operation, func_doc: Optional[doc]) -> Callable:
        """ Prepare a function that will be read by FastAPI by patching its __signature__ """
        # Give it a name that might pop up somewhere in tracebacks
        endpoint.__name__ = op.operation_id

        # Generate a signature
        endpoint.__signature__ = inspect.Signature(
            # Go over every parameter and put the signature and the documentation together
            parameters=[
                self._prepare_operation_parameter(argument_name, argument_type, op, func_doc)
                for argument_name, argument_type in op.signature.arguments.items()
            ],
            # Output value
            return_annotation=op.signature.return_type,
        )

        # Done
        return endpoint

    def _prepare_operation_parameter(self, name: str, type_: type, op: operation, func_doc: Optional[doc]) -> inspect.Parameter:
        """ Prepare a parameter for the FastAPI endpoint function """
        return inspect.Parameter(
            # Argument name: something that the API user has to provide
            name=name,
            # All arguments are keyword arguments
            kind=inspect.Parameter.KEYWORD_ONLY,
            # Parameter type annotation
            annotation=type_,
            # This is how FastAPI declares dependencies: <arg name> = Body() / Query() / Path()
            default=fastapi.Body(
                # If the argument has a default, use it.
                # If not, use the `...`. This is how FastAPI declares required parameters
                op.signature.argument_defaults.get(name, ...),
                # Have this parameter named. That is, don't "unwrap" it and put it at the top level.
                # We could have generated our own Pydantic model for the whole body, and gave it an `embed=False`, \
                # but why do it ourselves if FastAPI can?
                embed=True,
                # Documentation for the parameter
                title=func_doc.doc.parameters[name].summary if func_doc else None,
                description=func_doc.doc.parameters[name].description if func_doc else None,
            ),
        )

    def _get_func_documentation(self, func: Callable) -> (Callable, Optional[doc]):
        """ Check that the operation function is fully documented """
        # Get the function's doc
        func_doc = doc.get_from(func)

        # The `fully_documented` mode
        if self.fully_documented and self.debug:
            # Is documented?
            assert func_doc is not None, (
                f"Function {func} has no documentation associated with it. "
                f"Please use @doc.string(), or other @doc functions to document it."
            )

            # Validate documentation
            func_doc.assert_is_fully_documented()

            # Wrap the `func` for error validation
            func = func_doc.wrap_func_check_thrown_errors_are_documented(func)

        # Done. Return the same function unwrapped
        return func, func_doc

    def _route_documentation_kwargs(self, func_doc: Optional[doc]) -> dict:
        """ Get documentation kwargs for the route

        This function reads the @doc documentation from `func` and returns kwargs for `add_api_route()`
        """
        route_kw = {}

        # No doc, no party
        if not func_doc:
            return {}

        # Function documentation
        if func_doc.doc.function:
            route_kw['summary'] = func_doc.doc.function.summary
            route_kw['description'] = func_doc.doc.function.description

        # Result documentation
        if func_doc.doc.result:
            route_kw['response_description'] = (
                # Got to put them together because we have 2 fields, but FastAPI has only one
                (func_doc.doc.result.summary or '') +
                (func_doc.doc.result.description or '')
            )

        # Errors documentation.
        # Unfortunately, OpenAPI's responses are only described using http codes.
        # We will have to group our errors by HTTP codes :(
        if func_doc.doc.errors:
            route_kw['responses'] = responses = {}

            # For every error
            for error_type, error_doc in func_doc.doc.errors.items():
                # Only handle the types we know
                if not issubclass(error_type, errors.BaseApplicationError):
                    continue

                # Convert
                httpcode = error_type.httpcode

                # Init the HTTP code object
                if httpcode not in responses:
                    responses[httpcode] = {
                        'model': ErrorResponse,
                        'description': '',
                    }

                # Add our error to this description as some sort of Markdown list.
                # That's probably the best we can do here.
                responses[httpcode]['description'] += (
                    f'`{error_type.__name__}`. {error_doc.summary}{error_doc.description or ""}\n\n'
                )

        # Done
        return route_kw
