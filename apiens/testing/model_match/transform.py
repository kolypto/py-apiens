from __future__ import annotations

from collections import abc
from copy import copy
from typing import TYPE_CHECKING, Optional

from .model_info import ModelInfo, FieldInfo
from .predicates import filter_by_predicate, PredicateFn

if TYPE_CHECKING:
    from jessiql.query_object.rewrite import Rewriter, FieldContext


def select_fields(model_info: ModelInfo, filter: PredicateFn) -> ModelInfo:
    """ Get a new ModelInfo with fields selected by filter() """
    new_model_info = copy(model_info)
    new_model_info.fields = {
        name: field
        for name, field in model_info.fields.items()
        if filter_by_predicate(name, filter)
    }
    return new_model_info


def rename_fields_map(model_info: ModelInfo, renames: dict[str, str]) -> ModelInfo:
    """ Get a new ModelInfo with fields renamed according to the `rename` mapping

    Fields not present in the `renames` mapping will retain their names.

    Args:
        model_info: The source model
        renames: a mapping { old name => new name }
    """
    rename_by_mapping = lambda name: renames.get(name) or None
    return rename_fields_func(model_info, rename_by_mapping)


def rename_fields_func(model_info: ModelInfo, renamer: abc.Callable[[str], Optional[str]]):
    """ Get a new ModelInfo with fields renamed by renamer() callable

    If renamer() cannot rename a field, the field will retain its name.

    Args:
        model_info: The source model
        renamer: A function that gets the old name and converts it into a new name, or `None` to keep the field
    """
    def rename_by_func(field: FieldInfo) -> Optional[FieldInfo]:
        new_name = renamer(field.name)
        if new_name is not None:
            field.name = new_name
        return field

    return _transformed_fields(model_info, rename_by_func)


def jessiql_rewrite_api_to_db(model_info: ModelInfo, rewriter: Rewriter, *, context: FieldContext) -> ModelInfo:
    """ Get a new ModelInfo with fields renamed according to JessiQL rewriter

    Args:
        model_info: The source model
        rewriter: JessiQL Query Object rewriter for this model
    """
    rename_by_rewriter = lambda name: rewriter.api_to_db(name, context=context) or None
    return rename_fields_func(model_info, rename_by_rewriter)


def jessiql_rewrite_db_to_api(model_info: ModelInfo, rewriter: Rewriter) -> ModelInfo:
    """ Get a new ModelInfo with fields renamed according to JessiQL rewriter

    Args:
        model_info: The source model
        rewriter: JessiQL Query Object rewriter for this model
    """
    rename_by_rewriter = lambda name: rewriter.db_to_api(name) or None
    return rename_fields_func(model_info, rename_by_rewriter)



def _transformed_fields(model_info: ModelInfo, handler: abc.Callable[[FieldInfo], Optional[FieldInfo]]) -> ModelInfo:
    """ Create a new ModelInfo with fields transformed by handler()

    Args:
        model_info: ModelInfo object to copy from
        handler: A function to transform a field. If it returns None, the field is skipped
    """
    # Transform fields
    new_fields = (
        # Note: handler() may return `None` to skip fields
        handler(field)
        for field in model_info.fields.values()
    )

    # Create a new model info
    new_model_info = copy(model_info)
    new_model_info.fields = {
        field.name: field
        for field in new_fields
        if field is not None  # Skip some fields
    }

    # Done
    return new_model_info
