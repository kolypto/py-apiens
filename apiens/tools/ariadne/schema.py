import os.path
from types import ModuleType

import ariadne

from apiens.tools.ariadne.asgi import resolves_nonblocking


def register_nested_object(parent: ariadne.ObjectType, field_name: str, nested: ariadne.ObjectType):
    """ Utility to use nested query and mutation types

    Example:

        ```graphql
        type Query {
            nested: NestedQuery
        }

        type NestedQuery {
            ...
        }
        ```

        ```python
        Query = QueryType()
        NestedQuery = ObjectType('NestedQuery')

        register_nested_object(Query, 'nested', NestedQuery)
        ```

    See: https://github.com/mirumee/ariadne/issues/101#issuecomment-766999736
    """
    @resolves_nonblocking
    def resolver(*_):
        return nested

    parent.set_field(field_name, resolver)


def load_schema_from_module(module: ModuleType, filename: str = '') -> str:
    """ Given a Python module, load a graphql schema from a file in its path

    Example:
        load_schema_from_module(apiens.tools.ariadne, 'rich_validation.graphql')
    """
    return ariadne.load_schema_from_path(
        os.path.join(
            os.path.dirname(module.__file__),
            filename
        )
    )
