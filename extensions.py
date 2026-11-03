"""Shared Flask extensions.

Keeping the database object here is the first step towards an application
factory. The legacy app still owns the routes for now.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
