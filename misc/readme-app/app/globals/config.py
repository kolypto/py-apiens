""" Application configuration 

Lives in module at its top level. Easy to import.
"""

import pydantic as pd

from apiens.tools.settings import AUTOMATIC
from apiens.tools.settings import unit
from apiens.tools.settings.mixins import *


# We're using Pydantic BaseSettings for validation.
# It also can read values from the environment.
class Settings(EnvMixin, DomainMixin, CorsMixin, PostgresMixin, pd.BaseSettings):
    """ Application settings """

    # Human-readable name of this project
    # Used in titles, emails & stuff
    PROJECT_NAME: str = 'My Application'

    class Config:
        # Use this prefix for environment variable names.
        env_prefix = 'APP_'
        case_sensitive = True


# HACK: patch the path.
# This is necessary only because our project lives in a sub-folder, so "misc/env" cannot be easily found.
import os.path
import apiens.tools.settings
apiens.tools.settings.env.ENVS_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '../../misc/env'))


# Load default environment values from .env files.
from apiens.tools.settings import (
    set_default_environment, 
    load_environment_defaults_for, 
    switch_environment_when_running_tests,
)
set_default_environment('APP_ENV', default_environment='dev')
load_environment_defaults_for('APP_ENV')
switch_environment_when_running_tests('APP_ENV')

# Init settings
settings = Settings()
