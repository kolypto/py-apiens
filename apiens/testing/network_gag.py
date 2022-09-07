""" Network gag: a context manager to prevent real network connections from being made 

Example:
    with network_gag():
        ...  # I promised not to make any network connections

With pytest, use `network_gag_conftest` instead.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from unittest import mock


@contextmanager  # and decorator!
def network_gag():
    """ Set up a gag on everything that might try to do networking

    Any attempt to set up network connections will immediately fail.
    Such a failure would tell the developer that their unit-test is not mocked properly.

    It stops network connections made by: urllib, urllib3, aiohttp, amazon client
    
    Example:
        with network_gag():
            ... # do your stuff without networking
    """
    # Network gag: Amazon
    # Because some of our tests use Amazon, we put a show stopper here that fails in that case
    # Here, we create a patcher targeted at the low-level machinery inside the `boto3` Amazon library.
    # It will fail every time a request is made.
    # Because it's low level, however, it will not interfere with the `moto` library, whose mocks are higher-level
    try:
        import botocore  # type: ignore[import]
    except:
        amazon_gag = nullmock()
    else:
        amazon_gag = mock.patch('botocore.httpsession.URLLib3Session.send', mock.Mock(side_effect=AmazonGagError))

    # asyncio HTTP requests should be stopped
    try:
        import aiohttp  # type: ignore[import]
    except ImportError:
        internet_gag_aiohttp = nullmock()
    else:
        internet_gag_aiohttp = mock.patch('aiohttp.client.ClientSession._request', aiohttp_client_request_callback)

    # Network gag: HTTP requests
    # We put an additional stopper here that prevents all network requests through urllib3
    # This is the library that `requests` uses under the hood
    internet_gag_urllib3 = mock.patch(
        'urllib3.connectionpool.HTTPConnectionPool.urlopen',
        urllib3_urlopen_callback
    )

    # And this is the oldschool library that only a handful of oldschool libraries uses
    internet_gag_urllib = mock.patch(
        'urllib.request.urlopen',
        urllib_urlopen_callback
    )

    # All mocks
    gags = InternetGags(
        amazon=amazon_gag,
        urllib=internet_gag_urllib,
        urllib3=internet_gag_urllib3,
        aiohttp=internet_gag_aiohttp,
    )

    gags.start()

    try:
        yield gags
    finally:
        gags.stop()


def urllib_urlopen_callback(url, *args, **kwargs):
    """ Mock side-effect for: urllib """
    # This strange behavior is seen in the `xmlschema` library:
    # it loads related XML schemas using urlopen() and fails unit-tests!
    if url.startswith('file://'):
        return original_urllib_urlopen(url, *args, **kwargs)

    raise InternetGagError(url=url)


def urllib3_urlopen_callback(self, method, url, *args, **kwargs):
    """ Mock side-effect for: urllib3 """
    raise InternetGagError(url=f'{method} {url}')


def aiohttp_client_request_callback(self, method, url, **kwargs):
    """ Mock side-effect for: aiohttp """
    if '.mock.localhost' in url:
        return original_aiohttp_request(self, method, url, **kwargs)
    raise InternetGagError(url=f'{method} {url}')


@dataclass
class InternetGags:
    amazon: mock._patch
    urllib: mock._patch
    urllib3: mock._patch
    aiohttp: mock._patch

    def stop(self):
        self.amazon.stop()
        self.urllib.stop()
        self.urllib3.stop()
        self.aiohttp.stop()

    def start(self):
        self.amazon.start()
        self.urllib.start()
        self.urllib3.start()
        self.aiohttp.start()


class AmazonGagError(RuntimeError):
    """ Error: a unit-test tried to use Amazon """
    def __init__(self):
        super().__init__(
            'This unit-test has attempted to communicate with a live amazon service.\n'
            'Please use the `moto` library to mock Amazon in your test.\n'
            'It is simple. Just decorate your unit-test with @mock_s3 or something.\n'
            'Cheers!'
        )


class InternetGagError(RuntimeError):
    """ Error: a unit-test tried to make an HTTP request """
    def __init__(self, url: str):
        super().__init__(
            f'This unit-test has attempted to communicate with the Internet.\n'
            f'URL: {url}\n'
            f'Please use the `responses` library to mock HTTP in your tests.\n'
            f'Cheers!'
        )


def nullmock():
    return mock.patch.object(type('', (), {}), '__doc__', 'placeholder')


# Unmocked methods
import urllib.request
original_urllib_urlopen = urllib.request.urlopen

try:
    import aiohttp.client  # type: ignore[import]
except ImportError:
    original_aiohttp_request = None
else:
    original_aiohttp_request = aiohttp.client.ClientSession._request
