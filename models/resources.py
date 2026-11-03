"""Resource section and file models."""
from datetime import datetime

from extensions import db


class ResourceSection(db.Model):
    """A user-created subheading inside a subject on the Resources page."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject = db.Column(db.String(100), nullable=False, default="General")
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Resource(db.Model):
    """A file or note uploaded directly on the Resources page."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject = db.Column(db.String(100), nullable=False, default="General")
    subheading = db.Column(db.String(200), nullable=False, default="General")
    title = db.Column(db.String(200), nullable=True)
    filename = db.Column(db.String(500), nullable=True)
    original_filename = db.Column(db.String(300), nullable=True)
    note = db.Column(db.Text, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
