from typing import Union, Any, Optional

import graphql


def has_directive(directive_name: str, node: Union[graphql.InputObjectTypeDefinitionNode, graphql.ObjectTypeDefinitionNode, Any]) -> bool:
    """ Check that a field has a specific directive on it

    Example:
        Query = schema.get_type('Query')
        assert has_directive(
            'authenticated',
            Query.fields['listUsers']
        )
    """
    if not node or not node.directives:
        return False

    return any(
        directive.name.value == directive_name
        for directive in node.directives
    )


def get_directive(directive_name: str, node: Union[graphql.InputObjectTypeDefinitionNode, graphql.ObjectTypeDefinitionNode, Any]) -> Optional[graphql.DirectiveNode]:
    """ Get a directive from a field by name """
    if not node or not node.directives:
        return None

    for directive in node.directives:
        if directive.name.value == directive_name:
            return directive
    else:
        return None
