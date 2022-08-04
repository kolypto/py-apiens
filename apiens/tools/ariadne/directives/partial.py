import ariadne
import graphql


# See this module for the docs
from apiens.tools.graphql.directives import partial

# Directive definition. As a string.
DIRECTIVE_SDL = partial.DIRECTIVE_SDL

# Directive name
DIRECTIVE_NAME = partial.DIRECTIVE_NAME


class PartialDirective(ariadne.SchemaDirectiveVisitor):
    """ Directive @partial: partial input type with skippable fields """
    def visit_input_object(self, object_: graphql.GraphQLInputObjectType) -> graphql.GraphQLInputObjectType:
        partial.installto_input_object_type(self.schema, object_)
        return object_
