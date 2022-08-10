""" Generate short, url-friendly, identifiers """

import base64
from uuid import UUID  # shortcut


def uuid2shortid(uuid: UUID) -> str:
    """ Convert a UUID into a short id

    Under the hood, it's an urlsafe safe base64-encoded string [a-zA-Z0-9_-]

    Returns:
        A string of 22 ASCII characters: [a-zA-Z0-9_-]
    Example:
        'XFxL_QnATreb6V-89AdiCA'
    """
    # Encode to base64, convert bytes -> str, strip the padding ('==')
    return base64.urlsafe_b64encode(uuid.bytes).decode().rstrip('=')


def shortid2uuid(shortid: str) -> UUID:
    """ Convert a short id into a UUID """
    return UUID(bytes=base64.urlsafe_b64decode(shortid.encode() + b'=='))
