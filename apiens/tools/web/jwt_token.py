from __future__ import annotations

import pydantic as pd
from datetime import timedelta, datetime, timezone
from functools import cached_property
from typing import Optional, Any, ClassVar, TypeVar

# NOTE: this is the "python-jose" library. It's up to date. Unlike "jose"; be careful!
from jose import jwt  # type: ignore[import]


class JWTToken(pd.BaseModel):
    """ Base JWT token

    It handles a subject string, expiration time, encoding and decoding.
    The class is a Pydantic model which enables validation.

    Suggestion: better use StructuredJWTToken :)

    Example:
    >>> class APIAccessToken(JWTToken):
    >>>     SECRET_KEY = b'abcdef'
    >>>     sub: str = pd.Field(..., regex=r'session:id=(.+)$')
    >>>     
    >>>     @cached_property
    >>>     def session_id(self) -> UUID:
    >>>         assert self.sub.startswith('session:id')
    >>>         return shortid2uuid(self.sub.removeprefix('session:id'))
    >>>     
    >>>     @classmethod
    >>>     def create_for_session_id(cls, id: UUID, *, expires: timedelta = None) -> APIAccessToken:
    >>>         return cls.create(
    >>>             subject=f'session:id={uuid2shortid(id)}',
    >>>             expires_in=expires,
    >>>         )
    >>>
    >>> token = APIAccessToken.create(
    >>>     {'id': '123456'},
    >>>     expires_in=timedelta(days=7)
    >>> )
    >>> token_str = token.encode()

    """
    # Encryption algorithm
    ALGORITHM: ClassVar[str] = 'HS256'

    # Encryption key used for JWT. Secret!
    SECRET_KEY: ClassVar[str]

    # Subject: whom the token refers to
    sub: str
    # Expires: when the token is no longer valid. Naive UTC datetime.
    exp: datetime
    # Not before: don't accept before this date
    nbf: Optional[datetime]
    # Issued at: to tell the token's age
    iat: Optional[datetime]
    # Unique token id: to prevent replays
    jti: Any

    @classmethod
    def create(cls,
               subject: str,
               expires_in: timedelta,
               **extra
               ):
        """ Create a signed JWT token: a "thing" that identifies an authenticated user

        This method is more user-friendly that __init__()

        Args:
            subject: an arbitrary user identifier. E.g. "id=10" or "login=stark"
            expires_in: when will the token expire (relative timedelta). Cannot be empty.
            extra: any custom data you might want to put into the token
        Raises:
            jwt.JWTError: (unlikely) cases or errors when encoding the data
        """
        # Can't use any of the reserved claims as custom fields
        assert not (set(extra) & JWT_RESERVED_CLAIMS)

        # Make sure expiration time is always set
        assert expires_in is not None, "Every token must have an expiration time"

        # Token object
        return cls(
            # JWT fields:
            sub=subject,  # subject
            exp=datetime.utcnow() + expires_in,
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
        payload['sub'] = cls._decode_sub(payload['sub'])

        # Expiration: convert timestamp
        if 'exp' in payload:
            # A UTC timestamp. Convert it fromtimestamp(), remove tzinfo to keep it naive
            payload['exp'] = datetime.fromtimestamp(payload['exp'], tz=timezone.utc).replace(tzinfo=None)

        return cls(
            sub=payload['sub'],
            exp=payload['exp'],
        )

    @property
    def expires_in(self) -> timedelta:
        """ How soon will the token expire """
        return self.exp - datetime.utcnow()

    def encode(self) -> str:
        """ Encode the token into a string """
        # Convert `self` info a dict
        claims = self.dict(exclude={'sub'}, exclude_unset=True)
        claims['sub'] = self._encode_sub(self.sub)

        # Encode
        return jwt.encode(
            claims,
            self.SECRET_KEY,
            algorithm=self.ALGORITHM
        )

    def as_headers(self) -> dict:
        """ Encode the token as an HTTP header, tuple """
        return {"Authorization": f"Bearer {self.encode()}"}

    def _encode_sub(self, sub: str) -> str:
        """ Decode `sub` payload """
        return sub 
    
    @classmethod
    def _decode_sub(cls, sub: str) -> str:
        """ Encode `sub` payload """
        return sub 

    class Config:
        # @cached_property won't currently work
        # https://github.com/samuelcolvin/pydantic/issues/1241
        keep_untouched = (cached_property,)


class StructuredJWTToken(JWTToken):
    """ A JWT token that has a Pydantic model as its subject 
    
    Example:
    >>> class SessionInfo(pd.BaseModel):
    >>>     id: str
    >>> 
    >>> class APIAccessToken(StructuredJWTToken):
    >>>     SECRET_KEY = b'abcdef'
    >>>     sub: SessionInfo
    """
    sub: pd.BaseModel  # type: ignore[assignment]

    def _encode_sub(self, sub: pd.BaseModel) -> str:  # type: ignore[override]
        return sub.json(exclude_unset=True)
    
    @classmethod
    def _decode_sub(cls, sub: str) -> pd.BaseModel:  # type: ignore[override]
        schema = cls.__fields__['sub'].type_
        decoded_sub = cls.__config__.json_loads(sub)
        return schema(**decoded_sub)




# Reserved claims.
# Be careful not to use any of those values accidentally
JWT_RESERVED_CLAIMS = frozenset(('iss', 'sub', 'aud', 'exp', 'nbf', 'iat', 'jti'))


def looks_like_jwt_token(token: str) -> bool:
    """ Does the value look like a JWT token? """
    return isinstance(token, str) and token.count('.') == 2
