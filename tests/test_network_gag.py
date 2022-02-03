import pytest


# Import fixtures
from apiens.testing.network_gag import InternetGagError
from apiens.testing.network_gag_conftest import stop_all_network, unstop_all_network


def test_request_blocked():
    import urllib.request

    with pytest.raises(InternetGagError):
        urllib.request.urlopen('http://example.com')


@pytest.mark.skipif(True, reason="No networking in unit-tests")  # enable when necessary
@pytest.mark.makes_real_network_connections
def test_request_allowed():
    import urllib.request

    # Raises no errors
    urllib.request.urlopen('http://example.com')
