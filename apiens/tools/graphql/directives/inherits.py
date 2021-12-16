""" @inherits directive

Implements type inheritance: fields from parent types are copied over to child types

Example:
    type User {
        id: ID!
    }
    type UserLogin @inherits(type: "User") {
        login: String!
    }
"""
from typing import TypedDict

import graphql

from apiens.tools.graphql.ast import get_directive


# TODO: implement high-level bindings to Ariadne. Perhaps, rename the function like Ariadne's statis methods


# Directive name
DIRECTIVE_NAME = 'inherits'

# Directive definition
# language=graphql
DIRECTIVE_SDL = '''
directive @inherits (type: String) on OBJECT | INPUT_OBJECT
'''


class DirectiveArgs(TypedDict):
    # The type to inherit from
    type: str


# Directive implementation

def installto_object_type(schema: graphql.GraphQLSchema, type_def: graphql.GraphQLObjectType):
    assert isinstance(type_def, graphql.GraphQLObjectType)
    if not (directive := get_directive(DIRECTIVE_NAME, type_def.ast_node)):
        return

    directive_def = schema.get_directive(DIRECTIVE_NAME)
    args: DirectiveArgs = graphql.get_directive_values(directive_def, type_def.ast_node, variable_values={})
    parent_type: graphql.GraphQLObjectType = schema.get_type(args['type'])

    # Copy all fields from parent
    # TODO: this will fail the parent object has @inherits that didn't trigger yet. So currently, there is a limitation:
    #   parent objects have to go before child objects.
    #   Here's how to fix it: recursively update parents, install some sort of marker on them for reentrancy
    fields = type_def.fields
    for name, field in parent_type.fields.items():
        if name not in fields:
            fields[name] = field

    # Fix AST
    if False:  # CHECKME: no need to fix the AST...
        pass


def installto_input_object_type(schema: graphql.GraphQLSchema, type_def: graphql.GraphQLInputObjectType):
    """ Low-level: install the directive onto an object """
    assert isinstance(type_def, graphql.GraphQLInputObjectType)
    if not (directive := get_directive(DIRECTIVE_NAME, type_def.ast_node)):
        return

    directive_def = schema.get_directive(DIRECTIVE_NAME)
    args: DirectiveArgs = graphql.get_directive_values(directive_def, type_def.ast_node, variable_values={})
    parent_type: graphql.GraphQLObjectType = schema.get_type(args['type'])

    # Copy all fields from parent
    # This is a mutable mapping. We can modify it.
    fields = type_def.fields
    for name, field in parent_type.fields.items():
        if name not in fields:
            fields[name] = field


def install_directive_to_schema(schema: graphql.GraphQLSchema):
    """ Low-level: shortcut: install directive into a GraphQL schema """
    # Install onto InputObject types
    for type_name, type_def in schema.type_map.items():
        if isinstance(type_def, graphql.GraphQLObjectType):
            installto_object_type(schema, type_def)
        elif isinstance(type_def, graphql.GraphQLInputObjectType):
            installto_input_object_type(schema, type_def)


# Here's how to traverse the tree
# class DirectiveInstaller(graphql.Visitor):
#     def enter(self, node: graphql.Node, key: Optional[Union[str, int]], parent: Optional[graphql.Node],
#               path: list[Union[str, int]], ancestors: list[graphql.Node]):
#         when the type has directives, invoke directive installers
#
# for type_name, type_def in gql_schema.type_map.items():
#     graphql.visit(type_def.ast_node, DirectiveInstaller())
# visit the rest of the AST as well
