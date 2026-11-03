"""Compatibility application factory.

This is the first factory step while the routes still live in app.py.
It gives deployment tooling and tests a stable create_app() entry point
without rewriting the live monolith in one risky change.
"""
from app import app as legacy_app


def create_app(config=None):
    if config:
        legacy_app.config.update(config)
    return legacy_app
