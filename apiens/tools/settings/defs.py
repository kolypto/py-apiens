from enum import Enum


class Env(Enum):
    """ The environment name the application is running in """
    PROD = 'prod'
    DEV = 'dev'
    TEST = 'test'


# Add some aliases
# Source: https://stackoverflow.com/questions/43202777/get-enum-name-from-multiple-values-python
Env._value2member_map_['production'] = Env.PROD  # type: ignore[index]
Env._value2member_map_['development'] = Env.DEV  # type: ignore[index]
Env._value2member_map_['devel'] = Env.DEV  # type: ignore[index]
