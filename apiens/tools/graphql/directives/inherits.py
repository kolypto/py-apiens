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
from copy import copy
from typing import TypedDict, Union

import graphql

from apiens.tools.graphql.ast import has_directive


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
    _installto_type_or_input(schema, type_def)


def installto_input_object_type(schema: graphql.GraphQLSchema, type_def: graphql.GraphQLInputObjectType):
    """ Low-level: install the directive onto an object """
    _installto_type_or_input(schema, type_def)


def _installto_type_or_input(schema: graphql.GraphQLSchema, type_def: Union[graphql.GraphQLObjectType, graphql.GraphQLInputObjectType]):
    assert isinstance(type_def, (graphql.GraphQLObjectType, graphql.GraphQLInputObjectType))
    if not has_directive(DIRECTIVE_NAME, type_def.ast_node):
        return

    # Directive
    directive_def = schema.get_directive(DIRECTIVE_NAME)
    args: DirectiveArgs = graphql.get_directive_values(directive_def, type_def.ast_node, variable_values={})

    # Parent type
    parent_type: Union[graphql.GraphQLObjectType, graphql.GraphQLInputObjectType] = schema.get_type(args['type'])
    if not parent_type:
        raise ValueError(f"Unknown type: {args['type']}")

    # Cross-type inheritance
    inherit_field = get_field_inheritor(parent_type, type_def)

    # Copy all fields from parent
    # This is a mutable mapping. We can modify it.
    fields = type_def.fields
    for name, field in parent_type.fields.items():
        if name not in fields:
            fields[name] = inherit_field(field)

    # Fix AST
    if False:  # CHECKME: no need to fix the AST...
        pass


def install_directive_to_schema(schema: graphql.GraphQLSchema):
    """ Low-level: shortcut: install directive into a GraphQL schema """
    # Install onto InputObject types
    for type_name, type_def in schema.type_map.items():
        if isinstance(type_def, graphql.GraphQLObjectType):
            installto_object_type(schema, type_def)
        elif isinstance(type_def, graphql.GraphQLInputObjectType):
            installto_input_object_type(schema, type_def)


def get_field_inheritor(parent_type: Union[graphql.GraphQLObjectType, graphql.GraphQLInputObjectType],
                        child_type: Union[graphql.GraphQLObjectType, graphql.GraphQLInputObjectType]):
    """ Get a function that will properly inherit a field from one type to another

    The thing is: if you inherit a field from `type` to `type`, or from `input` to `input`, it works fine.
    But if you try to inherit an `input` from a `type`, it turns out that there is a field mismatch:
    e.g. a `type` has a resolver, but an `input` has a default value.

    This "inheritor" function will choose the right way to convert from the one to the other.
    """
    parent_is_type = isinstance(parent_type, graphql.GraphQLObjectType)
    parent_is_input = isinstance(parent_type, graphql.GraphQLInputObjectType)
    child_is_type = isinstance(child_type, graphql.GraphQLObjectType)
    child_is_input = isinstance(child_type, graphql.GraphQLInputObjectType)

    # Check: either type or input, nothing else
    assert parent_is_type != parent_is_input
    assert child_is_type != child_is_input

    # Choose how to copy
    if (parent_is_type and child_is_type) or (parent_is_input and child_is_input):
        return _inherit_field__copy
    elif parent_is_type and child_is_input:
        return _inherit_field__type_to_input
    elif parent_is_input and child_is_type:
        return _inherit_field__input_to_type
    else:
        raise NotImplementedError


def _inherit_field__copy(field):
    return copy(field)


def _inherit_field__type_to_input(field: graphql.GraphQLField) -> graphql.GraphQLInputField:
    return graphql.GraphQLInputField(
        type_=field.type,
        # default_value=graphql.Undefined,  # the default
        description=field.description,
        deprecation_reason=field.deprecation_reason,
        extensions=field.extensions,
        ast_node=graphql.language.ast.InputValueDefinitionNode(
            name=field.ast_node.name,
            description=field.ast_node.description,
            type=field.ast_node.type,
            directives=field.ast_node.directives,
            default_value=None,
        ),
    )


def _inherit_field__input_to_type(field: graphql.GraphQLInputField) -> graphql.GraphQLField:
    return graphql.GraphQLField(
        type_=field.type,
        # default_value=graphql.Undefined,  # the default
        description=field.description,
        deprecation_reason=field.deprecation_reason,
        extensions=field.extensions,
        ast_node=graphql.language.ast.FieldDefinitionNode(
            name=field.ast_node.name,
            description=field.ast_node.description,
            type=field.ast_node.type,
            directives=field.ast_node.directives,
            arguments=[],
        ),
    )


'''
GraphQLField:
    type: "GraphQLOutputType"
    args: GraphQLArgumentMap
    resolve: Optional["GraphQLFieldResolver"]
    subscribe: Optional["GraphQLFieldResolver"]
    description: Optional[str]
    deprecation_reason: Optional[str]
    extensions: Optional[Dict[str, Any]]
    ast_node: Optional[FieldDefinitionNode]

GraphQLInputField:
    type: "GraphQLInputType"
    default_value: Any
    description: Optional[str]
    deprecation_reason: Optional[str]
    out_name: Optional[str]  # for transforming names (extension of GraphQL.js)
    extensions: Optional[Dict[str, Any]]
    ast_node: Optional[InputValueDefinitionNode]
'''


# Here's how to traverse the tree
# class DirectiveInstaller(graphql.Visitor):
#     def enter(self, node: graphql.Node, key: Optional[Union[str, int]], parent: Optional[graphql.Node],
#               path: list[Union[str, int]], ancestors: list[graphql.Node]):
#         when the type has directives, invoke directive installers
#
# for type_name, type_def in gql_schema.type_map.items():
#     graphql.visit(type_def.ast_node, DirectiveInstaller())
# visit the rest of the AST as well
