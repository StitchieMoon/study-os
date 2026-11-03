"""Application paths and secret loading.

This is the first small extraction from the legacy app.py monolith.
It has no routes and no database imports, so it is safe to test in isolation.
"""
import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")


def load_secret_key():
    """Use SECRET_KEY from the environment, or a private key file."""
    env_key = os.environ.get("SECRET_KEY", "").strip()
    if env_key:
        return env_key

    instance_dir = os.path.join(BASE_DIR, "instance")
    os.makedirs(instance_dir, exist_ok=True)
    key_path = os.path.join(instance_dir, "secret_key")

    try:
        with open(key_path, "r", encoding="utf-8") as key_file:
            saved_key = key_file.read().strip()
        if saved_key:
            return saved_key
    except FileNotFoundError:
        pass

    new_key = secrets.token_hex(32)
    with open(key_path, "w", encoding="utf-8") as key_file:
        key_file.write(new_key)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass
    return new_key
