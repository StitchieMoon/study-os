"""Assessment model."""
from datetime import datetime

from extensions import db


class Assessment(db.Model):

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


    due_date = db.Column(
        db.String(20),
        nullable=True
    )


    instructions = db.Column(
        db.Text,
        nullable=True
    )


    rubric = db.Column(
        db.Text,
        nullable=True
    )


    resources = db.Column(
        db.Text,
        nullable=True
    )


    score = db.Column(
        db.Float,
        nullable=True
    )


    total_score = db.Column(
        db.Float,
        nullable=True
    )


    # Optional percentage for results where a raw score was not supplied.
    percentage_override = db.Column(
        db.Float,
        nullable=True
    )


    # How much this assessment counts towards the subject average.
    weight = db.Column(
        db.Float,
        nullable=True,
        default=1.0
    )


    grade = db.Column(
        db.String(20),
        nullable=True
    )


    happy_with_grade = db.Column(
        db.String(20),
        nullable=True
    )


    effort = db.Column(
        db.Integer,
        nullable=True
    )


    feedback = db.Column(
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


    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
