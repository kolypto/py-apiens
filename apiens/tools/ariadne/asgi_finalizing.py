from collections import abc

from starlette.requests import Request
from starlette.responses import Response
from starlette.websockets import WebSocket
from ariadne.asgi import GraphQL

from apiens.error.error_object.python import GraphqlResponseErrorObject
from apiens.tools.graphql.errors.error_convert import convert_to_graphql_application_error


# TODO: rewrite this class: it should finalize -- not a request, but a context.
#   This will be more directly applicable to websockets where one request may have multiple contexts:
#   a context is started for every subscription! And we must keep track of them and close them separately.
#   At the moment, this class may leak contexts when multiple subscriptions are used with one websocket.

class FinalizingGraphQL(GraphQL):
    """ GraphQL app that can do clean-up after a request

    Typical use: initialize a context for your GraphQL api, then implement a clean-up procedure in `finalize_request()`.

    Rationale: the original `ariadne.GraphQL` provides no way to clean-up after a request

    NOTE: this class inherits from Ariadne and heavily depends on its specific version! Only compatible with ariadne >= 0.15
    """
    async def finalize_request(self, request: Request) -> tuple[bool, abc.Iterable[Exception]]:
        """ Do clean-up after a request is over with

        NOTE: in order to finalize a context, use this storage place:
        > request.state.graphql_context = context
        or override the get_context_for_request() method

        NOTE: this function is run even when context_provider() function has failed.
        As a result, some stuff may be missing.

        NOTE: this function should never fail. It should report its errors as a list.

        Returns:
            is_fatal: do we have a fatal error in the result?
            errors: additional errors to add to the response
        """
        return False, ()

    async def finalize_successful_response(self, request: Request, response: Response) -> Response:
        """ Finalize a successful JSON response

        This method is executed when a GraphQL response is already rendered
        as a JSONResponse object. Note that the JSON dict is already made into bytes.
        """
        return response

    async def create_json_response(self, request: Request, result: dict, success: bool) -> Response:
        # Finalize request: let the user perform some post-request clean-up
        is_fatal, errors = await self.finalize_request(request)

        # Errors during clean-up? Add them to the response
        if errors:
            self._add_errors_to_result(result, errors, is_fatal=is_fatal, where='after-request')

        # Done
        return await super().create_json_response(request, result, success)

    async def graphql_http_server(self, request: Request) -> Response:
        # Get the response
        try:
            # It will call create_json_response() which will finalize the request.
            response = await super().graphql_http_server(request)
        except Exception as e:
            # GraphQL will consume all errors, but will raise context value provider exceptions
            # which we catch and report as "before-request" exceptions and report
            # as empty, fatal, response
            result = {'data': None}
            self._add_errors_to_result(result, [e], is_fatal=True, where='before-request')

            # Return the result.
            # GraphQL reports every successful result as 200 and every client error as 400
            return await self.create_json_response(request, result, success=True)

        # If everything went well, finalize the request as successful
        # This may add headers, data fields, etc
        response = await self.finalize_successful_response(request, response)

        # Done
        return response

    async def websocket_server(self, websocket: WebSocket) -> None:
        # Do your thing, websocket
        try:
            await super().websocket_server(websocket)
        # Clean-up the context after it's disconnected.
        # Note that errors are not reported! This is not too good, but because subscriptions are typically read-only,
        # we don't worry much about errors that might happen when the user disconnects.
        # TODO: use separate start_websocket_operation() and stop_websocket_operation()
        # TODO: find a way to report errors to the client while the socket it still connected, but going to disconnect.
        #   For instance, use stop_websocket_operation() and start_websocket_operation() with operation-local contexts?
        finally:
            await self.finalize_request(websocket)  # type: ignore[arg-type]

    def _add_errors_to_result(self, result: dict, errors: abc.Iterable[Exception], *, is_fatal: bool, where: str):
        """ Add exceptions to the response

        Args:
            result: The GraphQL result to add the errors to
            errors: Python Exceptions to add
            is_fatal: Was any of the exceptions fatal (i.e. renders the response invalid)?
            where: Identifier of the place where the code has failed. E.g. "after-request".
        """
        # Fatal errors?
        if is_fatal:
            # Do not report any result. That's a complete failure
            result['data'] = None

        # Report additional errors
        result.setdefault('errors', [])
        result['errors'].extend([
            self._format_additional_exception(error, where=where)
            for error in errors
        ])

    def _format_additional_exception(self, error: Exception, *, where: str) -> GraphqlResponseErrorObject:
        """ Convert an exception into a GraphQL error

        This function is used to present errors that happened before (or after) a GraphQL request in GraphQL format
        """
        error = convert_to_graphql_application_error(error)
        formatted_error: GraphqlResponseErrorObject = self.error_formatter(error, self.debug)  # type: ignore[assignment]
        formatted_error.setdefault('extensions', {})
        formatted_error['extensions']['where'] = where
        return formatted_error
