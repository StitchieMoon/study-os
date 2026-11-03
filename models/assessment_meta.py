"""Assessment settings and files."""
from datetime import datetime

from extensions import db


class GradeScaleSettings(db.Model):
    """Per-user editable school grading scale, stored as JSON."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    scale_json = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AssessmentFile(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )


    assessment_id = db.Column(
        db.Integer,
        db.ForeignKey("assessment.id"),
        nullable=False
    )


    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )


    category = db.Column(
        db.String(30),
        nullable=False
    )


    filename = db.Column(
        db.String(500),
        nullable=False
    )


    original_filename = db.Column(
        db.String(300),
        nullable=False
    )


    uploaded_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    assessment = db.relationship(
        "Assessment",
        backref=db.backref(
            "uploaded_files",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )
