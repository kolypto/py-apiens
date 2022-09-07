import random
from apiens.testing.object_match import (
    Whatever, check, Parameter,
    DictMatch, ObjectMatch,
)


def test_parameter():
    def main():
        # Inspect key by key
        res = execute_api_request()
        assert res['user']['id'] > 0  # inspect the dynamic field
        assert res['user']['login'] == 'kolypto'
        assert res['user']['name'] == 'Mark'

        # Pop
        res = execute_api_request()
        user_id = res['user'].pop('id')  # pop the dynamic field
        assert res == {
            'user': {
                'login': 'kolypto',
                'name': 'Mark',
            }
        }
        assert user_id > 0

        # Whatever
        res = execute_api_request()
        assert res == {
            'user': {
                # Ignore the value: equality always give True
                'id': Whatever,
                'login': 'kolypto',
                'name': 'Mark',
            }
        }

        # Check
        res = execute_api_request()
        assert res == {
            'user': {
                # Use a lambda function to test the value
                'id': check(lambda v: v>0),
                'login': 'kolypto',
                'name': 'Mark',
            }
        }

        # Parameter
        res = execute_api_request()
        assert res == {
            'user': {
                # Capture the value into a variable
                'id': (user_id := Parameter()),
                'login': 'kolypto',
                'name': 'Mark',
            }
        }
        # Use the value
        assert user_id.value > 0
        print(user_id.value)

        # DictMatch
        res = execute_api_request()
        assert res == {
            # Partial dict match: only named keys are compared
            'user': DictMatch({
                'login': 'kolypto',
                'name': 'Mark',
            })
        }

        # ObjectMatch
        from collections import namedtuple
        Point = namedtuple('Point', ('x', 'y'))
        
        point = Point(0, 100)
        assert point == ObjectMatch(x=0)


    def execute_api_request():
        return {
            'user': {
                'id': random.randint(0, 1000),
                'login': 'kolypto',
                'name': 'Mark',
            }
        }

    main()


