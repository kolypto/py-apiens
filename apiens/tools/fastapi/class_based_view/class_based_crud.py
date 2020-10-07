""" FastAPI bindings to CrudBase crud handlers

Example:
    class Response(pd.BaseModel):
        user: UserCrud.crudsettings.ResponseSchema

    class ListResponse(pd.BaseModel):
        users: List[UserCrud.crudsettings.ResponseSchema]

    @class_based_crud_view(router)
    class UserView(CrudView):
        CrudHandler = UserCrud
        name = 'user'
        names = 'users'

        Response: ClassVar[Type[pd.BaseModel]] = Response
        ListResponse: ClassVar[Type[pd.BaseModel]] = ListResponse

        def __init__(self, ssn: Session = Depends(db_session)):
            self.crud = self.CrudHandler(ssn)

        def primary_key(self, id: int = Path(..., title='User id')) -> dict:
            return {'id': id}

        create_or_update = NotImplemented

Is approximately equivalent to the following code:

    @router.get('/', response_model=ListResponse, response_model_exclude_unset=True)
    def list_users(ssn: Session = Depends(db_session)):
        with UserCrud(ssn).transaction() as crud:
            users = crud.list()
            return ListResponse(users=users)

    @router.get('/{id}', response_model=Response, response_model_exclude_unset=True)
    def get_user(id: int, ssn: Session = Depends(db_session)):
        with UserCrud(ssn).transaction() as crud:
            user = crud.get(id=id)
            return Response(user=user)

    @router.post('/', response_model=Response, response_model_exclude_unset=True)
    def create_user(user: UserCrud.crudsettings.CreateInputSchema = Body(..., embed=True),
                    ssn: Session = Depends(db_session)):
        with UserCrud(ssn).transaction() as crud:
            user = crud.create(user)
            return Response(user=user)

    @router.post('/{id}', response_model=Response, response_model_exclude_unset=True)
    def update_user(id: int,
                    user: UserCrud.crudsettings.UpdateInputSchema = Body(..., embed=True, title='Partial User: only modified fields'),
                    ssn: Session = Depends(db_session)):
        with UserCrud(ssn).transaction() as crud:
            user = crud.update(user, id=id)
            return Response(user=user)

    @router.delete('/{id}', response_model=Response, response_model_exclude_unset=True)
    def delete_user(id: int, ssn: Session = Depends(db_session)):
        with UserCrud(ssn).transaction() as crud:
            user = crud.delete(id=id)
            return Response(user=user)
"""

from copy import copy

import pydantic as pd
from apiens.views.mongoquery_crud import MongoCrudBase, MongoCrudSettings
from fastapi import APIRouter
from fastapi import Body, Depends
from typing import Type, ClassVar, Callable, Mapping, List, Optional

from .class_based_view import ViewBase  # noqa
from .class_based_view import class_based_view, Route, patch_method_fastapi_compatible
from .patch_func import patch_function_keyword_arguments


