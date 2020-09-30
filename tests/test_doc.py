import pytest
from typing import Callable

from apiens import doc


# Fixtures

@doc.string()
def f_no_docstring():
    pass


@doc.string()
def f_docstring_only_title():
    """ Some title """


@doc.string()
def f_docstring_title_with_description():
    """ Short

    And some longer text

    And even more
    """


@doc.string()
def f_with_examples():
    """ Title

    Example:
        hey hey
    """


@doc.string()
def f_arguments():
    """

    Args:
        a: first
        b: title
            longer
        c: title

            longer
    """


@doc.string()
def f_result():
    """

    Returns:
        some value
    """

import apiens.errors_default as exc  # noqa


@doc.string()
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
            'function_doc': {'summary': 'Some title ', 'description': None},
        }),
        (f_docstring_title_with_description, {
            'function_doc': {'summary': 'Short', 'description': 'And some longer text\n\nAnd even more'},
        }),
        (f_with_examples, {
            'function_doc': {'summary': 'Title', 'description': 'examples:\nhey hey'},
        }),
        (f_arguments, {
            'function_doc': None,
            'parameters_doc': {
                'a': {'name': 'a', 'summary': 'first', 'description': None},
                'b': {'name': 'b', 'summary': 'title', 'description': 'longer'},
                'c': {'name': 'c', 'summary': 'title', 'description': 'longer'},
            }
        }),
        (f_result, {
            'function_doc': None,
            'result_doc': {'summary': 'some value', 'description': None},
        }),
        (f_errors, {
            'errors_doc': {
                exc.E_FAIL: {'error': exc.E_FAIL, 'summary': 'explanation', 'description': None},
                # KeyError ignored!
            }
        })
    ]
)
def test_operation_doc_string(func: Callable, expected_doc: dict):
    """ Test how operation docstrings are read """
    actual_doc = doc.get_from(func)

    # Test: function doc
    expected_function_doc = expected_doc.get('function_doc', None)
    if expected_function_doc is None:
        assert actual_doc.function_doc is None
    else:
        assert actual_doc.function_doc.summary == expected_function_doc['summary']
        assert actual_doc.function_doc.description == expected_function_doc['description']

    # Test: result doc
    expected_result_doc = expected_doc.get('result_doc', None)
    if expected_result_doc is None:
        assert actual_doc.result_doc is None
    else:
        assert actual_doc.result_doc.summary == expected_result_doc['summary']
        assert actual_doc.result_doc.description == expected_result_doc['description']

    # Test: deprecated doc
    expected_deprecated_doc = expected_doc.get('deprecated_doc', None)
    if expected_deprecated_doc is None:
        assert actual_doc.deprecated_doc is None
    else:
        assert actual_doc.deprecated_doc.version == expected_deprecated_doc['version']
        assert actual_doc.deprecated_doc.summary == expected_deprecated_doc['summary']
        assert actual_doc.deprecated_doc.description == expected_deprecated_doc['description']

    # Test: parameters doc
    expected_parameters_doc = expected_doc.get('parameters_doc', {})
    assert expected_parameters_doc == {
        param_name: {'name': param_name, 'summary': param_doc.summary, 'description': param_doc.description}
        for param_name, param_doc in actual_doc.parameters_doc.items()
    }

    # Test: errors doc
    expected_errors_doc = expected_doc.get('errors_doc', {})
    assert expected_errors_doc == {
        error_type: {'error': error_doc.error, 'summary': error_doc.summary, 'description': error_doc.description}
        for error_type, error_doc in actual_doc.errors_doc.items()
    }
