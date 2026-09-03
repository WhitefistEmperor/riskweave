"""Local FastAPI application for the RingSentinel analyst console."""

from ringsentinel.api.app import app, create_app

__all__ = ["app", "create_app"]
