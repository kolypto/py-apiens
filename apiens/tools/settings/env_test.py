""" Automatically switch to "testing" mode when a test runner (pytest) is used """

from __future__ import annotations

import os
import sys

from .defs import Env
from .env import get_environment, load_environment_from_file


def switch_environment_when_running_tests(VAR_NAME: str):
    """ Detect test runners and switch the environment to "test"

    > Because it is outrageous to choose environments manually when it is possible to just `pytest`
    > (c) vdmit11

    Args:
        VAR_NAME: The name of the environment variable that selects the environment
    """
    # Current environment
    env = get_environment(VAR_NAME)

    # Testing in development?
    if env == Env.DEV and detect_test_run() and is_not_testing_migrations():
        env = Env.TEST
        os.environ[VAR_NAME] = env.value
        load_environment_from_file(env.value, override=True)


# region Detect test runners

def detect_test_run() -> bool:
    """ Are we currently running in unit-test mode? """
    return detect_pytest() or detect_pycharm_pytest_runner()


def detect_pytest() -> bool:
    """ Are we running: pytest? """
    return 'pytest' in sys.modules and 'pytest' in ' '.join(sys.argv)
    # WARNING: does not work!! Pytest sets this environment variable only later!
    # https://stackoverflow.com/a/58866220/134904
    # return "PYTEST_CURRENT_TEST" in os.environ


def detect_pycharm_pytest_runner():
    """ Are we running pycharm tests? """
    argv_str = ' '.join(sys.argv[1:])
    return '/pycharm/pydevd.py' in argv_str and '/pycharm/_jb_nosetest_runner.py' in argv_str


def is_not_testing_migrations() -> bool:
    """ Are we not testing migrations?

    When `pytest` is used on a migration, it shouldn't switch to "test" environment,
    because migrations should be tested on the development database
    """
    argv_str = ' '.join(sys.argv[1:])
    return 'alembic/versions/' not in argv_str

# endregion
