""" Helpers for your app configuration

Features:

* Supports three modes: production, development, testing
* Loads configuration from environment variables
* Automatically switches to "testing" when `pytest` is used

Example:
    import pydantic as pd

    class Settings(pd.Settings):
        REDIS_URL: str

    set_default_environment('ENV', default_environment='dev')
    load_environment_defaults_for('ENV')
    switch_environment_when_running_tests('ENV')
    logging.basicConfig()

    settings = Settings()

Check out `mixins` for some configuration values' recipes.
"""

from .defs import Env
from .env import (
    set_default_environment,
    load_environment_defaults_for,
    get_environment,
)
from .env_test import switch_environment_when_running_tests
from . import mixins, logging


# Syntactic sugar to indicate values that will get defaults when not provided
AUTOMATIC = None


# When `pint` is available, we can use `unit`
try:
    from .unit import unit
except ImportError as e:
    if e.name != 'pint':
        raise
