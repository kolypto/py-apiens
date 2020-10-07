""" Class-based views for FastAPI

Class-based views are implemented as @class_based_view() decorator.

Example:
    router = APIRouter()

    @class_based_view(
        router,
        Route(view_name='list', methods='GET', path='/'),  # or: ('list', 'GET', '/')
        Route(view_name='test', methods='GET', path='/test'),
    )
    class TestView:
        def __init__(self, current_user: models.User = Depends(current_user)):
            self.current_user = current_user

        def list(self):
            return {'users': []}

        def test(self, input: str):
            return {
                'current_user.id': self.current_user.id,
                'input': input,
            }

        @api_route.get('/self-test')
        def custom(self):
            return {'status': 'ok'}
"""
from __future__ import annotations

import dataclasses

import pydantic
from apiens.util import decomarker
from fastapi import APIRouter, FastAPI
from fastapi import Depends
from pydantic.utils import lenient_issubclass
from typing import List, Callable, Sequence, Union, Iterable, TypeVar, Optional, get_type_hints

from .patch_func import set_parameter_default, copy_func

ClsT = TypeVar('ClsT', bound=type)


class class_based_view:
    """ Decorator for classes to enable using their methods as class-based views """

    def __init__(self, router: Union[APIRouter, FastAPI], *routes: Union[Sequence, Route]):
        """ Decorate a class-based view

        Args:
            router: The APIRouter to register the routes on
            *routes: List of routes registerd on this class.
                Example: Route('list', '/', 'GET')
                Example: ('list', '/', 'GET')
                Alternatively, you can decorate individual methods using @api_route.get()
        """
        self.router = router
        self.routes: List[Route] = [
            # make Route() objects from tuples, if necessary
            route if isinstance(route, Route) else Route(*route)
            for route in routes
        ]

    def __call__(self, ViewCls: type):
        """ Decorator call """
        self.bind_to_class(ViewCls)

        # Transparently return the very same class.
        # The decorator is completely dissolved.
        return ViewCls

    def bind_to_class(self, ViewCls: type):
        """ Called when the class is known """
        # Discover new routes
        self._find_routes_on_class(ViewCls)

        # Add class information
        self._bind_routes_to_class(ViewCls)

        # Process the class
        self._prepare_class(ViewCls)

        # Patch every route endpoint
        self._patch_route_endpoints(ViewCls)

        # Register routes on the router
        self.register_routes_on(self.router, self.routes)

    @classmethod
    def register_routes_on(cls, router: APIRouter, routes: Iterable[Route]):
        """ Register all routes on the given router """
        for route in routes:
            if route.view_func_implemented:
                route.add_endpoint_to_router(router)

    def _prepare_class(self, ViewCls: type):
        """ Prepare the class before the routes are processed """
        # Run hooks
        if issubclass(ViewCls, ViewBase):
            ViewCls._customize_class_based_view(self)

    def _find_routes_on_class(self, ViewCls: type):
        """ Get @api_route()-decorated methods from the class and add them to self.routes  """
        self.routes.extend(
            decorated_endpoint.route
            for decorated_endpoint in api_route.all_decorated_from(ViewCls, inherited=True)
        )

    def _bind_routes_to_class(self, ViewCls: type):
        """ Add class information to every Route """
        for route in self.routes:
            route.bind_to_class(ViewCls)

    def _patch_route_endpoints(self, ViewCls: type):
        """ As soon as the class is known, patch every route to make sure it works with FastAPI """
        # Patch
        for route in self.routes:
            # Patch the endpoint
            if route.view_func_implemented:
                self._patch_endpoint(route)
                self._augment_endpoint_route(route)

    def _patch_endpoint(self, route: Route):
        """ Patch an endpoint to become compatible with FastAPI """
        route.view_func = copy_func(route.view_func)

        # By default, FastAPI will see the `self` argument and think it's a dependency.
        # It actually is: a dependency on an instantiated class.
        # Let's declare it as such: `self = Depends(ViewCls)`.
        route.view_func = patch_method_fastapi_compatible(route.ViewCls, route.view_func)

    def _augment_endpoint_route(self, route: Route):
        """ Get information from the endpoint and augment route """
        # Get type hints
        # Note that this evaluates forward references. We supply:
        # * the module as the global namespace
        # * the class as the local namespace
        # This lets you use class attributes as forward references. Yeehaw!
        # NOTE: type hints are evaluated on a per-view basis: thanks to copy_func(),
        # every class is evaluated in its own context! :)
        annotations = get_type_hints(
            route.view_func,
            # globalns=sys.modules[route.ViewCls.__module__].__dict__,  # use viewfunc.__globals__
            localns=vars(route.ViewCls)
        )

        # If there is anything useful in the return annotation, use it with FastAPI
        if lenient_issubclass(annotations.get('return'), pydantic.BaseModel):
            route.api_route_kwargs.setdefault('response_model', annotations['return'])