class CrudView:
    """ A class-based view for CrudBase crud handlers.

    An instance is created on every request, and one of its methods is executed.
    """

    # The Crud Handler to use
    CrudHandler: ClassVar[Type[MongoCrudBase]]

    # How to call the field in the response?
    # `name` when a single object is returned;
    # `names` when multiple objects are returned
    name: ClassVar[str]
    names: ClassVar[str]

    # Response schemas:
    # `Response` when a single object is returned
    # `ListResponse` when multiple objects are returned
    # Schemas will be generated using create_model() and `name` with `names` if not provided
    Response: ClassVar[Type[pd.BaseModel]]
    ListResponse: ClassVar[Type[pd.BaseModel]]

    # `crud`: instantiated CrudHandler
    __slots__ = 'crud',
    crud: MongoCrudBase

    def __init__(self):
        """ View constructor, executed on every request. Accepts dependencies as arguments. """
        # Override this method to declare your real dependencies
        raise NotImplementedError

    def primary_key(self) -> dict:
        """ Get request arguments and convert them to crud kwargs

        The output of this method is given to update() and delete() crud operations as kwargs.
        """
        # Override this method: declare the primary key dependencies and return them as a dict
        raise NotImplementedError

    # region CRUD methods

    # TODO: Currently, FastAPI uses `Response` and `ListResponse` to actually validate the resulting objects.
    #  Make this behavior optional: do not validate responses in production!

    # NOTE: return annotation is a forward reference that is dynamically re-evaluated on a per-class basis.
    def list(self) -> 'ListResponse':
        """ list() CRUD operation """
        with self.crud.transaction() as crud:
            items = crud.list()
            return self.ListResponse(**{self.names: items})

    # NOTE: Depends(primary_key) will be replaced by your actual primary key function
    def get(self, primary_key: dict = Depends(primary_key)) -> 'Response':
        """ get() CRUD operation """
        with self.crud.transaction() as crud:
            item = crud.get(**primary_key)
            return self.Response(**{self.name: item})

    # NOTE: `item` model and `alias` will be replaced from your `name` and `CrudHandler`
    def create(self, item: pd.BaseModel = Body(..., alias=None, embed=True, title='The new object to create')) -> 'Response':
        """ create() CRUD operation """
        with self.crud.transaction() as crud:
            item = crud.create(item)
            return self.Response(**{self.name: item})

    # NOTE: Depends(primary_key) will be replaced by your actual primary key function
    # NOTE: `item` model and `alias` will be replaced from your `name` and `CrudHandler`
    def update(self,
               primary_key: dict = Depends(primary_key),
               item: pd.BaseModel = Body(..., alias=None, embed=True, title='Partial object: only modified fields')) -> 'Response':
        """ update() CRUD operation """
        with self.crud.transaction() as crud:
            item = crud.update(item, **primary_key)
            return self.Response(**{self.name: item})

    # NOTE: Depends(primary_key) will be replaced by your actual primary key function
    def delete(self, primary_key: dict = Depends(primary_key)) -> 'Response':
        """ delete() CRUD operation """
        with self.crud.transaction() as crud:
            item = crud.delete(**primary_key)
            return self.Response(**{self.name: item})

    # NOTE: `item` model and `alias` will be replaced from your `name` and `CrudHandler`
    def create_or_update(self, item: pd.BaseModel = Body(..., alias=None, embed=True,
                                                         title='The object to save',
                                                         description='It will be updated if found by the primary key; created otherwise')) -> 'Response':
        """ create_or_update() CRUD operation """
        with self.crud.transaction() as crud:
            item = crud.create_or_update(item)
            return self.Response(**{self.name: item})

    # endregion


