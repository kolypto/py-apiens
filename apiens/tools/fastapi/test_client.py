import requests  # type: ignore[import]
import fastapi.testclient

from apiens.testing import SuccessfulMixin


class TestClient(fastapi.testclient.TestClient, SuccessfulMixin):
    """ FastAPI test client with special tools

    Features:
    * Use `client.successful()` to assert successful requests
    """

    def assertSuccessfulResult(self, method_name: str, return_value: requests.Response):
        # Get JSON
        assert return_value.headers.get('content-type') == 'application/json'
        json_response = return_value.json()

        # FastAPI errors
        assert 'detail' not in json_response, json_response['detail']
        assert 'error' not in json_response, json_response['error']