class api_route(decomarker):
    """ Decorate API methods on a class-based view

    NOTE: these routes will be added *after* other routes in the class-based view.
    TODO: override flag?

    Example:
        @class_based_view(router)
        class View:
            @api_route.get('/')
            def get(self, query: str):
                ...
    """

    def __init__(self, methods: Union[str, Iterable[str]], path: str, **api_route_kwargs):
        """ Describes a Route of a class-based view

        Args:
            methods: HTTP methods to use. Example: 'GET' or ['GET', 'POST']
            path: Endpoint path. Example: '/{id}'
            **api_route_kwargs: Additional options for APIRouter.add_api_route()
        """
        super().__init__()
        self.route = Route(..., methods, path, **api_route_kwargs)

    def __call__(self, handler_method: MethodT) -> MethodT:
        try:
            return super().__call__(handler_method)
        finally:
            self.route.view_name = self.func_name

    # region Convenience methods

    @classmethod
    def get(cls, path: str) -> api_route:
        return cls(path, 'GET')

    @classmethod
    def post(cls, path: str) -> api_route:
        return cls(path, 'POST')

    @classmethod
    def put(cls, path: str) -> api_route:
        return cls(path, 'PUT')

    @classmethod
    def patch(cls, path: str) -> api_route:
        return cls(path, 'PATCH')

    @classmethod
    def delete(cls, path: str) -> api_route:
        return cls(path, 'DELETE')

    # endregion


class ViewBase:
    """ Base for ClassBasedViews

    Note that @class_based_view can work with absolutely any class.
    However, if your class wants to customize the routes before they are registered, you have to inherit
    from this class and implement the hook methods.

    If you need something that is even more custom, then subclass @class_based_view
    """

    @classmethod
    def _customize_class_based_view(cls, decorator: class_based_view):
        """ Hook into @class_based_view and customize it before it is registered """
        raise NotImplementedError


@dataclasses.dataclass
class Route:
    """ Information about a route in a class-based view """

    def __init__(self, view_name: str, path: str, methods: Optional[Union[str, Iterable[str]]] = None, **api_route_kwargs):
        """ Describes a route of a class-based view

        Args:
            view_name: Name of the view function. E.g. 'get' will point to get()
            path: Endpoint path. Example: '/{id}'
            methods: HTTP methods to use. Example: 'GET' or ['GET', 'POST']. Default: 'GET'
            **api_route_kwargs: Additional options for APIRouter.add_api_route()
        """
        self.view_name = view_name
        self.path = path
        if methods is None:
            self.methods = None
        elif isinstance(methods, str):
            self.methods = [methods]
        else:
            self.methods = list(methods)
        self.api_route_kwargs = api_route_kwargs

    view_name: str
    path: str
    methods: List[str]
    api_route_kwargs: dict = dataclasses.field(default_factory=dict)

    def bind_to_class(self, ViewCls: type):
        """ Executed when the class is known """
        # Same: class, method
        self.ViewCls = ViewCls
        self.view_func = getattr(ViewCls, self.view_name)
        self.view_func_implemented = (self.view_func not in (None, NotImplemented))

    # Internal fields
    ViewCls: type = None
    view_func: Callable = None
    view_func_implemented: bool = None

    def add_endpoint_to_router(self, router: APIRouter):
        """ Add one route to the router """
        router.add_api_route(
            self.path,
            self.view_func,
            methods=self.methods,
            **self.api_route_kwargs
        )


class fastapi_compatible_method:
    """ A simple tool to implement a single method compatible with FastAPI

    It is a decorator that takes a method, and patches it to have the `self` argument
    to be declared as a dependency on the class constructor:

    * Arguments of the method become dependencies
    * Arguments of the __init__() method become dependencies as well
    * You can use the method as a dependency, or as an API endpoint.

    Example:

        class View:
            def __init__(self, arg: str):  # Arguments are dependencies (?arg)
                self.arg = arg

            @fastapi_compatible_method
            async def get(self, another_arg: str):  # arguments are dependencies (?another_arg)
                return {
                    'arg': self.arg,
                    'another_arg': another_arg,
                }

        app.get('/test')(View.get)
        # Check: http://localhost:8000/test?arg=value&another_arg=value

    It is a little awkward: you can't decorate the method with @app.get() directly: it's only possible
    to do it after the class has fully created.

    Thanks to: @dmontagu for the inspiration
    """

    # It is a descriptor: it wraps a method, and as soon as the method gets associated with a class,
    # it patches the `self` argument with the class dependency and dissolves without leaving a trace.

    def __init__(self, method: Callable):
        self.method = method

    def __set_name__(self, cls: type, method_name: str):
        # Patch the method and put it onto the class
        patched_method = patch_method_fastapi_compatible(cls, self.method)
        return setattr(cls, method_name, patched_method)


MethodT = TypeVar('MethodT', bound=Callable)


def patch_method_fastapi_compatible(Cls: type, method: MethodT) -> MethodT:
    """ Patch the method function to become compatible with FastAPI

    We only have to declare `self` as a dependency on the class itself: `self = Depends(cls)`.
    Using this hack, FastAPI provides the `self` argument as a dependency by instantiating a class.

    Args:
        Cls: the class the method is bound to
        method: the method function
    Returns:
        the same function, patched.
        If you want it clean, make a copy()
    """
    # By default, FastAPI will see the `self` argument and think it's a dependency.
    # It actually is: a dependency on an instantiated class.
    # Let's declare it as such: `self = Depends(ViewCls)`.
    patched_method = set_parameter_default(method, 'self', Depends(Cls))
    return patched_method

