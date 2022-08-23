from apiens.tools.settings.mixins import CorsMixin

def test_cors_origins():
    # NOTE: CorsMixin actually alters the environment in order to support JSON arrays.
    # After the value is patched, it should still be acceptable to CorsMixin.

    # Original, unpatched string
    settings = CorsMixin(CORS_ORIGINS='http://localhost,http://localhost:8080')

    # Patched string
    settings = CorsMixin(CORS_ORIGINS='["http://localhost", "http://localhost:8080"]')
