from __future__ import annotations

import os.path
import dotenv

from .defs import Env


# Environment enum class
ENV_ENUM = Env

# Path to .env files for environments
ENVS_PATH = 'misc/env/'

# Path to .env files when running locally (as determined by the following function)
ENVS_LOCAL_PATH = 'misc/env.local/'

# Is the application running locally? i.e. not in Docker.
# If so, then `ENVS_LOCAL_PATH` will be loaded too
IS_RUNNING_LOCALLY = int(os.getenv('ENV_RUNNING_LOCALLY', '0'))


def set_default_environment(VAR_NAME: str, *, default_environment: str):
    """ Set the default app environment if not set

    Example:
        set_default_environment('ENV', default_environment='dev')
    """
    if VAR_NAME not in os.environ:
        os.environ[VAR_NAME] = Env(default_environment).value


def load_environment_defaults_for(VAR_NAME: str):
    """ Load .env files for the environment if not already loaded.

    The app reads its configuration from the environment.
    But in some cases, like debugging with an IDE, this is inconvenient.

    For this reason, we *also* load .env files with Python, but it never overrides the existing environment.

    This is a back-up method, not the primary one.
    """
    # Current environment
    env = get_environment(VAR_NAME)

    # Load defaults. Do not override.
    load_environment_from_file(env.value, override=False)


def load_environment_from_file(name: str, *, override: bool):
    """ Load .env file by name: e.g. 'dev'.

    When not running locally, only `ENVS_PATH` is loaded.
    When running locally, also loads `ENVS_LOCAL_PATH` and `./.name.env`

    Args:
        name: The name of the file in `misc/env/` and `misc/env.local/`
        override: Override existing environment variables?
    """
    # Load from `misc/env`
    dotenv.load_dotenv(dotenv.find_dotenv(os.path.join(ENVS_PATH, f'{name}.env')), override=override)

    # Load from `misc/env.local` (only if running locally)
    if IS_RUNNING_LOCALLY:
        dotenv.load_dotenv(dotenv.find_dotenv(os.path.join(ENVS_LOCAL_PATH, f'{name}.env')), override=override)
        dotenv.load_dotenv(dotenv.find_dotenv(f'.{name}.env'), override=override)


def get_environment(VAR_NAME: str) -> Env:
    """ Get environment name (prod, dev, test) from environment variables

    Args:
        VAR_NAME: The environment variable name to get the value from

    Raises:
        ValueError: invalid environment name
    """
    env: str = os.environ[VAR_NAME]
    return ENV_ENUM(env)
