""" Bindings to the FastAPI framework """
from copy import copy

import fastapi
import fastapi.params
import inspect
from typing import List, Callable, Union, Optional
import urllib.parse

from apiens import operation, di, errors
from apiens.via.fastapi.error_schema import ErrorResponse
from apiens.via.fastapi.fastapi_route import fastapi_route


class OperationalApiRouter(fastapi.APIRouter):
    """ A FastAPI-compatible router to run your @operations

    Example:
        from apiens.via.fastapi import OperationalApiRouter

        router = OperationalApiRouter(debug=True, fully_documented=True)
        router.add_operations(
            index,
            UserOperations,
        )

        # Application
        app = FastAPI()
        app.include_router(router)
    """

    # The injector that's used to run your operations.
    # Don't forget to register your providers on it.
    # Note that this injector is just a template whose providers are used on actual endpoints
    injector: di.Injector

    # Flat operations: ordinary functions
    func_operations: List[Callable]

    # Class-based operations: classes
    class_operations: List[type]

    def __init__(self, *, debug: bool = False, fully_documented: bool = True, **kwargs):
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

    def add_operations(self, *operations: Union[Callable, type], prefix: str = None, tags: List[str] = None):
        """ Add operations to the router

        Args:
             *operations: Functions, or classes, decorated by @operation.
             prefix: the prefix to add to every operation
        """
        for operation in operations:
            # Tell classes and functions apart
            if inspect.isclass(operation):
                self.class_operations.append(self.register_class_operations(operation, prefix=prefix, tags=tags))
            else:
                self.func_operations.append(self.register_func_operation(operation, prefix=prefix, tags=tags))

    def register_func_operation(self, func: Callable, *, prefix: str = None, tags: List[str] = None) -> Callable:
        """ Register a single function-operation

        Args:
            func: The function to register as an operation
        """
        # Get the operation
        func_op = operation.get_from(func)
        assert func_op is not None, f'Function {func} must be decorated with @operation'

        # Register
        try:
            self._register_operation(func_op, prefix=prefix, tags=tags)
        except Exception as e:
            raise ValueError(f"Error registering @operation {func_op}") from e

        # Done
        return func

    def register_class_operations(self, class_: type, *, prefix: str = None, tags: List[str] = None) -> type:
        """ Register class-based operations """
        # Get the class operation itself
        class_op = operation.get_from(class_)
        assert class_op is not None, f'Class {class_} must be decorated with @operation'

        # List its sub-operations
        for func_op in operation.all_decorated_from(class_, inherited=True):
            try:
                self._register_operation(func_op, class_op, prefix=prefix, tags=tags)
            except Exception as e:
                raise ValueError(f"Error registering @operation {func_op}") from e

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

    def _execute_operation(self, /, func_op: operation, class_op: Optional[operation], operation_kwargs: dict):
        """ Execute an operation, using the di.Injector() from this router

        This function is basically the actual FastAPI endpoint that executes your operations.
        """
        # Within an injector ...
        with self._request_injector(func_op) as request_injector:
            args = []

            # ... init the class
            if class_op:
                instance_kwargs = class_op.pluck_kwargs_from(operation_kwargs)
                instance = request_injector.invoke(class_op.func, **instance_kwargs)

                # Pass the `self` as the first argument
                args.append(instance)

            # ... execute the function
            func_kwargs = func_op.pluck_kwargs_from(operation_kwargs)
            return request_injector.invoke(func_op.func, *args, **func_kwargs)

    def _register_operation(self, func_op: operation, class_op: operation = None, prefix: str = None, tags: List[str] = None):
        # Validate the documentation
        if self.debug:
            func_op.check_operation_documentation(fully_documented=self.fully_documented)

        # Prepare the operation endpoint
        operation_endpoint = self._prepare_function_operation_endpoint(func_op, class_op or None)

        # Choose the method and the path
        method = get_operation_method(func_op)
        path = get_operation_path(func_op)

        if class_op:
            path = path_join(get_operation_path(class_op), path)

        if prefix:
            path = path_join(prefix, path)

        # Choose an operation id
        if class_op:
            operation_id = f'{class_op.operation_id}.{func_op.operation_id}'
        else:
            operation_id = f'{func_op.operation_id}'

        # Register the route
        self.add_api_route(
            # Path: the operation id itself
            path,
            # Func: the function to all
            operation_endpoint,
            # HTTP method. Always 'POST', to let us pass arguments of arbitrary complexity in the body as JSON
            methods=[method],
            # Use the same operation id: openapi-generator will find a good use to it
            operation_id=operation_id,
            name=operation_id,
            tags=tags,
            # Its return type: exactly what the function returns.
            # With some pydantic tuning.
            response_model=func_op.signature.return_type,
            response_model_exclude_unset=True,
            # Documentation.
            **operation_route_documentation_kwargs(func_op)
        )

    def _prepare_function_operation_endpoint(self, func_op: operation, class_op: operation = None) -> Callable:
        """ Make an endpoint-function: to call an operation via a di.Injector()

        This function has to:

        * Receive arbitrary **kwargs to be compatible with any operation's arguments
        * Have a signature that FastAPI can read to infer its arguments and their types
        * Start an injector as a context manager -- to provide dependencies to the operation
        * Run the function
        * Return the result

        In addition, if this function is a method of a class:

        * Create an instance of this class
        * Call the function as a method
        * When calling both, be sure to pluck arguments from **kwargs
        """
        # Prepare the actual endpoint function
        def operation_endpoint(**kwargs):
            return self._execute_operation(func_op, class_op, kwargs)

        # Tune the function's signature
        operations = [class_op, func_op] if class_op else [func_op]
        patch_operation_endpoint_signature(
            operation_endpoint,
            func_op.operation_id,
            func_op.signature.return_type,
            *operations
        )

        # Done
        return operation_endpoint


