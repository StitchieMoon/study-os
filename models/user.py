"""User account model."""
from datetime import datetime

from extensions import db


class User(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )


    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )


    display_name = db.Column(
        db.String(100),
        nullable=True
    )


    email = db.Column(
        db.String(200),
        unique=True,
        nullable=False
    )


    password_hash = db.Column(
        db.String(300),
        nullable=False
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_token = db.Column(db.String(300), nullable=True)
    onboarded = db.Column(db.Boolean, default=False, nullable=False)
    year_level = db.Column(db.String(50), nullable=True)
