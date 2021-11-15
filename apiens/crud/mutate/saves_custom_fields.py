from __future__ import annotations

from apiens.structure.func import decomarker


class saves_custom_fields(decomarker):
    """ A decorator that marks a method that customizes the saving of certain fields, e.g. relationships.

    It's not safe to *just* let users save relationships and some other fields.
    With the help of this decorator, they are plucked out of the input and handled manually by your function.

    Example:
        ABSENT = object()

        class UserCrud(CrudBase):
            ...
            @saves_custom_fields('articles')
            def save_articles(self, /, new: User, prev: User = None, *, articles = ABSENT):
                if articles is not ABSENT:
                    ...  # custom article-saving logic

    You can use it to save any attributes that require custom behavior, not just relationships.

    The arguments are:

    * new: The instance that is being created/modified
    * prev: The unmodified versions of this instance (only during update())
    * **fields: the values of the fields that you have asked for

    Note that this method is called always, even if no `**fields` have actually been provided.
    """
    # The list of fields that this method is capable of saving.
    field_names = tuple[str, ...]

    def __init__(self, *field_names: str):
        """ Decorate a method that can save custom fields

        Args:
            *field_names: List of field names that it handles
        """
        super().__init__()
        self.field_names = field_names

    @classmethod
    def save(cls, crud: object, plucked_data: dict[saves_custom_fields, dict], new: object, prev: object = None):
        for handler, kwargs in plucked_data.items():
            handler.func(crud, new, prev, **kwargs)

    @classmethod
    def pluck_custom_fields(cls, crud: object, input_dict: dict) -> dict[saves_custom_fields, dict]:
        """ Given an `input_dict`, pluck all custom fields and stash them

        Args:
            crud: The Crud handler
            input_dict: The input dictionary to pluck the values from

        Returns:
            a mapping that will soon be used to call custom fields' handlers.
            It contains: { saves_custom_fields handelr => method kwargs }
        """
        ret = {}
        remove_fields = set()

        # Go through every handler
        for handler in cls.all_decorated_from(type(crud)):
            # For every handler, collect arguments from the dict
            ret[handler] = {
                # NOTE: if an argument has not been provided, use `ABSENT`
                # We don't use `None` to differentiate from a `None` provided by the user
                field_name: input_dict.get(field_name)
                for field_name in handler.field_names
                if field_name in input_dict
            }

            # Remember the fields to remove
            remove_fields.update(handler.field_names)

        # Remove the fields from the dict
        for remove_field in remove_fields:
            if remove_field in input_dict:
                del input_dict[remove_field]

        # Done
        return ret

    @classmethod
    def all_field_names_from(cls, CrudClass: type) -> set[str]:
        """ Get the names of all custom fields """
        return set().union(*(
            handler.field_names
            for handler in cls.all_decorated_from(CrudClass)
        ))
