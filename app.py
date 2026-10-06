"""Vercel ASGI entry point. Local development uses ringsentinel.api.app instead."""

from pathlib import Path

from ringsentinel.platform.vercel_entry import create_vercel_app

app = create_vercel_app(Path(__file__).parent)
