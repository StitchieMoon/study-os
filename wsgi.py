"""Production entrypoint.

The legacy routes still live in app.py; factory.py provides the stable
create_app() contract while the codebase is split up gradually.
"""
from factory import create_app

application = create_app()
