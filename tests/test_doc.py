import pytest
from typing import Callable

from apiens import operation


# Fixtures

@operation()
def f_no_docstring():
    pass


@operation()
def f_docstring_only_title():
    """ Some title """


@operation()
def f_docstring_title_with_description():
    """ Short

    And some longer text

    And even more
    """


@operation()
def f_with_examples():
    """ Title

    Example:
        hey hey
    """


@operation()
def f_arguments():
    """

    Args:
        a: first
        b: title
            longer
        c: title

            longer
    """


@operation()
def f_result():
    """

    Returns:
        some value
    """

import apiens.errors_default as exc  # noqa


@operation()
def f_errors():
    """

    Raises:
        exc.E_FAIL: explanation
        KeyError: bad failure
    """


@pytest.mark.parametrize(
    ['func', 'expected_doc'],
    [
        (f_no_docstring, {}),
        (f_docstring_only_title, {
            'function': {'summary': 'Some title ', 'description': None},
        }),
        (f_docstring_title_with_description, {
            'function': {'summary': 'Short', 'description': 'And some longer text\n\nAnd even more'},
        }),
        (f_with_examples, {
            'function': {'summary': 'Title', 'description': 'examples:\nhey hey'},
        }),
        (f_arguments, {
            'function': None,
            'parameters': {
                'a': {'name': 'a', 'summary': 'first', 'description': None},
                'b': {'name': 'b', 'summary': 'title', 'description': 'longer'},
                'c': {'name': 'c', 'summary': 'title', 'description': 'longer'},
            }
        }),
        (f_result, {
            'function': None,
            'result': {'summary': 'some value', 'description': None},
        }),
        (f_errors, {
            'errors': {
                exc.E_FAIL: {'error': exc.E_FAIL, 'summary': 'explanation', 'description': None},
                # KeyError ignored!
            }
        })
    ]
)
def test_operation_doc_string(func: Callable, expected_doc: dict):
    """ Test how operation docstrings are read """
    actual_doc = operation.get_from(func).doc

    # Test: function doc
    expected_function_doc = expected_doc.get('function', None)
    if expected_function_doc is None:
        assert actual_doc.function is None
    else:
        assert actual_doc.function.summary == expected_function_doc['summary']
        assert actual_doc.function.description == expected_function_doc['description']

    # Test: result doc
    expected_result_doc = expected_doc.get('result', None)
    if expected_result_doc is None:
        assert actual_doc.result is None
    else:
        assert actual_doc.result.summary == expected_result_doc['summary']
        assert actual_doc.result.description == expected_result_doc['description']

    # Test: deprecated doc
    expected_deprecated_doc = expected_doc.get('deprecated', None)
    if expected_deprecated_doc is None:
        assert actual_doc.deprecated is None
    else:
        assert actual_doc.deprecated.version == expected_deprecated_doc['version']
        assert actual_doc.deprecated.summary == expected_deprecated_doc['summary']
        assert actual_doc.deprecated.description == expected_deprecated_doc['description']

    # Test: parameters doc
    expected_parameters_doc = expected_doc.get('parameters', {})
    assert expected_parameters_doc == {
        param_name: {'name': param_name, 'summary': param_doc.summary, 'description': param_doc.description}
        for param_name, param_doc in actual_doc.parameters.items()
    }

    # Test: errors doc
    expected_errors_doc = expected_doc.get('errors', {})
    assert expected_errors_doc == {
        error_type: {'error': error_doc.error, 'summary': error_doc.summary, 'description': error_doc.description}
        for error_type, error_doc in actual_doc.errors.items()
    }
