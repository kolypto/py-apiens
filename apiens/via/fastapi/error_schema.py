""" Schemas for the Error response """
import pydantic as pd
from typing import Optional

from apiens.errors import BaseApplicationError


class ErrorObject(pd.BaseModel):
    """ Object representing an API error """
    # Generic fields
    name: str = pd.Field(...,
                         title='Error class name.',
                         description='Use it in your code to handle different error conditions.')

    title: str = pd.Field(...,
                          title='A generic descriptive message',
                          description='Not for the user, but for the developer')
    httpcode: int = pd.Field(...,
                             title='HTTP error code')

    # Specific error data
    error: str = pd.Field(...,
                          title='Error message for the user',
                          description='Negative side: what has gone wrong')
    fixit: str = pd.Field(...,
                          title='Suggested action for the user',
                          description='Positive side: what the user is supposed to do')
    info: dict = pd.Field(...,
                          title='Additional information',
                          description='Structured information about the error')

    # Debug information
    debug: Optional[dict] = pd.Field(...,
                                     title='Additional debug information',
                                     description='Only available in non-production mode')

    @classmethod
    def from_exception(cls, e: BaseApplicationError, include_debug_info: bool):
        """ Create the `ErrorObject` from a Python exception """
        return cls(
            name=e.name,
            title=str(e.title),
            httpcode=e.httpcode,
            error=str(e.error),
            fixit=str(e.fixit),
            info=e.info,
            debug=None if include_debug_info else e.debug,
        )


class ErrorResponse(pd.BaseModel):
    """ Error response as returned by the API """
    error: ErrorObject

    @classmethod
    def from_exception(cls, e: BaseApplicationError, include_debug_info: bool):
        """ Create the `ErrorResponse` from a Python exception """
        return ErrorResponse(error=ErrorObject.from_exception(e, include_debug_info=include_debug_info))
