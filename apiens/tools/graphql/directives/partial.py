""" @partial directive

Implements partial input objects with skippable fields.

Example:

    input UserInput @partial {
        # All fields are NonNull, but in fact, they can be skipped.
        id: ID!
        login: String!
        name: String!
        age: Int
    }

Now you can submit the following objects:

    {}
    {'age': None}
    {'age': 33}
    {'age': 33, 'login': 'john'}

but you cannot submit

    {'login': None}

Note that this directive works exclusively on the server: it modifies types in such a way that clients see the result,
but clients do not see the directive.
"""
from typing import Any

import graphql

from apiens.tools.graphql.ast import has_directive
from apiens.tools.graphql.input_types import wraps_input_object_out_type


# Directive name
DIRECTIVE_NAME = 'partial'

# Directive definition
# language=graphql
DIRECTIVE_SDL = '''
directive @partial on INPUT_OBJECT
'''

# Directive implementation

def installto_input_object_type(schema: graphql.GraphQLSchema, type_def: graphql.GraphQLInputObjectType):
    """ Low-level: install the directive onto an object """
    assert isinstance(type_def, graphql.GraphQLInputObjectType)
    if not has_directive(DIRECTIVE_NAME, type_def.ast_node):
        return

    # Remember the list of fields that used to be non-null
    # CHECKME: this tooling might fail in case field names are rewritten
    non_null_names = set()

    # Fix field types
    # Unwrap NonNull from every field
    for field_name, field in type_def.fields.items():
        if graphql.is_non_null_type(field.type):
            # Unwrap NonNull
            field.type = graphql.get_nullable_type(field.type)

            # Remember the field by name. We'll fail if `Null` is provided.
            assert field_name == field.out_name or field.out_name is None
            assert field_name == field.ast_node.name.value
            non_null_names.add(field_name)

    # Fix AST
    if False:  # CHECKME: no need to fix the AST...
        # Unwrap NonNull from every field
        for field in type_def.ast_node.fields:
            if isinstance(field.type, graphql.NonNullTypeNode):
                field.type = field.type.type

        # Reset property cache
        try:
            del type_def.fields
        except AttributeError:
            pass

    # Wrap the resolver
    @wraps_input_object_out_type(type_def)
    def out_type(value: dict[str, Any], node=type_def.ast_node, non_null_names = frozenset(non_null_names)) -> dict:
        cannot_be_null = {
            k
            for k, v in value.items()
            if v is None and k in non_null_names
        }
        if cannot_be_null:
            raise graphql.GraphQLError(f"Fields must not be null: {', '.join(cannot_be_null)}", node)
        else:
            return value


def install_directive_to_schema(schema: graphql.GraphQLSchema):
    """ Low-level: shortcut: install directive into a GraphQL schema """
    # Install onto InputObject types
    for type_name, type_def in schema.type_map.items():
        if isinstance(type_def, graphql.GraphQLInputObjectType):
            installto_input_object_type(schema, type_def)
