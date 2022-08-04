""" Test error/exc.py """

import pydantic as pd

from apiens.error import exc

def test_base_application_error():
    """ Text: exc.BaseApplicationError """
    e = exc.E_API_ARGUMENT.format(
        'Wrong `{name}` value',
        'Please check your `{name}`',
        name='name',
        debug_value='John',
    )   
    
    assert e.error == 'Wrong `name` value'
    assert e.fixit == 'Please check your `name`'
    assert e.info == {'name': 'name'}
    assert e.debug == {'value': 'John'}

    assert e.name == 'E_API_ARGUMENT'
    assert e.dict(include_debug_info=True) == {
        'name': 'E_API_ARGUMENT',
        'title': exc.E_API_ARGUMENT.title,
        'httpcode': 400,
        'error': 'Wrong `name` value',
        'fixit': 'Please check your `name`',
        'info': {'name': 'name'},
        'debug': {'value': 'John'},
    }
    assert e.dict(include_debug_info=False)['debug'] == None


def test_E_CLIENT_VALIDATION():
    """ Test: exc.E_CLIENT_VALIDATION and its custom logic """
    def main():
        # Convert Pydantic errors
        try: 
            User(id='INVALID', login=None)
        except pd.ValidationError as pd_error:
            error = exc.E_CLIENT_VALIDATION.from_pydantic_validation_error(pd_error)
            assert error.info == {
                # Model is named
                'model': 'User',
                'errors': [
                    # Pydantic errors are included
                    *pd_error.errors()
                ]
            }
    
    class User(pd.BaseModel):
        id: int
        login: str

    # Go
    main()


def test_F_UNEXPECTED_ERROR():
    """ Test: F_UNEXPECTED_ERROR and its custom logic """
    try:
        raise ValueError('!')
    except Exception as e:
        application_error = exc.F_UNEXPECTED_ERROR.from_exception(e)
        assert application_error.debug == {
            'errors': [
                {
                    'msg': '!',
                    'type': 'ValueError',
                    # Nice traceback is included
                    'trace': ['error/test_error_exc.py:test_F_UNEXPECTED_ERROR'],
                }
            ]
        }
