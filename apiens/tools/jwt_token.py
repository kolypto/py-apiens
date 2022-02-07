from __future__ import annotations

import pydantic as pd
from datetime import timedelta, datetime
from functools import cached_property
from typing import Optional, Any, ClassVar, Generic, TypeVar

from jose import jwt  # type: ignore[import]


SubjectT = TypeVar('SubjectT')


class JWTToken(pd.BaseModel, Generic[SubjectT]):
    """ Base JWT token

    It's a "thing" that has validation, expiration, and identifies someone.
    """
    # Encryption algorithm
    ALGORITHM: ClassVar[str] = 'HS256'

    # Encryption key used for JWT. Secret!
    SECRET_KEY: ClassVar[str]

    # Subject: whom the token refers to
    sub: SubjectT
    # Expires: when the token is no longer valid
    exp: datetime
    # Not before: don't accept before this date
    nbf: Optional[datetime]
    # Issued at: to tell the token's age
    iat: Optional[datetime]
    # Unique token id: to prevent replays
    jti: Any

    @classmethod
    def create(cls,
               subject: SubjectT,
               expires: timedelta = None,
               **extra
               ):
        """ Create a signed JWT token: a "thing" that identifies an authenticated user

        Args:
            subject: an arbitrary user identifier. E.g. "id=10" or "login=stark"
            expires: when will the token expire
            extra: any custom data you might want to put into the token
        Raises:
            jwt.JWTError: (unlikely) cases or errors when encoding the data
        """
        # Can't use any of the reserved claims as custom fields
        assert not (set(extra) & JWT_RESERVED_CLAIMS)

        # Token object
        return cls(
            # JWT fields:
            sub=subject,  # subject
            exp=(datetime.utcnow() + expires) if expires else None,  # expiration
            # nbf=datetime.utcnow() + ...,  # not before
            # iat=datetime.utcnow(),  # issued at
            # jti=uuid,  # token id
            **extra  # custom claims (extra fields)
        )

    @classmethod
    def decode(cls, token: str):
        """ Decode & validate a user-supplied authentication token

        Raises:
            jwt.JWTError: If the signature is invalid in any way.
            jwt.ExpiredSignatureError: signature has expired (subclass).
            jwt.JWTClaimsError: any claim is invalid (subclass).
            pydantic.ValidationError: token contents is malformed (unlikely)
        """
        payload = jwt.decode(
            token,
            cls.SECRET_KEY,
            algorithms=[cls.ALGORITHM]
        )
        return cls(**payload)

    @property
    def expires_in(self) -> int:
        """ The number of seconds the token will expire in """
        return int((self.exp - datetime.utcnow()).total_seconds())

    def encode(self) -> str:
        """ Encode the token into a string """
        return jwt.encode(
            self.dict(exclude_unset=True),
            self.SECRET_KEY,
            algorithm=self.ALGORITHM
        )

    def as_headers(self) -> dict:
        """ Encode the token as an HTTP header, tuple """
        return {"Authorization": f"Bearer {self.encode()}"}

    class Config:
        # @cached_property won't currently work
        # https://github.com/samuelcolvin/pydantic/issues/1241
        keep_untouched = (cached_property,)


# Reserved claims.
# Be careful not to use any of those values accidentally
JWT_RESERVED_CLAIMS = frozenset(('iss', 'sub', 'aud', 'exp', 'nbf', 'iat', 'jti'))
