from functools import wraps
from typing import Optional, Union

from ariadne import SchemaDirectiveVisitor
from graphql import GraphQLField, GraphQLResolveInfo
from graphql import GraphQLObjectType, GraphQLInterfaceType
from graphql import GraphQLFieldResolver


class WrapperDirective(SchemaDirectiveVisitor):
    """ Implement a directive that simply wraps the field resolver with custom logic

    NOTE: for subscriptions, it wraps the subscriber method instead, but uses the same function for your convenience.
    If this is not convenient, add the `WrapsSubscription` mixin.

    Example:
        class AuthenticatedDirective(WrapperDirective):
            def resolve(self, root, info: ResolveInfo, /, **kwargs):
                if not info.context.authenticated:
                    raise NotAuthenticated()
                return super().resolve(root, info, **kwargs)
    """

    # The original resolver found on the field.
    # Call it from your resolve()
    original_resolver: Optional[GraphQLFieldResolver]

    def resolve(self, root, info: GraphQLResolveInfo, /, **kwargs):
        """ Wrapper for the original resolve() function defined on the field.

        Override this function to have custom logic executed before, or after, the resolver.
        """
        return self.original_resolver(root, info, **kwargs)  # type: ignore[misc]

    def visit_field_definition(self, field: GraphQLField, object_type: Union[GraphQLObjectType, GraphQLInterfaceType]) -> GraphQLField:  # type: ignore[return]
        # We have two kinds of fields:
        # * subscriptions. Will have both `field.resolve` and `field.subscribe`
        # * queries. Will have `field.resolve` but not `field.subscribe`
        # In case of a subscription, we wrap the subscription, not the resolver!

        if field.subscribe is not None:
            # Use a separate method for subscriptions
            if isinstance(self, WrapsSubscription):
                self.original_subscriber = _replace_resolver(field, 'subscribe', self.subscribe)
            # Use the same method for resolvers and subscriptions
            else:
                self.original_resolver = _replace_resolver(field, 'subscribe', self.resolve)
        elif field.resolve is not None:
            self.original_resolver = _replace_resolver(field, 'resolve', self.resolve)
        else:
            raise AssertionError(f'{object_type}.{field} has no resolver')  #

class WrapsSubscription:
    """ A mixin for "WrapperDirective" that makes it use a separate function for subscriptions

    This separate function is async and may be convenient in async contexts
    """
    # The original resolver found on the field.
    # Call it from your resolve()
    original_subscriber: Optional[GraphQLFieldResolver]

    async def subscribe(self, root, info: GraphQLResolveInfo, /, **kwargs):
        """ Wrapper for the original resolve() function defined on the field.

        Override this function to have custom logic executed before, or after, the resolver.
        """
        return self.original_subscriber(root, info, **kwargs)  # type: ignore[misc]


def _replace_resolver(field: GraphQLField, attr_name: str, replacement_method: GraphQLFieldResolver):
    # This `field.resolve` might be `None` when a default resolver is assumed.
    # Ariadne suggests that we use `field resolve or graphql.default_resolver`, but we'll try to avoid doing so
    # because it might block the `snake_case_fallback_resolvers()` from being installed in schema.py.
    # If this line ever fails, then perhaps we'll have to do as Ariadne docs suggest.
    # Link: https://ariadnegraphql.org/docs/schema-directives
    assert getattr(field, attr_name) is not None

    # Remember the original function
    original_resolver = getattr(field, attr_name)

    # Use our self.resolve() instead
    # Make sure it's properly wrapped -- so that any decorators applied to the original function are visible through us.
    # This is especially important for @resolves_in_threadpool and @resolves_nonblocking
    @wraps(original_resolver)
    def wrapped_resolver(root, info, /, **kwargs):
        return replacement_method(root, info, **kwargs)

    # Assign this resolver
    setattr(field, attr_name, wrapped_resolver)

    # Return the original method
    return original_resolver