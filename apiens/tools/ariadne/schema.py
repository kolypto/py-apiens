import ariadne


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
    def resolver(*_):
        return nested

    parent.set_field(field_name, resolver)
