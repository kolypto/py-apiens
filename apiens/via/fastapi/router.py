""" Bindings to the FastAPI framework """
from copy import copy

import fastapi
import inspect
from typing import List, Callable, Union

from apiens import operation, di, errors
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

    def add_operations(self, *operations: Union[Callable, type]):
        """ Add operations to the router

        Args:
             *operations: Functions, or classes, decorated by @operation.
        """
        for operation in operations:
            if inspect.isclass(operation):
                self.class_operations.append(self.register_class_operations(operation))
            else:
                self.func_operations.append(self.register_func_operation(operation))

    def register_func_operation(self, func: Callable) -> Callable:
        """ Register a single function-operation

        Args:
            func: The function to register as an operation
        """
        # Get the operation
        func_op = operation.get_from(func)
        assert func_op is not None, f'Function {func} must be decorated with @operation'

        # Validate the documentation
        if self.debug:
            func_op.check_operation_documentation(fully_documented=self.fully_documented)
            func = func_op.wrap_func_check_thrown_errors_are_documented(func)

        # Prepare the actual operation endpoint
        operation_endpoint = self._prepare_function_operation_endpoint(func, func_op)

        # Register the route
        self.add_api_route(
            # Path: the operation id itself
            '/' + func_op.operation_id,
            # Func: the function to all
            operation_endpoint,
            # HTTP method. Always 'POST', to let us pass arguments of arbitrary complexity in the body as JSON
            methods=['POST'],  # TODO: choose methods and paths
            # Use the same operation id: openapi-generator will find a good use to it
            operation_id=func_op.operation_id,
            name=func_op.operation_id,
            # Its return type: exactly what the function returns.
            # With some pydantic tuning.
            response_model=func_op.signature.return_type,
            response_model_exclude_unset=True,
            response_model_exclude_defaults=True,
            # Documentation.
            **self._operation_route_documentation_kwargs(func_op)
        )

        # Done
        return func

    def register_class_operations(self, class_: type) -> type:
        """ Register a single class-based operation with all of its sub-operations """
        # Get the class operation itself
        class_op = operation.get_from(class_)
        assert class_op is not None, f'Class {class_} must be decorated with @operation'

        # List its sub-operations
        for func_op in operation.all_decorated_from(class_, inherited=True):
            func = func_op.func

            # Validate the documentation
            if self.debug:
                func_op.check_operation_documentation(fully_documented=self.fully_documented)
                func = func_op.wrap_func_check_thrown_errors_are_documented(func)

            # Prepare the class operation endpoint
            operation_endpoint = self._prepare_method_operation_endpoint_function(class_, class_op, func, func_op)

            # Register the route
            self.add_api_route(
                # Path: the operation id itself
                '/' + class_op.operation_id + '/' + func_op.operation_id,
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
                **self._operation_route_documentation_kwargs(func_op)
            )

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

    def _prepare_function_operation_endpoint(self, func: Callable, func_op: operation) -> Callable:
        """ Prepare a function that will be used to call the operation """
        # Prepare the actual endpoint function
        def operation_endpoint(**kwargs):
            # Within an injector ...
            with self._request_injector(func_op) as request_injector:
                # ... execute the function
                return request_injector.invoke(func, **kwargs)

        # Done
        self._patch_operation_endpoint_signature(operation_endpoint, func_op.operation_id, func_op.signature.return_type, func_op)
        return operation_endpoint

    def _prepare_method_operation_endpoint_function(self, class_: type, class_op: operation, func: Callable, func_op: operation) -> Callable:
        # Prepare the actual endpoint function
        def operation_endpoint(**kwargs):
            # Inside a working injector ...
            with self._request_injector(func_op) as request_injector:
                # ... init the class
                instance_kwargs = class_op.pluck_kwargs_from(kwargs)
                instance = request_injector.invoke(class_, **instance_kwargs)

                # ... execute its method.
                # Provide `self=instance` as the 1st positional argument
                func_kwargs = func_op.pluck_kwargs_from(kwargs)
                return request_injector.invoke(func, instance, **func_kwargs)

        # Done
        self._patch_operation_endpoint_signature(operation_endpoint, func_op.operation_id, func_op.signature.return_type, class_op, func_op)
        return operation_endpoint

    def _patch_operation_endpoint_signature(self, endpoint: Callable, name: str, return_type: type, *operations: operation) -> Callable:
        """ Prepare an endpoint function that will be understood by FastAPI for calling a function

        This method is suitable for patching both a function operation and class operation functions.
        The difference lies in the distinction between function operations and class-based operations:
        * Function operations have arguments which become API input arguments
        * Class-based operations have a constructor that has to be called before the method, and it may also have paramenters.
        Therefore, with class-based operations, we have to merge the parameters from both the constructor and the method.
        """
        # Combine the parameters from all operations
        combined_parameters = {
            argument_name: self._operation_parameter_info(argument_name, argument_type, op)
            for op in operations
            for argument_name, argument_type in op.signature.arguments.items()
        }

        # Give it a name that might pop up somewhere in tracebacks
        endpoint.__name__ = name

        # Generate a signature
        endpoint.__signature__ = inspect.Signature(
            parameters=list(combined_parameters.values()),
            return_annotation=return_type,
        )

        # Done
        return endpoint

    def _operation_parameter_info(self, name: str, type_: type, op: operation) -> inspect.Parameter:
        """ Prepare a parameter for the FastAPI endpoint function """
        return inspect.Parameter(
            # Argument name: something that the API user has to provide
            name=name,
            # All arguments are keyword arguments
            kind=inspect.Parameter.KEYWORD_ONLY,
            # Parameter type annotation
            annotation=type_,
            # This is how FastAPI declares dependencies: <arg name> = Body() / Query() / Path()
            # TODO: Choose Body() / Query() / Path()
            default=fastapi.Body(
                # If the argument has a default, use it.
                # If not, use the `...`. This is how FastAPI declares required parameters
                op.signature.argument_defaults.get(name, ...),
                # Have this parameter named. That is, don't "unwrap" it and put it at the top level.
                # We could have generated our own Pydantic model for the whole body, and gave it an `embed=False`, \
                # but why do it ourselves if FastAPI can?
                embed=True,
                # Documentation for the parameter
                title=op.doc.parameters[name].summary,
                description=op.doc.parameters[name].description,
            ),
        )

    def _operation_route_documentation_kwargs(self, op: operation) -> dict:
        """ Get documentation kwargs for the route

        This function reads the docstring from `func` and returns kwargs for `add_api_route()`
        """
        route_kw = {}
        
        # Function documentation
        if op.doc.function:
            route_kw['summary'] = op.doc.function.summary
            route_kw['description'] = op.doc.function.description

        # Result documentation
        if op.doc.result:
            route_kw['response_description'] = (
                # Got to put them together because we have 2 fields, but FastAPI has only one
                (op.doc.result.summary or '') +
                (op.doc.result.description or '')
            )

        # Errors documentation.
        # Unfortunately, OpenAPI's responses are only described using http codes.
        # We will have to group our errors by HTTP codes :(
        if op.doc.errors:
            route_kw['responses'] = responses = {}

            # For every error
            for error_type, error_doc in op.doc.errors.items():
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
