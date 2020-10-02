""" Bindings to the FastAPI framework """
import inspect
from contextlib import ExitStack
from copy import copy
from typing import List, Callable, ContextManager, Optional

import fastapi

from apiens import operation, di, doc
from apiens.via.fastapi.error_schema import ErrorResponse


class OperationalApiRouter(fastapi.APIRouter):
    """ A FastAPI-compatible router to run your @operations """

    def __init__(self, injector: di.Injector, debug: bool = False, fully_documented: bool = True, **kwargs):
        """

        Args:
            injector: An injector to use as a template. It must not be used, but have
                all the providers that your application wants the operations to be able to resolve.
            debug: Debug mode; will make extra consistency and quality checks
            fully_documented: Ensure that every function, parameter, and result, has a description and annotation.
                This parameter is dearly loved by documentation freaks, but is probably a curse to everyone else ... :)
            **kwargs: Keyword arguments for the APIRouter, if you for some reason want to tune it to your taste
        """
        super().__init__(**kwargs)

        # Request injector template
        self.request_injector_template = injector

        # Debug mode
        self.debug = debug

        # Do we want all operations fully documented?
        self.fully_documented: bool = fully_documented

        # Flat operations: ordinary functions
        self.func_operations: List[Callable] = []

        # Class-based operations: classes
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
        self.class_operations.extend(operations)
        return self

    def register_flat_operation(self, func: Callable) -> Callable:
        """ Register a single flat operation

        Args:
            func: The function to register as an operation
        """
        # Get the operation
        func_op = operation.get_from(func)
        assert func_op is not None, f'Function {func} must be decorated with @operation'

        # Get the documentation
        func, func_doc = self._get_func_documentation(func)

        # Prepare the actual operation function
        def operation_caller_function(**kwargs):
            with self._request_injector(func_op) as request_injector:
                return {
                    'ret': request_injector.invoke(func, kwargs),
                }

        # Prepare the endpoint function
        def endpoint(**input_parameters):
            return operation_caller_function(**input_parameters)

        endpoint.__name__ = func_op.operation_id
        endpoint.__signature__ = inspect.Signature(
            parameters=[
                inspect.Parameter(
                    name=argument_name,
                    kind=inspect.Parameter.KEYWORD_ONLY,
                    default=fastapi.Body(
                        func_op.signature.argument_defaults.get(argument_name, ...),
                        embed=True,
                        title=func_doc.parameters_doc[argument_name].summary,
                        description=func_doc.parameters_doc[argument_name].description,
                    ),
                    annotation=argument_type,
                )
                for argument_name, argument_type in func_op.signature.arguments.items()
            ],
            return_annotation=func_op.signature.return_type,
        )

        # Register the route
        self.add_api_route(
            # Path: the operation id itself
            '/' + func_op.operation_id,
            # Func: the function to all
            endpoint,
            # Use the same operation id: openapi-generator will find a good use to it
            operation_id=func_op.operation_id,
            name=func_op.operation_id,
            # HTTP method. Always 'POST', to let us pass arguments of arbitrary complexity in the body as JSON
            methods=['POST'],
            # Its return type: exactly what the function returns.
            # With some pydantic tuning.
            response_model=func_op.signature.return_type,
            response_model_exclude_unset=True,
            response_model_exclude_defaults=True,
            # Documentation.
            **self._route_documentation_kwargs(func)
        )

        # Done
        return func

    def _request_injector(self, func_op: operation) -> di.Injector:
        """ Create a di.Injector() for this request """
        # Init the request Injector by copy()ing the template injector that already has providers set up
        request_injector: di.Injector = copy(self.request_injector_template)

        # Provide a few contextual things:
        # * `operation`: the operation that is being run
        # * `di.Injector`: the injector itself, for low-level access
        request_injector.provide_value(operation, func_op)
        request_injector.provide_value(di.Injector, request_injector)

        return request_injector

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

    def _route_documentation_kwargs(self, func: Callable) -> dict:
        """ Get documentation kwargs for the route

        This function reads the @doc documentation from `func` and returns kwargs for `add_api_route()`
        """
        route_kw = {}

        # Get the function's documentation
        func_doc = doc.get_from(func)
        if not func_doc:
            return {}

        # Function documentation
        if func_doc.function_doc:
            route_kw['summary'] = func_doc.function_doc.summary
            route_kw['description'] = func_doc.function_doc.description

        # Result documentation
        if func_doc.result_doc:
            route_kw['response_description'] = (
                # Got to put them together because we have 2 fields, but FastAPI has only one
                (func_doc.result_doc.summary or '') +
                (func_doc.result_doc.description or '')
            )

        # Errors documentation.
        # Unfortunately, OpenAPI's responses are only described using http codes.
        # We will have to group our errors by HTTP codes :(
        if func_doc.errors_doc:
            route_kw['responses'] = responses = {}

            # For every error
            for error_type, error_doc in func_doc.errors_doc.items():
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
                    f'\n\n`{error_type.name}`. {error_doc.summary}{error_doc.description}'
                )

        # Done
        return route_kw
