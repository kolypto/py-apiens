""" Pytest fixtures to prevent real network traffic in unit-tests 

Usage:
    # conftest.py
    from apiens.testing.network_gag_conftest import stop_all_network, unstop_all_network
"""

import pytest

from .network_gag import network_gag, InternetGags


@pytest.fixture(scope='session', autouse=True)
def stop_all_network():
    """ A network gag that prevents all unit-tests from communicating with the real network

    Use this snippet to remove this gag:
        @pytest.mark.makes_real_network_connections
    """
    with network_gag() as gag:
        yield gag


@pytest.fixture(scope='function', autouse=True)
def unstop_all_network(request, stop_all_network: InternetGags):
    """ A magic fixture that would undo `stop_all_network()` for tests marked with `makes_real_network_connections`

    Example:
        @pytest.mark.makes_real_network_connections
        def test_google():
            requests.get('https://google.com/')
    """
    # If this particular test is not marked, do nothing
    if 'makes_real_network_connections' not in request.node.keywords:
        yield
        return

    # For every function marked with 'makes_real_network_connections':
    stop_all_network.stop()

    try:
        yield
    finally:
        stop_all_network.start()
