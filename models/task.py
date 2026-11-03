"""Homework task model."""
from datetime import datetime

from extensions import db


class Task(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )


    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )


    title = db.Column(
        db.String(200),
        nullable=False
    )


    subject = db.Column(
        db.String(100),
        nullable=True
    )


    assigned_date = db.Column(
        db.String(20),
        nullable=True
    )


    due_date = db.Column(
        db.String(20),
        nullable=True
    )


    notes = db.Column(
        db.Text,
        nullable=True
    )


    completed = db.Column(
        db.Boolean,
        default=False
    )


    archived = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )


    pinned = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )


    reflection = db.Column(
        db.Text,
        nullable=True
    )


    finished_file = db.Column(
        db.String(300),
        nullable=True
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )
