"""School subject model."""
from datetime import datetime

from extensions import db


class Subject(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )


    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )


    name = db.Column(
        db.String(100),
        nullable=False
    )


    colour = db.Column(
        db.String(30),
        nullable=False,
        default="#4f5fd5"
    )


    icon = db.Column(
        db.String(20),
        nullable=False,
        default="📘"
    )


    archived = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
