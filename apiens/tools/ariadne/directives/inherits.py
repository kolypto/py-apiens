import ariadne
import graphql


# See this module for the docs
from apiens.tools.graphql.directives import inherits

# Directive definition. As a string.
DIRECTIVE_SDL = inherits.DIRECTIVE_SDL

# Directive name.
DIRECTIVE_NAME = inherits.DIRECTIVE_NAME


class InheritsDirective(ariadne.SchemaDirectiveVisitor):
    """ Directive @inherits: inherit fields from another type """
    def visit_object(self, object_: graphql.GraphQLObjectType) -> graphql.GraphQLObjectType:
        inherits.installto_object_type(self.schema, object_)
        return object_

    def visit_input_object(self, object_: graphql.GraphQLInputObjectType) -> graphql.GraphQLInputObjectType:
        inherits.installto_input_object_type(self.schema, object_)
        return object_
