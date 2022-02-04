from typing import Optional

import pydantic as pd

from .base import BaseApplicationError


class ErrorObject(pd.BaseModel):
    """ Object representing an API error """
    # Generic fields
    name: str = pd.Field(...,
                         title='Error class name.',
                         description='Error name: E_* for user errors, F_* for internal failures.')

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
                          description='Positive side: what the user can do to fix it')
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
            debug=e.debug if include_debug_info else None,
        )


class ErrorResponse(pd.BaseModel):
    """ Error response as returned by the API """
    error: ErrorObject

    @classmethod
    def from_exception(cls, e: BaseApplicationError, include_debug_info: bool):
        """ Create the `ErrorResponse` from a Python exception """
        return cls(error=ErrorObject.from_exception(e, include_debug_info=include_debug_info))
