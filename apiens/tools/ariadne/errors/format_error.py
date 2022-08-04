import ariadne
import graphql
from apiens.error import exc
from apiens.tools.graphql.errors.error_extensions import add_graphql_error_extensions


def application_error_formatter(error: graphql.GraphQLError, debug: bool = False, *, BaseApplicationError = exc.BaseApplicationError) -> dict:
    """ Error formatter. Add Error Object for application errors

    When `debug` is set, it will return an error dict that also has a reference to the original Exception object.
    """
    error = add_graphql_error_extensions(error, debug, BaseApplicationError=BaseApplicationError)
    error_dict = ariadne.format_error(error, debug)
    return error_dict
