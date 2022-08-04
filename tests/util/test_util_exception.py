from apiens.util.exception import exception_from


def test_exception_from():
    # Create an error
    try:
        raise ValueError('A')
    except ValueError as value_error:
        # Use exception_from()
        new_error = RuntimeError('B')
        exception_from(new_error, value_error)

        # Try raising it
        try:
            raise new_error
        except Exception as e:
            assert e.__cause__ == value_error
