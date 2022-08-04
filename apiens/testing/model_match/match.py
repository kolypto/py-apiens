from collections import abc
import dataclasses
from typing import TypedDict, Any, Union
from typing import get_args, get_origin, get_type_hints

try:
    from typing import is_typeddict
except ImportError:
    # TODO: remove them Python 3.10 is the minimal version for apiens
    def is_typeddict(t):  # type: ignore[misc]
        return isinstance(t, type) and issubclass(t, dict) and hasattr(t, '__total__')

from .model_info import ModelInfo, FieldInfo
from .predicates import filter_by_predicate, PredicateFn
from .singledispatch_lambda import singledispatch_lambda


@singledispatch_lambda().decorator
def match(model: Union[type, Any], filter: PredicateFn = None) -> ModelInfo:
    """ Convert an object into a dict for matching

    Given an object (a typed dict, a dataclass, a pydantic model, an sqlalchemy model, graphql type),
    it will convert it into a ModelInfo dict that can be used for matching.
    """
    raise NotImplementedError(f'Object of type {model} is not supported')


@match.register(is_typeddict)
def match_typed_dict(model: type[dict], filter: PredicateFn = None) -> ModelInfo:
    """ Match: TypedDict """
    return ModelInfo(fields={
        name: FieldInfo(
            name=name,
            type=None, #str(type??),  # not implemented yet
            required=name in model.__required_keys__,  # type: ignore[attr-defined]
            nullable=_is_typing_optional(type),
        )
        for name, type in get_type_hints(model).items()
        if filter_by_predicate(name, filter)
    })


@match.register(dataclasses.is_dataclass)
def match_dataclass(model: type, filter: PredicateFn = None) -> ModelInfo:
    """ Match: @dataclass """
    field: dataclasses.Field
    return ModelInfo(fields={
        field.name: FieldInfo(
            name=field.name,
            type=None,  # not implemented yet
            required=field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING,  # type: ignore[misc]
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
    def match_pydantic_model(model: pd.BaseModel, filter: PredicateFn = None) -> ModelInfo:
        """ Match: Pydantic model """
        field: pd.fields.ModelField
        return ModelInfo(fields={
            field.name: FieldInfo(
                name=field.name,
                type=None,  # not implemented
                required=None if field.required is pd.fields.Undefined else field.required,  # type: ignore[arg-type]
                nullable=field.allow_none,
                aliases={field.alias} if field.alt_alias else set(),
            )
            for field in model.__fields__.values()
            if filter_by_predicate(field.name, filter)
        })

try:
    import sqlalchemy as sa
    import sqlalchemy.orm.base
    from apiens.tools.sqlalchemy import sainfo
except ImportError:
    pass
else:
    @match.register(lambda v: sa.orm.base.manager_of_class(v) is not None)
    def match_sqlalchemy_model(model: type, filter: PredicateFn = None, *, props: bool = True, rels: bool = True) -> ModelInfo:
        """ Match: SqlAlchemy model """
        mapper: sa.orm.Mapper = sa.orm.class_mapper(model)

        fields = {}

        # Columns, Relations
        for name, attr in mapper.all_orm_descriptors.items():
            if not filter_by_predicate(name, filter):
                continue

            if sainfo.columns.is_column(attr):
                col: sa.Column = attr.expression

                if sainfo.columns.is_column_property(attr):
                    default = attr.default

                    # SqlALchemy likes to wrap it into `ColumnDefault`
                    if isinstance(default, sa.sql.schema.ColumnDefault):
                        default = default.arg

                    # SqlAlchemy supports defaults that are: callable, SQL expressions
                    if isinstance(default, (abc.Callable, sa.sql.ColumnElement, sa.sql.Selectable)):  # type: ignore[arg-type]
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
                elif sainfo.columns.is_column_expression(attr):
                    fields[name] = FieldInfo(
                        name=name,
                        type=None,  # not implemented
                        required=False,
                        nullable=True,  # everything's possible. Let's be lax
                        aliases={col.name} if col.name != name else set(),
                    )
                elif sainfo.columns.is_composite_property(attr):
                    fields[name] = FieldInfo(
                        name=name,
                        type=None,  # not implemented
                        required=False,
                        nullable=False,  # composite properties do not support NULLs
                        aliases={col.name} if col.name != name else set(),
                    )
                else:
                    raise NotImplementedError
            elif sainfo.relations.is_relation(attr) and rels:
                # TO-MANY relationships are not nullable. They're lists.
                if attr.property.uselist:
                    nullable = False
                # TO-ONE relationships may be nullable if the FK is nullable
                else:
                    nullable = any((
                        local_col.nullable == True or remote_col.nullable == True
                        for local_col, remote_col in attr.property.local_remote_pairs
                    ))

                fields[name] = FieldInfo(
                    name=name,
                    type=None,  # not implemented
                    required=False,
                    nullable=nullable,
                )
            elif isinstance(attr, sa.ext.hybrid.hybrid_property):
                # Will be handled in the properties section down below
                pass
            # These types are not implemented
            # elif isinstance(attr, sa.ext.associationproxy.AssociationProxyInstance):
            #     pass
            # elif isinstance(attr, sa.ext.hybrid.hybrid_method):
            #     pass
            # else:
            #     raise NotImplementedError(type(attr))

        # Properties
        if props:
            for name, prop in sainfo.properties.get_all_model_properties(model).items():
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
    def match_graphql_type(model: graphql.GraphQLObjectType, filter: PredicateFn = None) -> ModelInfo:
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
    def match_graphql_input_type(model: graphql.GraphQLInputObjectType, filter: PredicateFn = None) -> ModelInfo:
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
