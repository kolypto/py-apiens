from fastapi import FastAPI

from app.globals.config import settings


# ASGI app
asgi_app = FastAPI(
    title=settings.PROJECT_NAME,
    description=""" Test app """,
    debug=not settings.is_production,
)

# Middleware
if not settings.is_testing:
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware

    # All requests must have correct "Host:" header (to guard against HTTP Host Header attack)
    asgi_app.add_middleware(TrustedHostMiddleware, allowed_hosts=[settings.DOMAIN, f'*.{settings.DOMAIN}'])

    # CORS requests (when the UI runs on a host different from the API)
    asgi_app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )


# Attach routes
from . import endpoints
asgi_app.include_router(endpoints.router)


# Attach GraphQL routes
from app.expose.graphql.app import graphql_app
asgi_app.mount('/graphql/', graphql_app)


# # Exception handlers
from apiens.tools.fastapi.exception_handlers import register_application_exception_handlers
register_application_exception_handlers(asgi_app, passthru=settings.is_testing)
