""" Helpers for your app configuration

Example:
    class Settings(apiens.tools.settings.Settings):
        REDIS_URL: str

    set_default_environment('ENV', default_environment='dev')
    load_environment_defaults_for('ENV')
    switch_environment_when_running_tests('ENV')

    settings = Settings()

"""

from .defs import Env
from .env import (
    set_default_environment,
    load_environment_defaults_for,
    get_environment,
)
from .env_test import switch_environment_when_running_tests
from . import mixins


# Syntactic sugar to indicate values that will get defaults when not provided
AUTOMATIC = None


try:
    from .unit import unit
except ImportError as e:
    if e.name == 'pint':
        pass
    else:
        raise
