from collections import abc
import dataclasses
from typing import TypedDict, Any, Union
from typing import get_args, get_origin, get_type_hints, is_typeddict

from .model_info import ModelInfo, FieldInfo
from .predicates import filter_by_predicate
from .singledispatch_lambda import singledispatch_lambda


@singledispatch_lambda().decorator
def match(model: Union[type, Any], filter: callable = None) -> ModelInfo:
    raise NotImplementedError(f'Object of type {model} is not supported')


@match.register(is_typeddict)
def match_typed_dict(model: type[TypedDict], filter: callable = None) -> ModelInfo:
    """ Match: TypedDict """
    return ModelInfo(fields={
        name: FieldInfo(
            name=name,
            type=None, #str(type??),  # not implemented yet
            required=name in model.__required_keys__,
            nullable=_is_typing_optional(type),
        )
        for name, type in get_type_hints(model).items()
        if filter_by_predicate(name, filter)
    })


@match.register(dataclasses.is_dataclass)
def match_dataclass(model: type, filter: callable = None) -> ModelInfo:
    """ Match: @dataclass """
    field: dataclasses.Field
    return ModelInfo(fields={
        field.name: FieldInfo(
            name=field.name,
            type=None,  # not implemented yet
            required=field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING,
            nullable=_is_typing_optional(field.type),
        )
        for field in dataclasses.fields(model)
        if filter_by_predicate(field.name, filter)
    })


try:
    import pydantic as pd
except ImportError:
    pass
else:
    @match.register(lambda v: isinstance(v, type) and issubclass(v, pd.BaseModel))
    def match_pydantic_model(model: pd.BaseModel, filter: callable = None) -> ModelInfo:
        """ Match: Pydantic model """
        field: pd.fields.ModelField
        return ModelInfo(fields={
            field.name: FieldInfo(
                name=field.name,
                type=None,  # not implemented
                required=None if field.required is pd.fields.Undefined else field.required,
                nullable=field.allow_none,
                aliases={field.alias} if field.alt_alias else set(),
            )
            for field in model.__fields__.values()
            if filter_by_predicate(field.name, filter)
        })

try:
    import sqlalchemy as sa
    import sqlalchemy.orm.base
    import jessiql.sainfo
except ImportError:
    pass
else:
    @match.register(lambda v: sa.orm.base.manager_of_class(v) is not None)
    def match_sqlalchemy_model(model: type, filter: callable = None, *, props: bool = False, rels: bool = False) -> ModelInfo:
        """ Match: SqlAlchemy model """
        mapper: sa.orm.Mapper = sa.orm.class_mapper(model)

        fields = {}

        # Columns, Relations
        for name, attr in mapper.all_orm_descriptors.items():
            if not filter_by_predicate(name, filter):
                continue

            if jessiql.sainfo.columns.is_column(attr):
                col: sa.Column = attr.expression

                # Extract the default value
                default = attr.default
                # SqlALchemy likes to wrap it into `ColumnDefault`
                if isinstance(default, sa.sql.schema.ColumnDefault):
                    default = default.arg

                # SqlAlchemy supports defaults that are: callable, SQL expressions
                if isinstance(default, (abc.Callable, sa.sql.ColumnElement, sa.sql.Selectable)):
                    default_provided = True
                # ignore `None` for non-nullable columns
                elif default is None and not attr.expression.nullable:
                    default_provided = False
                else:
                    default_provided = True

                fields[name] = FieldInfo(
                    name=name,
                    type=None,  # not implemented
                    required=not default_provided,
                    nullable=col.nullable,
                    aliases={col.name} if col.name != name else set(),
                )
            elif jessiql.sainfo.relations.is_relation(attr) and rels:
                fields[name] = FieldInfo(
                    name=name,
                    type=None,  # not implemented
                    required=False,
                    nullable=attr.expression.nullable,
                )

        # Properties
        if props:
            for name, prop in jessiql.sainfo.properties.get_all_model_properties(model).items():
                fields[name] = FieldInfo(
                    name=name,
                    type=None,  # not implemented
                    required=False,
                    nullable=None,
                )

        return ModelInfo(fields=fields)


try:
    import graphql
except ImportError:
    pass
else:
    @match.register(lambda v: isinstance(v, graphql.GraphQLObjectType))
    def match_graphql_type(model: graphql.GraphQLObjectType, filter: callable = None, *, snakes: bool = False) -> ModelInfo:
        """ Match: GraphQL Object type """
        return ModelInfo(fields={
            name: FieldInfo(
                name=name,
                type=None,  # not implemented
                required=None,  # right?
                nullable=graphql.is_nullable_type(field.type),
            )
            for name, field in model.fields.items()
            if filter_by_predicate(name, filter)
        })


    @match.register(lambda v: isinstance(v, graphql.GraphQLInputObjectType))
    def match_graphql_input_type(model: graphql.GraphQLInputObjectType, filter: callable = None, *, snakes: bool = False) -> ModelInfo:
        """ Match: GraphQL Input type """
        return ModelInfo(fields={
            name: FieldInfo(
                name=name,
                type=None,  # not implemented
                required=field.default_value is not None,
                nullable=graphql.is_nullable_type(field.type),
            )
            for name, field in model.fields.items()
            if filter_by_predicate(name, filter)
        })


def _is_typing_optional(t: type):
    """ Given a type annotation, see if has the `Optional[]` wrapper """
    return get_origin(t) is Union and type(None) in get_args(t)
