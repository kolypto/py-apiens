""" Partial objects for Pydantic

A partial object makes every field "skippable" (i.e. you can omit it),
but not "nullable" (i.e. you cannot assign `null`)
"""

import pydantic as pd
from pydantic.utils import lenient_issubclass


def partial(*fields):
    """ Make the object "partial": i.e. mark all fields as "skippable"

    In Pydantic terms, this means that they're not nullable, but not required either.

    Example:

        @partial
        class User(pd.BaseModel):
            id: int

        # `id` can be skipped, but cannot be `None`
        User()
        User(id=1)

    Example:

        @partial('id')
        class User(pd.BaseModel):
            id: int
            login: str

        # `id` can be skipped, but not `login`
        User(login='johnwick')
        User(login='johnwick', id=1)
    """
    # Call pattern: @partial class Model(pd.BaseModel):
    if len(fields) == 1 and lenient_issubclass(fields[0], pd.BaseModel):
        Model = fields[0]
        field_names = ()
    # Call pattern: @partial('field_name') class Model(pd.BaseModel):
    else:
        Model = None
        field_names = fields

    # Decorator
    def decorator(Model: type[pd.BaseModel] = Model, field_names: frozenset[str] = frozenset(field_names)):
        # Iter fields, set `required=False`
        for field in Model.__fields__.values():
            # All fields, or specific named fields
            if not field_names or field.name in field_names:
                field.required = False

        # Exclude unset
        # Otherwise non-nullable fields would have `{'field': None}` which is unacceptable
        dict_orig = Model.dict
        def dict_excludes_unset(*args, exclude_unset: bool = None, **kwargs):
            exclude_unset = True
            return dict_orig(*args, **kwargs, exclude_unset=exclude_unset)
        Model.dict = dict_excludes_unset  # type: ignore[assignment]

        # Done
        return Model

    # Call patterrn
    if Model is None:
        return decorator
    else:
        return decorator(Model)
