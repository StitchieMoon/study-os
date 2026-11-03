"""Homework attachment model."""
from datetime import datetime

from extensions import db


class HomeworkResource(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )


    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )


    task_id = db.Column(
        db.Integer,
        db.ForeignKey("task.id"),
        nullable=False
    )


    filename = db.Column(
        db.String(300),
        nullable=False
    )


    original_filename = db.Column(
        db.String(300),
        nullable=True
    )


    uploaded_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
