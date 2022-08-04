""" Derived models for Pydantic: generate models based on other models """

from collections import abc
from typing import Optional, Any

import pydantic as pd


def derive_model(model: type[pd.BaseModel],
                 name: Optional[str] = None,
                 module: Optional[str] = None, *,
                 include: abc.Iterable[str] = None,
                 exclude: abc.Iterable[str] = None,
                 BaseModel: type[pd.BaseModel] = None,
                 extra_fields: dict[str, Any] = None,
                 ) -> type[pd.BaseModel]:
    """ Derive a Pydantic model by including/excluding fields

    Args:
        model: Pydantic model to derive from
        name: Name for the new model. None: get from the old model
            Note that in some cases non-unique model names may lead to errors. Try to provide a good one.
        module: __name__ of the module.
            Only important in cases where you want models to have globally unique names.
        include: The list of fields to include into the resulting model. All the rest will be excluded.
        exclude: The list of fields to exclude from the resulting model. All the rest will be included.
        BaseModel: the base to use
        extra_fields: extra fields to add. They will override existing ones.
    """
    assert bool(include) != bool(exclude), 'Provide `include` or `exclude` but not both'

    # Prepare include list
    include_fields = set(include) if include else (set(model.__fields__) - set(exclude or ()))

    # Fields
    fields = prepare_fields_for_create_model(
        field
        for field in model.__fields__.values()
        if field.name in include_fields
    )

    # Add/override extra fields
    fields.update(extra_fields or {})

    # Default: `BaseModel` comes from the model itself
    if BaseModel is None:
        BaseModel = empty_model_subclass(model, f'{model.__name__}Derived')

    # Derive a model
    return pd.create_model(  # type: ignore[call-overload]
        name or model.__name__,
        __module__=module or model.__module__,  # will this work?
        __base__=BaseModel,
        **fields
    )


def derive_optional(model: type[pd.BaseModel],
                    name: Optional[str] = None,
                    module: Optional[str] = None, *,
                    include: abc.Iterable[str] = None,
                    exclude: abc.Iterable[str] = None,
                    BaseModel: type[pd.BaseModel] = None,
                    ) -> type[pd.BaseModel]:
    """ Derive a Pydantic model by making some fields optional """



def merge_models(name: str,
                 *models: type[pd.BaseModel],
                 module: Optional[str] = None,
                 BaseModel: type[type[pd.BaseModel]] = None,
                 Config: Optional[type] = None,
                 extra_fields: dict[str, Any] = None,
                 ):
    """ Create a new Pydantic model by merging the fields of several models """
    # Collect fields
    fields = prepare_fields_for_create_model(
        field
        for model in models
        for field in model.__fields__.values()
    )

    # Add/override extra fields
    fields.update(extra_fields or {})

    # Create a model
    return pd.create_model(  # type: ignore[call-overload]
        name,
        __module__=module or models[0].__module__,  # same module by default
        __config__=Config,
        __base__=BaseModel,
        **fields
    )


def empty_model_subclass(Model: type[pd.BaseModel], name: str) -> type[pd.BaseModel]:
    """ Create a subclass of Model that will inherit none of the fields """
    return type(
        name,
        # Subclass the base model
        (Model,),
        # Reset the list of fields.
        # This is necessary so as not to inherit any fields from the base model
        {'__fields__': {}},
    )


def prepare_fields_for_create_model(fields: abc.Iterable[pd.fields.ModelField]) -> dict[str, tuple[type, pd.fields.FieldInfo]]:
    return {
        field.name: (
            field.outer_type_ if field.required else Optional[field.type_],
            field.field_info
        )
        for field in fields
    }
