from collections import abc
from typing import Optional

from ariadne import SchemaDirectiveVisitor
from graphql import GraphQLField, GraphQLResolveInfo


class WrapperDirective(SchemaDirectiveVisitor):
    """ Implement a directive that simply wraps the field resolver with custom logic

    Example:
        class AuthenticatedDirective(WrapperDirective):
            def resolve(self, root, info: ResolveInfo, /, **kwargs):
                if not info.context.authenticated:
                    raise NotAuthenticated()
                return super().resolve(root, info, **kwargs)
    """

    # The original resolver found on the field.
    # Call it from your resolve()
    original_resolver: abc.Callable

    def resolve(self, root, info: GraphQLResolveInfo, /, **kwargs):
        """ Wrapper for the original resolve() function defined on the field.

        Override this function to have custom logic executed before, or after, the resolver.
        """
        return self.original_resolver(root, info, **kwargs)

    def visit_field_definition(self, field, object_type) -> GraphQLField:
        # * Back up the original resolver into `self.original_resolver`;
        # * Set our custom self.resolve() as the new resolver

        # This `field.resolve` might be `None` when a default resolver is assumed.
        # Ariadne suggests that we use `field resolve or graphql.default_resolver`, but we'll try to avoid doing so
        # because it might block the `snake_case_fallback_resolvers()` from being installed in schema.py.
        # If this line ever fails, then perhaps we'll have to do as Ariadne docs suggest.
        # Link: https://ariadnegraphql.org/docs/schema-directives
        assert field.resolve is not None

        # Remember the original resolve function
        self.original_resolver = field.resolve  # type: ignore[assignment]

        # Use our self.resolve() instead
        field.resolve = self.resolve

        # Done
        return field