def patch_operation_endpoint_signature(endpoint: Callable, name: str, return_type: type, *operations: operation) -> Callable:
    """ Prepare an endpoint function that will be understood by FastAPI.

    Goals:

    * Give it a nice name
    * Set the return type annotation
    * Set types and documentation for every parameter

    This method is suitable for patching both a function operation and class operation functions.
    The difference lies in the distinction between function operations and class-based operations:
    * Function operations have arguments which become API input arguments
    * Class-based operations have a constructor that has to be called before the method, and it may also have paramenters.
    Therefore, with class-based operations, we have to merge the parameters from both the constructor and the method.
    """
    # Combine the parameters from all operations
    combined_parameters = {
        argument_name: operation_parameter_info(argument_name, argument_type, op)
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


def operation_parameter_info(name: str, type_: type, op: operation) -> inspect.Parameter:
    """ Prepare a parameter for the FastAPI endpoint function """
    # Create the FastAPI parameter
    # In FastAPI, this determines where the parameter is coming from: Body, Query, Path, etc.

    # Is there an override?
    customized = fastapi_route.get_from(op.func)
    if customized and name in customized.parameters:
        parameter = fastapi_route.get_from(op.func).parameters[name]
    # Use the default: Body()
    else:
        parameter = fastapi.Body(
            # If the parameter has a default, use it.
            # If not, use the `...`. This is how FastAPI declares required parameters
            op.signature.argument_defaults.get(name, ...),
            # Documentation for the parameter
            title=op.doc.parameters[name].summary if name in op.doc.parameters else None,
            description=op.doc.parameters[name].description if name in op.doc.parameters else None,
        )

    # For `Body` parameters, make sure they have `embed=True`.
    # That is, don't "unwrap" it and put it at the top level.
    if isinstance(parameter, fastapi.params.Body):
        parameter.embed = True

    # Make the parameter
    return inspect.Parameter(
        # Argument name: something that the API user has to provide
        name=name,
        # All arguments are keyword arguments
        kind=inspect.Parameter.KEYWORD_ONLY,
        # Parameter type annotation
        annotation=type_,
        # This is how FastAPI declares dependencies: <arg name> = Body() / Query() / Path()
        default=parameter
    )


def operation_route_documentation_kwargs(op: operation) -> dict:
    """ Get documentation kwargs for the route

    This function reads the docstring from `func` and returns kwargs for `add_api_route()`
    """
    route_kw = {}

    # Function documentation
    if op.doc.function:
        route_kw['summary'] = op.doc.function.summary
        route_kw['description'] = op.doc.function.description

    if op.doc.deprecated:
        route_kw['deprecated'] = True
        # TODO: include more info? `op.doc.deprecated.version/summary/description` & stuff

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


def get_operation_method(op: operation) -> str:
    """ Having an @operation, decide which HTTP method to use for it. It may be overridden with @fastapi_route() """
    if fastapi_route.is_decorated(op.func):
        return fastapi_route.get_from(op.func).method
    else:
        return 'POST'


def get_operation_path(op: operation) -> str:
    """ Having an @operation, decide which path to use for it. It may be overridden with @fastapi_route() """
    if fastapi_route.is_decorated(op.func):
        return path_join('/', fastapi_route.get_from(op.func).path)
    else:
        return path_join('/', op.operation_id)


def path_join(base: str, url: str) -> str:
    """ Join two parts of an URL """
    base = base.rstrip('/') + '/'
    url = url.lstrip('/')
    return urllib.parse.urljoin(base, url)