class class_based_crud_view(class_based_view):
    """ Decorator for the class-based CrudView """

    def __init__(self, router: APIRouter, pk_path: str = '/{id:int}', *routes: Route, operation_id_fmt: Optional[str] = '{method}_{name}'):
        """ Add routes from this decorated class to `router`

        Args:
            router: The APIRouter to register the routes on
            pk_path: URL path to use for a route with a primary key. Example: '/{id}'
            *routes: Additional routes to register
            operation_id_fmt: OperationId format
        """
        root_path = '/'
        super().__init__(
            router,
            # Known API routes.
            # If some of them are `None` or `NotImplemented`, they will be ignored
            Route('list', root_path, 'GET'),
            Route('get', pk_path, 'GET'),
            Route('create', root_path, 'POST'),
            Route('create_or_update', root_path, 'PUT'),
            # NOTE: ReST standards use PUT for update(). I prefer POST.
            Route('update', pk_path, 'POST'),
            Route('delete', pk_path, 'DELETE'),
            # Extra routes
            *routes
        )
        self.operation_id_fmt = operation_id_fmt

    def _prepare_class(self, ViewCls: Type[CrudView]):
        # Generate default `Response` and `ListResponse`
        if not getattr(ViewCls, 'Response', None):
            ViewCls.Response = self._prepare_class_generate_Response(ViewCls)
        if not getattr(ViewCls, 'ListResponse', None):
            ViewCls.ListResponse = self._prepare_class_generate_ListResponse(ViewCls)

        # super
        super()._prepare_class(ViewCls)

    def _patch_route_endpoints(self, ViewCls: Type[CrudView]):
        super()._patch_route_endpoints(ViewCls)

        # Prepare routes as a mapping
        routes_map = {route.view_name: route for route in self.routes}
        # Patch routes for compatibility with FastAPI
        self._patch_route_endpoints_for_fastapi(ViewCls, routes_map)

    def _patch_route_endpoints_for_fastapi(self, ViewCls: Type[CrudView], routes_map: Mapping[str, Route]):
        # Patch the `primary_key()` method: declare `self` to be a dependency to make sure it works
        ViewCls.primary_key = patch_method_fastapi_compatible(ViewCls, copy(ViewCls.primary_key))
        
        # This is how we generate operation_id
        opid = lambda method, name: (
            self.operation_id_fmt.format(method=method, name=name)
            if self.operation_id_fmt else
            None
        )

        # Patch every view to make sure it works as a CRUD handler
        # Each endpoint can receive: primary_key(), `item` input item with `InputSchema` annotation
        crudsettings: MongoCrudSettings = ViewCls.CrudHandler.crudsettings
        self._patch_route_endpoint(routes_map, 'list', opid('list', ViewCls.names))
        self._patch_route_endpoint(routes_map, 'get', opid('get', ViewCls.name))
        self._patch_route_endpoint(routes_map, 'create', opid('create', ViewCls.name),
                                   InputSchema=crudsettings.CreateInputSchema)
        self._patch_route_endpoint(routes_map, 'update', opid('update', ViewCls.name),
                                   InputSchema=crudsettings.UpdateInputSchema)
        self._patch_route_endpoint(routes_map, 'create_or_update', opid('create_or_update', ViewCls.name),
                                   InputSchema=crudsettings.CreateOrUpdateInputSchema)
        self._patch_route_endpoint(routes_map, 'delete', opid('delete', ViewCls.name))

    @classmethod
    def _patch_route_endpoint(cls,
                              routes_map: Mapping[str, Route],
                              view_name: str,
                              operation_id: Optional[str], *,
                              InputSchema: Type[pd.BaseModel] = None):
        """ Patch a route's endpoint to make it compatible with FastAPI.

        The following patches are done to views that require it:

        * A view requires the `primary_key`: Depends(ViewCls.primary_key) is provided
        * A view requires the `item` input data: Body(alias=ViewCls.name) is provided
        """
        # Get the route. Skip it if not implemented.
        route = routes_map[view_name]
        if not route.view_func_implemented:
            return

        # Patch it
        ViewCls: Type[CrudView] = route.ViewCls  # noqa
        route.view_func = patch_crud_handler_endpoint_arguments(
            endpoint=route.view_func,
            # Patches
            primary_key=ViewCls.primary_key,  # primary_key() function
            input_item_name=ViewCls.name,
            InputSchema=InputSchema,
        )

        # Give it a nice name (if not already set)
        if operation_id:
            route.api_route_kwargs.setdefault('operation_id', operation_id)

        # Additional route settings
        route.api_route_kwargs.update(
            # Not setting `response_model` because it comes from return annotations
            #response_model=ListResponse or Response
            response_model_exclude_unset=True,
        )

    def _prepare_class_generate_Response(self, ViewCls: Type[CrudView]) -> Type[pd.BaseModel]:
        """ Generate the ViewCls.Response schema (when not provided) """
        return pd.create_model(
            # module/view/class combination has to be unique.
            # this enables us to have multiple views in a file
            ViewCls.__name__ + 'Response',
            __module__=ViewCls.__module__,
            **{ViewCls.name: (
                ViewCls.CrudHandler.crudsettings.ResponseSchema,
                pd.Field(...))}
        )

    def _prepare_class_generate_ListResponse(self, ViewCls: Type[CrudView]) -> Type[pd.BaseModel]:
        """ Generate the ViewCls.ListResponse schema (when not provided) """
        return pd.create_model(
            ViewCls.__name__ + 'ListResponse',
            __module__=ViewCls.__module__,
            **{ViewCls.names: (
                List[ViewCls.CrudHandler.crudsettings.ResponseSchema],
                pd.Field(...))}
        )


def patch_crud_handler_endpoint_arguments(
        endpoint: Callable, *,
        primary_key: Callable = None,
        input_item_name: str = None,
        InputSchema: Type[pd.BaseModel] = None):
    """ Take an endpoint and patch its arguments:

    * `pk`: make it use the cls.primary_key
    * `item`: give it a proper `cls.name` and a type annotation
    
    Args:
        endpoint: The endpoint: view function to patch
        primary_key: Dependency provider for the `pk` dependency: a function
        input_item_name: Field name for the input object (create() and update())
        InputSchema: Pydantic schema for the input object
    """
    # Get a patched copy
    new_endpoint = copy(endpoint)
    patch = patch_function_keyword_arguments(new_endpoint)
    try:
        parameter = None  # to make sure that the first send() gets a None
        while parameter := patch.send(parameter):
            # Primary key
            # Replace: set default value = Depends(primary_key)
            # This is necessary because the `primary_key` function is local to every implementation
            if parameter.name == 'primary_key':
                assert primary_key
                parameter = parameter.replace(default=Depends(primary_key))
            # Input item
            # Replace: set type annotation = InputSchema and default value's alias to `name`
            # This input item's name and schema depend on the implementation
            elif parameter.name == 'item':
                assert InputSchema, f'No input schema provided for {endpoint} in the relevant Crud Handler settings. Cannot configure.'
                assert input_item_name, f'No inpput object `name` was provided. Cannot configure {endpoint}'
                default = copy(parameter.default)
                default.alias = input_item_name
                parameter = parameter.replace(default=default, annotation=InputSchema)
    except StopIteration:
        # Done: return the patched endpoint
        return new_endpoint
