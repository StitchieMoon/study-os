"""Health check blueprint.

The URL stays /healthz; only the registration moves into a blueprint.
"""
import os

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/healthz")
def healthz():
    version = "unknown"
    try:
        version_path = os.path.join(os.path.dirname(__file__), "..", "VERSION")
        with open(version_path, "r", encoding="utf-8") as version_file:
            version = version_file.read().strip()
    except OSError:
        pass
    return jsonify({"status": "ok", "version": version})
