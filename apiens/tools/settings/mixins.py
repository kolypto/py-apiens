""" Pieces for building a useful application settings """

import secrets
import json
import pydantic as pd
from typing import Optional
from urllib3.util import parse_url  # type: ignore[import]

from .defs import Env


__all__ = (
    'EnvMixin', 'LocaleMixin', 'DomainMixin', 'CorsMixin', 'SecretMixin',
    'PostgresMixin', 'RedisMixin',
)


class EnvMixin(pd.BaseSettings):
    """ Settings: environment.

    Lets your app run in different modes: e.g. provide more error information when in development.

    Example:

    if not settings.is_production:
        ... # do some debugging stuff
    """
    # Environment
    ENV: Env

    @property
    def is_production(self) -> bool:
        """ Is running in a production environment?

        This normally means stricter checks, absence of development tools & debug information
        """
        return self.ENV == Env.PROD

    @property
    def is_testing(self) -> bool:
        """ Is running in testing environment?

        This normally means more debug code is executed
        """
        return self.ENV == Env.TEST

    @property
    def is_development(self) -> bool:
        """ Is running in a development environment?

        This normally means that dev tools and tracebacks are available
        """
        return self.ENV == Env.DEV


class LocaleMixin(pd.BaseSettings):
    """ Settings: language and timezone """
    # Locale
    LOCALE: str = 'en'

    # Default timezone
    TZ: str = 'Europe/Moscow'


class DomainMixin(pd.BaseSettings):
    """ Settings: application URL """
    # URL to where the app is served
    # Example: https://example.com/
    SERVER_URL: pd.AnyHttpUrl

    @property
    def DOMAIN(self):
        """ Domain name: host:port """
        purl = parse_url(self.SERVER_URL)
        return purl.netloc


class CorsMixin(pd.BaseSettings):
    """ Settings: CORS policy setting """
    # Allowed CORS origins
    # List of urls: "http://localhost,http://localhost:4200"
    # Or a list of JSON urls: ["http://localhost","http://localhost:4200"]
    CORS_ORIGINS: list[pd.AnyHttpUrl] = []

    @pd.validator('CORS_ORIGINS', pre=True)
    def prepare_cors_origins(cls, v: Optional[str]):
        if isinstance(v, str):
            # JSON string: ["...", "..."]
            if v[:1] == '[' and v[-1:] == ']':
                return json.loads(v)
            # Comma-separated string: ..., ..., ...
            else:
                return [i.strip() for i in v.split(',')]
        return v

    def __init__(self, *args, **kwargs):
        # NOTE: because @validator(pre=True) isn't executed early enough with environment settings
        # (it already tries to load JSON from the value into a complex field), we have to apply a hack here
        # See: https://github.com/samuelcolvin/pydantic/issues/1458
        import os, json
        CORS_NAME = self.Config.env_prefix + 'CORS_ORIGINS'
        if f'{CORS_NAME}::modified' not in os.environ:
            os.environ[CORS_NAME] = json.dumps(
                CorsMixin.prepare_cors_origins(os.getenv(CORS_NAME, ''))
            )

            # We have to make sure that this os.environ hacking happens only once.
            # Otherwise, uvicorn reloader may re-run it and corrupt the variable value
            os.environ[f'{CORS_NAME}::modified'] = '1'

        # Parse the settings from environment
        super().__init__(*args, **kwargs)


class SecretMixin(pd.BaseSettings):
    """ Setting: secret key for cryptography """
    # Secret key for the app
    # The default is used for testing and is regenerated every time
    SECRET_KEY: str = secrets.token_urlsafe(32)


class PostgresMixin(pd.BaseSettings):
    """ Setting: Postgres connection 
    
    Variable names are the same as those used with the official Docker container.
    """
    # Database connection
    # Names of these variables match with names from the postgres Docker container.
    # We manually set `env=` name to make sure that Config.env_prefix has no effect on it
    POSTGRES_HOST: str = pd.Field(..., env='POSTGRES_HOST')
    POSTGRES_PORT: str = pd.Field(..., env='POSTGRES_PORT')
    POSTGRES_USER: str = pd.Field(..., env='POSTGRES_USER')
    POSTGRES_PASSWORD: str = pd.Field(..., env='POSTGRES_PASSWORD')
    POSTGRES_DB: str = pd.Field(..., env='POSTGRES_DB')
    POSTGRES_URL: Optional[pd.PostgresDsn] = None  # build automatically

    @pd.validator("POSTGRES_URL", pre=True)
    def prepare_postgres_url(cls, v: Optional[str], values: dict):
        assert not v, 'This value should not be set directly'

        return pd.PostgresDsn.build(
            scheme="postgresql",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_HOST"),
            port=values.get('POSTGRES_PORT', None),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )


class RedisMixin(pd.BaseSettings):
    """ Setting: Redis connection """
    REDIS_URL: pd.RedisDsn

