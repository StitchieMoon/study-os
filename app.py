import os
import json
import secrets
import smtplib
import hmac
import threading
import time
import re
import zipfile
import ipaddress
import socket
import io
import base64
import random
import calendar as pycalendar
from email.message import EmailMessage
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from urllib.parse import urlparse
import requests

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    abort,
    url_for
)

from flask_sqlalchemy import SQLAlchemy

from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)

from werkzeug.utils import secure_filename

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend

from extensions import db
from models.user import User
from models.subject import Subject
from models.task import Task
from models.homework_resource import HomeworkResource
from models.assessment import Assessment
from blueprints.health import health_bp
from blueprints.auth import auth_bp
from blueprints.today import today_bp
from blueprints.homework import homework_bp


# =========================================================
# APP SETUP
# =========================================================

from config import BASE_DIR, UPLOAD_FOLDER, load_secret_key


os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


app = Flask(__name__)


app.config["SECRET_KEY"] = load_secret_key()


app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "STUDYOS_DATABASE_URI",
    "sqlite:///study_os.db",
)


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "20")) * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SMTP_SERVER"] = os.environ.get("SMTP_SERVER", "")
app.config["SMTP_PORT"] = int(os.environ.get("SMTP_PORT", "587"))
app.config["SMTP_USERNAME"] = os.environ.get("SMTP_USERNAME", "")
app.config["SMTP_PASSWORD"] = os.environ.get("SMTP_PASSWORD", "")
app.config["EMAIL_FROM"] = os.environ.get("EMAIL_FROM", app.config["SMTP_USERNAME"])
app.config["SMTP_USE_TLS"] = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

db.init_app(app)
app.register_blueprint(health_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(today_bp)
app.register_blueprint(homework_bp)
# Keep the old endpoint name used by templates and login_required().
app.add_url_rule("/login", endpoint="login", view_func=app.view_functions["auth.login"], methods=["GET", "POST"])
app.add_url_rule("/register", endpoint="register", view_func=app.view_functions["auth.register"], methods=["GET", "POST"])
app.add_url_rule("/forgot-password", endpoint="forgot_password", view_func=app.view_functions["auth.forgot_password"], methods=["GET", "POST"])
app.add_url_rule("/forgot-password/confirm", endpoint="forgot_password_confirm", view_func=app.view_functions["auth.forgot_password_confirm"], methods=["POST"])
app.add_url_rule("/reset-password/<token>", endpoint="reset_password", view_func=app.view_functions["auth.reset_password"], methods=["GET", "POST"])
app.add_url_rule("/verify-email/pending", endpoint="verify_email_pending", view_func=app.view_functions["auth.verify_email_pending"], methods=["GET", "POST"])
app.add_url_rule("/verify-email/<token>", endpoint="verify_email", view_func=app.view_functions["auth.verify_email"], methods=["GET"])
app.add_url_rule("/signup", endpoint="signup", view_func=app.view_functions["auth.signup"], methods=["GET"])
app.add_url_rule("/today", endpoint="today_page", view_func=app.view_functions["today.today_page"], methods=["GET"])
app.add_url_rule("/tasks", endpoint="tasks", view_func=app.view_functions["homework.tasks"], methods=["GET"])
app.add_url_rule("/add-task", endpoint="add_task", view_func=app.view_functions["homework.add_task"], methods=["POST"])
app.add_url_rule("/task/<int:task_id>", endpoint="view_task", view_func=app.view_functions["homework.view_task"], methods=["GET"])
app.add_url_rule("/edit-task/<int:task_id>", endpoint="edit_task", view_func=app.view_functions["homework.edit_task"], methods=["POST"])
app.add_url_rule("/save-task-notes/<int:task_id>", endpoint="save_task_notes", view_func=app.view_functions["homework.save_task_notes"], methods=["POST"])
app.add_url_rule("/complete-task/<int:task_id>", endpoint="complete_task", view_func=app.view_functions["homework.complete_task"], methods=["POST"])
app.add_url_rule("/uncomplete-task/<int:task_id>", endpoint="uncomplete_task", view_func=app.view_functions["homework.uncomplete_task"], methods=["POST"])
app.add_url_rule("/incomplete-task/<int:task_id>", endpoint="uncomplete_task", view_func=app.view_functions["homework.uncomplete_task"], methods=["POST"])
app.add_url_rule("/mark-incomplete/<int:task_id>", endpoint="uncomplete_task", view_func=app.view_functions["homework.uncomplete_task"], methods=["POST"])
app.add_url_rule("/mark-as-incomplete/<int:task_id>", endpoint="uncomplete_task", view_func=app.view_functions["homework.uncomplete_task"], methods=["POST"])
app.add_url_rule("/tasks/history", endpoint="task_history", view_func=app.view_functions["homework.task_history"], methods=["GET"])
app.add_url_rule("/delete-task/<int:task_id>", endpoint="delete_task", view_func=app.view_functions["homework.delete_task"], methods=["POST"])
app.add_url_rule("/upload-task-resource/<int:task_id>", endpoint="upload_task_resource", view_func=app.view_functions["homework.upload_task_resource"], methods=["POST"])
app.add_url_rule("/download-task-resource/<int:resource_id>", endpoint="download_task_resource", view_func=app.view_functions["homework.download_task_resource"], methods=["GET"])
app.add_url_rule("/download-finished-task/<int:task_id>", endpoint="download_finished_task", view_func=app.view_functions["homework.download_finished_task"], methods=["GET"])
app.add_url_rule("/delete-task-resource/<int:resource_id>", endpoint="delete_task_resource", view_func=app.view_functions["homework.delete_task_resource"], methods=["POST"])
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

from services.time import (
    APP_TZ_NAME,
    app_now,
    app_today,
    local_day_bounds_utc,
    local_date_of,
)

SMTP_SETTINGS_FILE = os.path.join(BASE_DIR, "instance", "smtp.json")


def load_smtp_settings():
    try:
        with open(SMTP_SETTINGS_FILE, "r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
    except (OSError, ValueError):
        return
    mapping = {
        "server": "SMTP_SERVER",
        "port": "SMTP_PORT",
        "username": "SMTP_USERNAME",
        "password": "SMTP_PASSWORD",
        "from_email": "EMAIL_FROM",
        "use_tls": "SMTP_USE_TLS",
    }
    for key, config_key in mapping.items():
        if key in settings:
            app.config[config_key] = settings[key]


def save_smtp_settings(settings):
    os.makedirs(os.path.dirname(SMTP_SETTINGS_FILE), exist_ok=True)
    with open(SMTP_SETTINGS_FILE, "w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file)
    try:
        os.chmod(SMTP_SETTINGS_FILE, 0o600)
    except OSError:
        pass
    load_smtp_settings()


load_smtp_settings()



# =========================================================
# SECURITY HELPERS
# =========================================================

ALLOWED_UPLOAD_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".txt", ".md", ".doc", ".docx", ".ppt", ".pptx",
    ".xls", ".xlsx", ".csv", ".zip",
}

INLINE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def upload_extension(filename):
    name = (filename or "").strip()
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[1].lower()[:20]


def upload_is_allowed(filename):
    return upload_extension(filename) in ALLOWED_UPLOAD_EXTENSIONS


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def csrf_protect():
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None

    saved_token = session.get("_csrf_token")
    sent_token = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")

    if not saved_token or not sent_token or not hmac.compare_digest(saved_token, sent_token):
        abort(400, description="Security check failed. Refresh the page and try again.")

    return None


@app.after_request
def add_security_headers(response):
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


_login_attempts = {}
_login_lock = threading.Lock()
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60


def login_attempt_key():
    identifier = request.form.get("identifier", "").strip().lower()
    return (request.remote_addr or "unknown", identifier)


def too_many_login_attempts(key):
    now = time.time()
    with _login_lock:
        attempts = [stamp for stamp in _login_attempts.get(key, []) if now - stamp < LOGIN_WINDOW_SECONDS]
        _login_attempts[key] = attempts
        return len(attempts) >= LOGIN_MAX_ATTEMPTS


def record_login_failure(key):
    with _login_lock:
        _login_attempts.setdefault(key, []).append(time.time())


def clear_login_failures(key):
    with _login_lock:
        _login_attempts.pop(key, None)


# =========================================================
# TEMPLATE FILTERS
# =========================================================

from services.dates import (
    parse_homework_date,
    normalise_homework_date,
    date_format,
    homework_date_input,
)

app.template_filter("date_format")(date_format)
app.template_filter("homework_date_input")(homework_date_input)


# =========================================================
# USER MODEL
# =========================================================



# =========================================================
# SUBJECT MODEL
# =========================================================



# =========================================================
# HOMEWORK MODEL
# =========================================================



# =========================================================
# HOMEWORK RESOURCE MODEL
# =========================================================



# =========================================================
# ASSESSMENT MODEL
# =========================================================



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


# =========================================================
# RESOURCES
# =========================================================

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


class PushSubscription(db.Model):
    __tablename__ = "push_subscription"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh = db.Column(db.Text, nullable=False)
    auth = db.Column(db.Text, nullable=False)
    user_agent = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PushReminderSent(db.Model):
    __tablename__ = "push_reminder_sent"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reminder_key = db.Column(db.String(300), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PracticeTest(db.Model):
    """A generated practice test and its answer key."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject = db.Column(db.String(100), nullable=True)
    topic = db.Column(db.String(200), nullable=True)
    year_level = db.Column(db.String(20), nullable=True)
    difficulty = db.Column(db.String(20), nullable=True)
    questions_json = db.Column(db.Text, nullable=False)
    total_marks = db.Column(db.Float, nullable=True)
    score = db.Column(db.Float, nullable=True)
    percentage = db.Column(db.Float, nullable=True)
    grade = db.Column(db.String(20), nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================================================
# TO-DO MODEL
# =========================================================

class Todo(db.Model):

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


    date = db.Column(
        db.String(20),
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


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )


# =========================================================
# CALENDAR EVENT MODEL
# =========================================================

class CalendarEvent(db.Model):

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


    event_date = db.Column(
        db.String(20),
        nullable=False
    )


    start_time = db.Column(
        db.String(10),
        nullable=True
    )


    end_time = db.Column(
        db.String(10),
        nullable=True
    )


    subject = db.Column(
        db.String(100),
        nullable=True
    )


    event_type = db.Column(
        db.String(100),
        nullable=False,
        default="Event"
    )


    notes = db.Column(
        db.Text,
        nullable=True
    )

    # Recurrence is stored on the original event rather than creating
    # hundreds of duplicate database rows. The calendar expands the series
    # when a particular date is viewed.
    recurrence_rule = db.Column(
        db.String(50),
        nullable=False,
        default="none"
    )

    recurrence_interval = db.Column(
        db.Integer,
        nullable=False,
        default=1
    )

    recurrence_unit = db.Column(
        db.String(20),
        nullable=False,
        default="day"
    )

    recurrence_until = db.Column(
        db.String(20),
        nullable=True
    )

    # YYYY-MM-DD dates skipped from this recurring series.
    recurrence_exceptions = db.Column(
        db.Text,
        nullable=True
    )


# =========================================================
# PANORAMA MODEL
# =========================================================

class PanoramaSession(db.Model):

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
        nullable=False,
        default="Study Session"
    )


    subject = db.Column(
        db.String(100),
        nullable=False,
        default=""
    )


    start_time = db.Column(
        db.String(10),
        nullable=True
    )


    end_time = db.Column(
        db.String(10),
        nullable=True
    )


    study_length = db.Column(
        db.Integer,
        nullable=False,
        default=25
    )


    break_length = db.Column(
        db.Integer,
        nullable=False,
        default=5
    )


    cycles = db.Column(
        db.Integer,
        nullable=False,
        default=1
    )


    study_music = db.Column(
        db.String(300),
        nullable=True
    )


    break_music = db.Column(
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


# =========================================================
# EMAIL HELPERS
# =========================================================

def send_email(to_email, subject, body):
    if not all([app.config["SMTP_SERVER"], app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"], app.config["EMAIL_FROM"]]):
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = app.config["EMAIL_FROM"]
    message["To"] = to_email
    message.set_content(body)
    if app.config["SMTP_PORT"] == 465:
        with smtplib.SMTP_SSL(app.config["SMTP_SERVER"], app.config["SMTP_PORT"], timeout=20) as server:
            server.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
            server.send_message(message)
    else:
        with smtplib.SMTP(app.config["SMTP_SERVER"], app.config["SMTP_PORT"], timeout=20) as server:
            if app.config["SMTP_USE_TLS"]:
                server.starttls()
            server.login(app.config["SMTP_USERNAME"], app.config["SMTP_PASSWORD"])
            server.send_message(message)
    return True

def make_token(email, purpose):
    return serializer.dumps(email, salt=f"study-os-{purpose}")

def read_token(token, purpose, max_age=3600):
    return serializer.loads(token, salt=f"study-os-{purpose}", max_age=max_age)


# =========================================================
# LOGIN HELPERS
# =========================================================

def logged_in():

    return (
        session.get("user_id")
        is not None
    )


def current_user_id():

    return session.get(
        "user_id"
    )


def login_required():

    if not logged_in():

        flash(
            "Please log in to access SmartStride.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    return None


# =========================================================
# QUICK ADD
# =========================================================

def parse_quick_add(text, subject_names):
    """Small rule-based parser for the home quick-add bar."""
    raw = (text or "").strip()
    title = raw
    due = None
    today = app_today()
    lowered = raw.lower()

    # Explicit ISO date first.
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", raw)
    if iso:
        try:
            due = datetime.strptime(iso.group(1), "%Y-%m-%d").date()
            title = title.replace(iso.group(0), " ")
        except ValueError:
            due = None

    # Day/month, using the current year unless one is supplied.
    if due is None:
        short_date = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", raw)
        if short_date:
            try:
                year = int(short_date.group(3) or today.year)
                if year < 100:
                    year += 2000
                due = date(year, int(short_date.group(2)), int(short_date.group(1)))
                title = title.replace(short_date.group(0), " ")
            except ValueError:
                due = None

    if due is None:
        if re.search(r"\btoday\b", lowered):
            due = today
            title = re.sub(r"\btoday\b", " ", title, flags=re.I)
        elif re.search(r"\btomorrow\b", lowered):
            due = today + timedelta(days=1)
            title = re.sub(r"\btomorrow\b", " ", title, flags=re.I)
        elif re.search(r"\bnext week\b", lowered):
            due = today + timedelta(days=7)
            title = re.sub(r"\bnext week\b", " ", title, flags=re.I)
        else:
            for index, day_name in enumerate(pycalendar.day_name):
                day_key = day_name.lower()
                if re.search(r"\b" + re.escape(day_key) + r"\b", lowered):
                    days_ahead = (index - today.weekday()) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    due = today + timedelta(days=days_ahead)
                    title = re.sub(r"\b" + re.escape(day_key) + r"\b", " ", title, flags=re.I)
                    break

    subject = ""
    aliases = {
        "maths": "Mathematics", "math": "Mathematics",
        "english": "English", "science": "Science",
        "history": "History", "geography": "Geography"
    }
    for token, canonical in aliases.items():
        if canonical in subject_names and re.search(r"\b" + re.escape(token) + r"\b", title, flags=re.I):
            subject = canonical
            title = re.sub(r"\b" + re.escape(token) + r"\b", " ", title, flags=re.I)
            break
    if not subject:
        for name in sorted(subject_names, key=len, reverse=True):
            if name and re.search(r"\b" + re.escape(name) + r"\b", title, flags=re.I):
                subject = name
                title = re.sub(r"\b" + re.escape(name) + r"\b", " ", title, flags=re.I)
                break

    title = re.sub(r"\b(due|by|on|for)\b\s*$", " ", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip(" -–—,.;:")
    if not title:
        title = "New task"
    return title[:200], due, subject


@app.route("/quick-add", methods=["POST"])
def quick_add():
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    text = request.form.get("text", "").strip()
    if not text:
        flash("Type something to add, for example: Maths worksheet due Friday.", "error")
        return redirect(url_for("home"))

    subject_names = [
        subject.name for subject in Subject.query.filter_by(user_id=uid, archived=False).all()
    ]
    title, due, subject = parse_quick_add(text, subject_names)
    db.session.add(Task(
        user_id=uid,
        title=title,
        subject=subject or None,
        assigned_date=app_today().isoformat(),
        due_date=due.isoformat() if due else None,
        completed=False,
    ))
    db.session.commit()
    if due:
        flash("Added “%s” for %s." % (title, due.strftime("%d/%m/%Y")), "success")
    else:
        flash("Added “%s” — no date yet." % title, "success")
    return redirect(url_for("home"))


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if not logged_in():

        return redirect(
            url_for("login")
        )


    uid = current_user_id()


    homework_count = Task.query.filter_by(
        user_id=uid,
        completed=False, archived=False
    ).count()


    assessment_count = Assessment.query.filter_by(
        user_id=uid,
        completed=False, archived=False
    ).count()


    todo_count = Todo.query.filter_by(
        user_id=uid,
        completed=False, archived=False
    ).count()


    todos = Todo.query.filter_by(
        user_id=uid,
        completed=False, archived=False
    ).order_by(
        Todo.date.asc(),
        Todo.created_at.asc()
    ).all()

    tasks = Task.query.filter_by(
        user_id=uid,
        completed=False, archived=False
    ).order_by(Task.due_date.asc()).all()

    assessments = Assessment.query.filter_by(
        user_id=uid,
        completed=False, archived=False
    ).order_by(Assessment.due_date.asc()).all()

    all_home_assessments = Assessment.query.filter_by(user_id=uid).filter(Assessment.archived.is_(False)).all()
    home_percentages = []
    for assessment in all_home_assessments:
        value = assessment_percentage(assessment)
        if value is not None and (assessment.grade or "").strip().upper() != "N/A":
            home_percentages.append(value)
    overall_average = (
        sum(home_percentages) / len(home_percentages)
        if home_percentages else None
    )
    overall_grade = (
        grade_for_percentage(overall_average, get_user_grade_scale(uid))
        if overall_average is not None else None
    )

    pinned_tasks = Task.query.filter_by(
        user_id=uid, completed=False, archived=False, pinned=True
    ).order_by(Task.due_date.asc()).limit(3).all()

    home_assessment_rows = []
    for assessment in assessments:
        due = parse_homework_date(assessment.due_date)
        if due is not None:
            days = (due - app_today()).days
            if days <= 21:
                home_assessment_rows.append({"assessment": assessment, "days": days,
                                             "action": assessment_next_action(assessment)})
    home_assessment_rows.sort(key=lambda row: row["days"])

    return render_template(
        "index.html",
        pinned_tasks=pinned_tasks,
        home_assessment_rows=home_assessment_rows,
        overall_average=overall_average,
        overall_grade=overall_grade,
        homework_count=homework_count,
        assessment_count=assessment_count,
        todo_count=todo_count,
        todos=todos,
        completed_todos=Todo.query.filter_by(
            user_id=uid,
            completed=True
        ).order_by(
            Todo.completed_at.desc(),
            Todo.created_at.desc()
        ).all(),
        tasks=tasks,
        assessments=assessments,
        user=User.query.get(uid)
    )


# =========================================================
# LOGIN
# =========================================================

# =========================================================
# REGISTER
# =========================================================

# =========================================================
# FORGOT PASSWORD
# =========================================================

# =========================================================
# LOGOUT
# =========================================================

# =========================================================
# SUBJECTS
# =========================================================

@app.route("/subjects")
def subjects():

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    all_subjects = Subject.query.filter_by(
        user_id=uid, archived=False
    ).order_by(
        Subject.name.asc()
    ).all()


    subject_task_counts = {}


    for subject in all_subjects:

        subject_task_counts[
            subject.id
        ] = Task.query.filter_by(

            user_id=uid,

            subject=subject.name,

            completed=False, archived=False

        ).count()


    return render_template(

        "subjects.html",

        subjects=all_subjects,

        subject_task_counts=subject_task_counts,

        viewing_subject=False,

        subject=None,

        subject_tasks=[]

    )


@app.route(
    "/subject/<int:subject_id>"
)
def subject_page(subject_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    subject = Subject.query.filter_by(

        id=subject_id,

        user_id=uid, archived=False

    ).first_or_404()


    all_subjects = Subject.query.filter_by(

        user_id=uid, archived=False

    ).order_by(

        Subject.name.asc()

    ).all()


    subject_task_counts = {}


    for subject_item in all_subjects:

        subject_task_counts[
            subject_item.id
        ] = Task.query.filter_by(

            user_id=uid,

            subject=subject_item.name,

            completed=False, archived=False

        ).count()


    subject_tasks = Task.query.filter_by(

        user_id=uid,

        subject=subject.name,

        completed=False, archived=False

    ).order_by(

        Task.due_date.asc().nullslast(),

        Task.id.asc()

    ).all()


    return render_template(

        "subjects.html",

        subjects=all_subjects,

        subject_task_counts=subject_task_counts,

        viewing_subject=True,

        subject=subject,

        subject_tasks=subject_tasks

    )


@app.route(
    "/add-subject",
    methods=["POST"]
)
def add_subject():

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    name = request.form.get(
        "name",
        ""
    ).strip()


    colour = request.form.get(
        "colour",
        "#4f5fd5"
    ).strip()


    icon = request.form.get("icon", "📘").strip() or "📘"


    if name:

        existing = Subject.query.filter(

            Subject.user_id == uid,

            db.func.lower(
                Subject.name
            ) == name.lower()

        ).first()


        if existing:

            flash(
                "You already have a subject with that name.",
                "error"
            )


        else:

            db.session.add(

                Subject(

                    user_id=uid,

                    name=name,

                    colour=colour,

                    icon=icon

                )

            )

            log_audit(uid, "create", "subject", None, name)

            db.session.commit()


    return redirect(
        url_for("subjects")
    )


@app.route(
    "/edit-subject/<int:subject_id>",
    methods=["POST"]
)
def edit_subject(subject_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    subject = Subject.query.filter_by(

        id=subject_id,

        user_id=uid, archived=False

    ).first_or_404()


    old_name = subject.name


    new_name = request.form.get(
        "name",
        ""
    ).strip()


    new_colour = request.form.get(
        "colour",
        "#4f5fd5"
    ).strip()


    new_icon = request.form.get("icon", "📘").strip() or "📘"


    if not new_name:

        flash(
            "Subject name cannot be empty.",
            "error"
        )

        return redirect(
            url_for(
                "subject_page",
                subject_id=subject_id
            )
        )


    duplicate = Subject.query.filter(

        Subject.user_id == uid,

        Subject.id != subject_id,

        db.func.lower(
            Subject.name
        ) == new_name.lower()

    ).first()


    if duplicate:

        flash(
            "You already have another subject with that name.",
            "error"
        )

        return redirect(
            url_for(
                "subject_page",
                subject_id=subject_id
            )
        )


    save_version(uid, "subject", subject)

    subject.name = new_name

    subject.colour = new_colour

    subject.icon = new_icon


    Task.query.filter_by(

        user_id=uid,

        subject=old_name

    ).update(

        {
            "subject": new_name
        }

    )


    Assessment.query.filter_by(

        user_id=uid,

        subject=old_name

    ).update(

        {
            "subject": new_name
        }

    )


    CalendarEvent.query.filter_by(

        user_id=uid,

        subject=old_name

    ).update(

        {
            "subject": new_name
        }

    )


    db.session.commit()


    return redirect(
        url_for(
            "subject_page",
            subject_id=subject_id
        )
    )


@app.route(
    "/delete-subject/<int:subject_id>",
    methods=["POST"]
)
def delete_subject(subject_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    subject = Subject.query.filter_by(

        id=subject_id,

        user_id=uid, archived=False

    ).first_or_404()


    save_version(uid, "subject", subject)

    subject.archived = True

    log_audit(uid, "archive", "subject", subject.id, subject.name)

    db.session.commit()

    flash("Subject archived. You can restore it from Data tools → Archive.", "success")

    return redirect(
        url_for("subjects")
    )


@app.route(
    "/subject/<int:subject_id>/history"
)
def subject_history(subject_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    subject = Subject.query.filter_by(

        id=subject_id,

        user_id=uid, archived=False

    ).first_or_404()


    completed_tasks = Task.query.filter_by(

        user_id=uid,

        subject=subject.name,

        completed=True

    ).order_by(

        Task.completed_at.desc()

    ).all()


    return render_template(

        "subject_history.html",

        subject=subject,

        tasks=completed_tasks

    )


# =========================================================
# HOMEWORK
# =========================================================





# =========================================================
# TO-DO PAGE
# =========================================================

@app.route("/todos")
def todos_page():

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    todos = Todo.query.filter_by(

        user_id=uid,

        completed=False, archived=False

    ).order_by(

        Todo.date.asc(),

        Todo.created_at.asc()

    ).all()


    completed_todos = Todo.query.filter_by(

        user_id=uid,

        completed=True

    ).order_by(

        Todo.completed_at.desc()

    ).all()


    return render_template(

        "todos.html",

        todos=todos,

        completed_todos=completed_todos

    )


# =========================================================
# ADD TO-DO
# =========================================================

@app.route(
    "/add-todo",
    methods=["POST"]
)
def add_todo():

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    title = request.form.get(
        "title",
        ""
    ).strip()


    if title:

        db.session.add(

            Todo(

                user_id=uid,

                title=title,

                date=request.form.get(
                    "date",
                    ""
                ).strip(),

                completed=False

            )

        )


        db.session.commit()


    return redirect(

        request.form.get(

            "redirect_page",

            url_for("todos_page")

        )

    )


# =========================================================
# COMPLETE TO-DO
# =========================================================

@app.route(
    "/complete-todo/<int:todo_id>",
    methods=["POST"]
)
def complete_todo(todo_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    todo = Todo.query.filter_by(

        id=todo_id,

        user_id=uid

    ).first_or_404()


    was_completed = bool(todo.completed)


    todo.completed = True


    todo.completed_at = datetime.utcnow()


    if not was_completed:
        award_xp(uid, 5, "To-do completed", commit=False)

    log_audit(uid, "complete", "todo", todo.id, todo.title)

    db.session.commit()


    return redirect(

        request.form.get(

            "redirect_page",

            url_for("todos_page")

        )

    )


# =========================================================
# RESTORE COMPLETED TO-DO
# =========================================================

@app.route(
    "/restore-todo/<int:todo_id>",
    methods=["POST"]
)
def restore_todo(todo_id):
    required = login_required()
    if required:
        return required

    uid = current_user_id()

    todo = Todo.query.filter_by(
        id=todo_id,
        user_id=uid
    ).first_or_404()

    todo.completed = False
    todo.completed_at = None

    db.session.commit()

    return redirect(
        request.form.get(
            "redirect_page",
            url_for("home")
        )
    )


# =========================================================
# DELETE TO-DO
# =========================================================

@app.route(
    "/delete-todo/<int:todo_id>",
    methods=["POST"]
)
def delete_todo(todo_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    todo = Todo.query.filter_by(

        id=todo_id,

        user_id=uid

    ).first_or_404()


    move_to_trash(uid, "todo", todo, todo.title)

    todo.archived = True

    todo.completed = True

    todo.completed_at = todo.completed_at or datetime.utcnow()

    db.session.commit()

    flash("Moved to Trash. You can restore it from Data tools → Trash.", "success")

    return redirect(request.form.get("redirect_page", url_for("todos_page")))



# =========================================================
# TO-DO HISTORY AND EDITING
# =========================================================

@app.route("/todos/history")
def todos_history():
    required = login_required()
    if required:
        return required

    completed_todos = Todo.query.filter_by(
        user_id=current_user_id(),
        completed=True
    ).order_by(
        Todo.completed_at.desc(),
        Todo.created_at.desc()
    ).all()

    return render_template(
        "todo_history.html",
        completed_todos=completed_todos
    )

@app.route("/edit-todo/<int:todo_id>", methods=["POST"])
def edit_todo(todo_id):
    required = login_required()
    if required:
        return required

    todo = Todo.query.filter_by(
        id=todo_id,
        user_id=current_user_id()
    ).first_or_404()

    title = request.form.get("title", "").strip()
    date_value = request.form.get("date", "").strip()

    if not title:
        flash("A To-Do needs a title.", "error")
        return redirect(request.form.get("redirect_page", url_for("todos_page")))

    save_version(uid, "todo", todo)
    todo.title = title
    todo.date = date_value
    log_audit(uid, "update", "todo", todo.id, title)
    db.session.commit()

    flash("To-Do updated.", "success")
    return redirect(
        request.form.get("redirect_page", url_for("todos_page"))
    )

# =========================================================
# ASSESSMENTS
# =========================================================

def save_assessment_files(assessment, category):
    """Save uploaded files attached to an assessment."""
    uid = current_user_id()

    for uploaded_file in request.files.getlist(category + "_files"):
        if not uploaded_file:
            continue

        original_filename = (
            uploaded_file.filename
            or ""
        ).strip()

        if not original_filename:
            continue

        if not upload_is_allowed(original_filename):
            flash(
                "%s: that file type is not allowed." % original_filename,
                "error"
            )
            continue

        # Do not reject a file just because its name contains characters
        # that secure_filename cannot transliterate (for example, some
        # non-Latin filenames). The stored filename is generated separately,
        # so the original filename can safely remain display-only metadata.
        safe_filename = secure_filename(
            original_filename
        )

        extension = upload_extension(
            original_filename
        )

        stored_filename = (
            "assessment_"
            + secrets.token_hex(12)
            + extension
        )

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            stored_filename
        )

        try:
            uploaded_file.save(file_path)
        except (OSError, ValueError) as exc:
            app.logger.exception(
                "Could not save assessment upload %r: %s",
                original_filename,
                exc
            )
            flash(
                "Could not upload %s. Please try again or use a smaller file." % original_filename,
                "error"
            )
            continue

        db.session.add(
            AssessmentFile(
                assessment_id=assessment.id,
                user_id=uid,
                category=category,
                filename=stored_filename,
                original_filename=original_filename
            )
        )


@app.route("/assessment-file/<int:file_id>")
def assessment_file(file_id):

    required = login_required()

    if required:
        return required

    item = AssessmentFile.query.filter_by(
        id=file_id,
        user_id=current_user_id()
    ).first_or_404()

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        item.filename,
        download_name=item.original_filename,
        as_attachment=(
            upload_extension(item.filename)
            not in INLINE_IMAGE_EXTENSIONS
        ),
        conditional=True
    )


@app.route("/delete-assessment-file/<int:file_id>", methods=["POST"])
def delete_assessment_file(file_id):

    required = login_required()

    if required:
        return required

    item = AssessmentFile.query.filter_by(
        id=file_id,
        user_id=current_user_id()
    ).first_or_404()

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        item.filename
    )

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    db.session.delete(item)
    db.session.commit()
    flash("Assessment file removed.", "success")

    return redirect(url_for("assessments"))


def _assessment_sort_key(item):
    parsed = parse_homework_date(item.due_date)
    # Real dates are always before undated assessments, with the closest
    # upcoming/oldest due date first. This is chronological ordering, not
    # alphabetical ordering of the stored date string.
    return (1, date.max, item.id) if parsed is None else (0, parsed, item.id)


def _render_assessments_page(history=False):
    uid = current_user_id()

    query = Assessment.query.filter_by(user_id=uid).filter(Assessment.archived.is_(False))

    if history:
        query = query.filter(Assessment.completed.is_(True))
    else:
        query = query.filter(
            db.or_(
                Assessment.completed.is_(False),
                Assessment.completed.is_(None)
            )
        )

    page_assessments = query.all()
    page_assessments.sort(key=_assessment_sort_key)

    all_subjects = Subject.query.filter_by(
        user_id=uid, archived=False
    ).order_by(
        Subject.name.asc()
    ).all()

    return render_template(
        "assessments.html",
        assessments=page_assessments,
        subjects=all_subjects,
        history=history
    )


@app.route("/assessments")
def assessments():
    required = login_required()
    if required:
        return required
    return _render_assessments_page(history=False)


@app.route("/assessments/history")
def assessment_history():
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    history_assessments = Assessment.query.filter(
        Assessment.user_id == uid,
        Assessment.completed.is_(True)
    ).all()
    history_assessments.sort(key=_assessment_sort_key)

    # Use the same assessment card template as the upcoming page so history
    # has the full assessment controls, including delete/edit/file actions.
    all_subjects = Subject.query.filter_by(
        user_id=uid, archived=False
    ).order_by(Subject.name.asc()).all()

    return render_template(
        "assessments.html",
        assessments=history_assessments,
        subjects=all_subjects,
        history=True
    )


@app.route(
    "/upload-assessment-files/<int:assessment_id>",
    methods=["POST"]
)
def upload_assessment_files(assessment_id):
    """Upload one or more files for an existing assessment.

    This deliberately uses a simple multipart form with a single ``files``
    field plus a category. It avoids relying on HTML form association between
    inputs and a different form, which caused uploads to be silently missed.
    """
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    assessment = Assessment.query.filter_by(
        id=assessment_id,
        user_id=uid
    ).first_or_404()

    category = request.form.get("category", "").strip().lower()
    if category not in ("instructions", "rubric", "resources"):
        flash("Choose Instructions, Rubric or Resources before uploading.", "error")
        return redirect(request.form.get("redirect_to") or url_for("assessments"))

    uploaded_files = request.files.getlist("files")
    saved_count = 0

    for uploaded_file in uploaded_files:
        if not uploaded_file or not uploaded_file.filename:
            continue

        original_filename = uploaded_file.filename.strip()
        if not original_filename:
            continue

        safe_filename = secure_filename(original_filename)
        source_name = safe_filename or original_filename
        extension = ""
        if "." in source_name:
            extension = "." + source_name.rsplit(".", 1)[1][:20]

        stored_filename = "assessment_" + secrets.token_hex(12) + extension
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)

        try:
            uploaded_file.save(file_path)
        except (OSError, ValueError) as exc:
            app.logger.exception("Could not save assessment upload %r: %s", original_filename, exc)
            flash("Could not upload %s. Please try again or use a smaller file." % original_filename, "error")
            continue

        db.session.add(AssessmentFile(
            assessment_id=assessment.id,
            user_id=uid,
            category=category,
            filename=stored_filename,
            original_filename=original_filename
        ))
        saved_count += 1

    if saved_count:
        db.session.commit()
        flash("%d assessment file%s uploaded." % (saved_count, "" if saved_count == 1 else "s"), "success")
    else:
        flash("No files were selected.", "error")

    return redirect(request.form.get("redirect_to") or url_for("assessments"))


@app.route(
    "/add-assessment",
    methods=["POST"]
)
def add_assessment():

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    title = request.form.get(

        "title",

        request.form.get(
            "name",
            ""
        )

    ).strip()


    if title:

        assessment = Assessment(

            user_id=uid,

            title=title,

            subject=request.form.get(
                "subject",
                ""
            ).strip(),

            due_date=normalise_homework_date(
                request.form.get(
                    "due_date",
                    ""
                ).strip()
            ),

            instructions=request.form.get(
                "instructions",
                ""
            ).strip(),

            rubric=request.form.get(
                "rubric",
                ""
            ).strip(),

            resources=request.form.get(
                "resources",
                ""
            ).strip()

        )

        db.session.add(assessment)
        db.session.flush()

        save_assessment_files(assessment, "instructions")
        save_assessment_files(assessment, "rubric")
        save_assessment_files(assessment, "resources")

        db.session.commit()


    return redirect(
        url_for("assessments")
    )


@app.route(
    "/grade-assessment/<int:assessment_id>",
    methods=["POST"]
)
def grade_assessment(assessment_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    assessment = Assessment.query.filter_by(

        id=assessment_id,

        user_id=uid

    ).first_or_404()


    was_completed = bool(assessment.completed)


    score = request.form.get(
        "score",
        ""
    )


    total_score = request.form.get(
        "total_score",
        ""
    )


    try:

        assessment.score = (
            float(score)
            if score
            else None
        )

        assessment.total_score = (
            float(total_score)
            if total_score
            else None
        )

        if assessment.score is not None and assessment.total_score is not None:
            if assessment.total_score <= 0:
                raise ValueError
            if assessment.score < 0 or assessment.score > assessment.total_score:
                flash(
                    "Score must be between 0 and the total score.",
                    "error"
                )
                return redirect(url_for("assessments"))

    except ValueError:

        flash(
            "Enter valid numeric scores. Total score must be greater than 0.",
            "error"
        )

        return redirect(
            url_for("assessments")
        )


    assessment.grade = request.form.get(
        "grade",
        ""
    ).strip()


    effort_text = request.form.get(
        "effort",
        ""
    ).strip()

    happy_text = request.form.get(
        "happy_with_grade",
        ""
    ).strip()

    try:
        assessment.effort = (
            int(effort_text)
            if effort_text
            else None
        )

        if assessment.effort is not None and not 1 <= assessment.effort <= 10:
            raise ValueError

    except ValueError:
        flash(
            "Effort must be a whole number from 1 to 10.",
            "error"
        )
        return redirect(url_for("assessments"))


    if happy_text:
        try:
            happy_value = int(happy_text)
        except ValueError:
            flash(
                "Happiness with your grade must be a whole number from 1 to 10.",
                "error"
            )
            return redirect(url_for("assessments"))

        if not 1 <= happy_value <= 10:
            flash(
                "Happiness with your grade must be a whole number from 1 to 10.",
                "error"
            )
            return redirect(url_for("assessments"))

        assessment.happy_with_grade = str(happy_value)
    else:
        assessment.happy_with_grade = None


    assessment.feedback = request.form.get(
        "feedback",
        ""
    ).strip()


    assessment.completed = True


    assessment.completed_at = datetime.utcnow()


    if not was_completed:
        award_xp(uid, 25, "Assessment graded", commit=False)

    log_audit(uid, "grade", "assessment", assessment.id, assessment.title)

    db.session.commit()


    return redirect(
        url_for("grades")
    )


@app.route(
    "/edit-assessment/<int:assessment_id>",
    methods=["POST"]
)
def edit_assessment(assessment_id):

    required = login_required()

    if required:
        return required

    uid = current_user_id()
    assessment = Assessment.query.filter_by(
        id=assessment_id,
        user_id=uid
    ).first_or_404()

    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    due_date = request.form.get("due_date", "").strip()
    instructions = request.form.get("instructions", "").strip()
    rubric = request.form.get("rubric", "").strip()
    resources = request.form.get("resources", "").strip()
    feedback = request.form.get("feedback", "").strip()

    if not title:
        flash("Assessment title is required.", "error")
        return redirect(url_for("assessments"))

    save_version(uid, "assessment", assessment)
    log_audit(uid, "update", "assessment", assessment.id, title)

    assessment.title = title
    assessment.subject = subject
    assessment.due_date = normalise_homework_date(due_date)
    assessment.instructions = instructions
    assessment.rubric = rubric
    assessment.resources = resources
    assessment.feedback = feedback

    save_assessment_files(assessment, "instructions")
    save_assessment_files(assessment, "rubric")
    save_assessment_files(assessment, "resources")

    db.session.commit()
    flash("Assessment updated.", "success")
    return redirect(url_for("assessments"))


@app.route(
    "/edit-assessment-section/<int:assessment_id>",
    methods=["POST"]
)
def edit_assessment_section(assessment_id):
    """Edit exactly one saved assessment information section.

    This keeps Instructions, Rubric and Resources independently editable so
    changing one section cannot overwrite the other two.
    """
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    assessment = Assessment.query.filter_by(
        id=assessment_id,
        user_id=uid
    ).first_or_404()

    category = request.form.get("category", "").strip().lower()
    content = request.form.get("content", "").strip()

    field_map = {
        "instructions": "instructions",
        "rubric": "rubric",
        "resources": "resources",
    }

    field_name = field_map.get(category)
    if not field_name:
        flash("That assessment section is not editable.", "error")
        return redirect(request.form.get("redirect_to") or url_for("assessments"))

    setattr(assessment, field_name, content)
    db.session.commit()
    flash("Assessment section updated.", "success")
    return redirect(request.form.get("redirect_to") or url_for("assessments"))


@app.route(
    "/delete-assessment/<int:assessment_id>",
    methods=["POST"]
)
def delete_assessment(assessment_id):

    required = login_required()

    if required:
        return required

    uid = current_user_id()
    assessment = Assessment.query.filter_by(
        id=assessment_id,
        user_id=uid
    ).first_or_404()

    move_to_trash(uid, "assessment", assessment, assessment.title)

    assessment.archived = True

    assessment.completed = True

    assessment.completed_at = assessment.completed_at or datetime.utcnow()

    db.session.commit()

    flash("Moved to Trash. You can restore it from Data tools → Trash.", "success")

    return redirect(url_for("assessments"))


    for uploaded_file in list(assessment.uploaded_files):
        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            uploaded_file.filename
        )
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

    db.session.delete(assessment)
    db.session.commit()
    flash("Assessment deleted.", "success")
    return redirect(url_for("assessments"))


@app.route(
    "/ungrade-assessment/<int:assessment_id>",
    methods=["POST"]
)
def ungrade_assessment(assessment_id):

    required = login_required()

    if required:
        return required

    uid = current_user_id()
    assessment = Assessment.query.filter_by(
        id=assessment_id,
        user_id=uid
    ).first_or_404()

    assessment.score = None
    assessment.total_score = None
    assessment.grade = None
    assessment.happy_with_grade = None
    assessment.effort = None
    assessment.feedback = None
    assessment.completed = False
    assessment.completed_at = None

    db.session.commit()
    flash("Assessment returned to ungraded.", "success")
    return redirect(url_for("assessments"))


# =========================================================
# GRADES AND PROGRESS
# =========================================================

DEFAULT_GRADE_SCALE = [
    {"label": "A+", "min": 90, "max": 100},
    {"label": "A",  "min": 80, "max": 89},
    {"label": "B+", "min": 75, "max": 79},
    {"label": "B",  "min": 70, "max": 74},
    {"label": "C+", "min": 65, "max": 69},
    {"label": "C",  "min": 60, "max": 64},
    {"label": "D+", "min": 55, "max": 59},
    {"label": "D",  "min": 50, "max": 54},
    {"label": "E+", "min": 40, "max": 49},
    {"label": "E",  "min": 0,  "max": 39},
    {"label": "N/A", "min": None, "max": None},
]


def get_user_grade_scale(uid):
    saved = GradeScaleSettings.query.filter_by(user_id=uid).first()
    if not saved:
        return [dict(row) for row in DEFAULT_GRADE_SCALE]
    try:
        rows = json.loads(saved.scale_json)
        if isinstance(rows, list) and rows:
            # Deliberately discard legacy numeric-equivalent fields. The scale
            # maps percentages to letter labels only; no grade-number maths.
            cleaned = []
            for row in rows:
                if not isinstance(row, dict) or not str(row.get("label", "")).strip():
                    continue
                label = str(row["label"]).strip()
                if label.upper() == "N/A":
                    cleaned.append({"label": "N/A", "min": None, "max": None})
                    continue
                try:
                    low, high = float(row.get("min")), float(row.get("max"))
                except (TypeError, ValueError):
                    continue
                cleaned.append({"label": label, "min": low, "max": high})
            if cleaned and any(row["label"].upper() == "N/A" for row in cleaned):
                return cleaned
    except (TypeError, ValueError):
        pass
    return [dict(row) for row in DEFAULT_GRADE_SCALE]


def grade_for_percentage(percentage, scale):
    if percentage is None:
        return None
    try:
        value = float(percentage)
    except (TypeError, ValueError):
        return None

    # Compare the real percentage with each band's lower bound. Rounding first
    # promoted 69.5 to 70, 79.5 to 80 and 89.5 to 90, which gave the wrong
    # letter grade at every boundary.
    bands = []
    for row in scale:
        if str(row.get("label", "")).upper() == "N/A":
            continue
        if row.get("min") is None or row.get("max") is None:
            continue
        try:
            bands.append((float(row["min"]), str(row["label"])))
        except (TypeError, ValueError, KeyError):
            continue

    for lower_bound, label in sorted(bands, reverse=True):
        if value >= lower_bound:
            return label
    return None


def assessment_percentage(assessment):
    if assessment.score is not None and assessment.total_score is not None and assessment.total_score > 0:
        return (assessment.score / assessment.total_score) * 100
    value = getattr(assessment, "percentage_override", None)
    return float(value) if value is not None else None


@app.route("/grades")
def grades():
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    scale = get_user_grade_scale(uid)
    all_subjects = Subject.query.filter_by(user_id=uid, archived=False).order_by(Subject.name.asc()).all()
    all_assessments = Assessment.query.filter_by(user_id=uid).filter(Assessment.archived.is_(False)).order_by(
        Assessment.subject.asc(), Assessment.due_date.asc(), Assessment.created_at.asc(), Assessment.id.asc()
    ).all()

    rows = []
    percentages = []
    subject_stats = {}
    overall_points = []
    subject_points = {}
    for assessment in all_assessments:
        percentage = assessment_percentage(assessment)
        saved_label = (assessment.grade or "").strip()
        # A result with a percentage always receives an automatic letter grade
        # from the percentage bands. Manually selected labels are retained only
        # for results without a percentage (or an explicit N/A).
        if saved_label.upper() == "N/A":
            grade_label = "N/A"
        elif percentage is not None:
            grade_label = grade_for_percentage(percentage, scale) or ""
        else:
            grade_label = saved_label

        subject_name = (assessment.subject or "Unassigned").strip() or "Unassigned"
        stats = subject_stats.setdefault(
            subject_name,
            {"percentages": [], "count": 0, "graded_count": 0},
        )
        stats["count"] += 1
        if percentage is not None and grade_label.upper() != "N/A":
            percentages.append(percentage)
            stats["percentages"].append(percentage)
            stats["graded_count"] += 1

            result_date = parse_homework_date(assessment.due_date)
            if result_date is None and assessment.created_at:
                result_date = assessment.created_at.date()
            if result_date is not None:
                subject_points.setdefault(subject_name, []).append({
                    "date": result_date.isoformat(),
                    "label": result_date.strftime("%d %b"),
                    "value": round(percentage, 1),
                    "title": assessment.title,
                })
                overall_points.append({
                    "date": result_date.isoformat(),
                    "label": result_date.strftime("%d %b"),
                    "value": round(percentage, 1),
                    "title": assessment.title,
                })
        rows.append({"assessment": assessment, "percentage": percentage, "grade_label": grade_label})

    overall_average = sum(percentages) / len(percentages) if percentages else None
    average_grade_label = grade_for_percentage(overall_average, scale) if overall_average is not None else None

    try:
        today = datetime.now(
            ZoneInfo(os.environ.get("APP_TIMEZONE", "Australia/Melbourne"))
        ).date()
    except Exception:
        today = app_today()
    current_week = today - timedelta(days=today.weekday())
    result_dates = [
        datetime.strptime(point["date"], "%Y-%m-%d").date()
        for points in subject_points.values()
        for point in points
    ]
    earliest = min(result_dates) if result_dates else current_week
    first_week = min(
        earliest - timedelta(days=earliest.weekday()),
        current_week - timedelta(weeks=4),
    )

    weeks = []
    cursor = first_week
    while cursor <= current_week:
        weeks.append({"date": cursor.isoformat(), "label": cursor.strftime("%d %b")})
        cursor += timedelta(days=7)

    overall_points.sort(key=lambda point: point["date"])

    def cumulative_events(points):
        events = []
        values = []
        for point in sorted(points, key=lambda item: item["date"]):
            values.append(point["value"])
            average = round(sum(values) / len(values), 1)
            if events and events[-1]["date"] == point["date"]:
                events[-1]["value"] = average
                events[-1]["title"] = events[-1]["title"] + " + " + point["title"]
            else:
                events.append({
                    "date": point["date"],
                    "label": point["label"],
                    "value": average,
                    "title": point["title"],
                })
        return events

    chart_subjects = {}
    for name in sorted(subject_points):
        stats = subject_stats.get(name, {})
        values = stats.get("percentages", [])
        average = round(sum(values) / len(values), 1) if values else None
        chart_subjects[name] = {
            "events": cumulative_events(subject_points[name]),
            "average": average,
            "grade": grade_for_percentage(average, scale) if average is not None else "",
        }

    chart_data = {
        "weeks": weeks,
        "start": weeks[0]["date"] if weeks else current_week.isoformat(),
        "end": (current_week + timedelta(days=6)).isoformat(),
        "overall": {
            "events": cumulative_events(overall_points),
            "average": round(overall_average, 1) if overall_average is not None else None,
            "grade": average_grade_label or "",
        },
        "subjects": chart_subjects,
    }

    for stats in subject_stats.values():
        stats["average_percentage"] = (
            sum(stats["percentages"]) / len(stats["percentages"])
            if stats["percentages"] else None
        )
        stats["average_grade_label"] = (
            grade_for_percentage(stats["average_percentage"], scale)
            if stats["average_percentage"] is not None else None
        )

    graded_assessment_count = sum(1 for row in rows if row["percentage"] is not None and row["grade_label"].upper() != "N/A")
    return render_template(
        "grades.html", assessments=all_assessments, rows=rows, subjects=all_subjects,
        subject_stats=subject_stats, overall_average=overall_average,
        average_grade_label=average_grade_label, grade_scale=scale,
        chart_data=chart_data,
        graded_count=graded_assessment_count,
        grade_count=graded_assessment_count,
        ungraded_count=sum(1 for row in rows if row["percentage"] is None and not row["grade_label"]),
    )


@app.route("/grades/save-scale", methods=["POST"])
def save_grade_scale():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    labels = request.form.getlist("scale_label[]")
    mins = request.form.getlist("scale_min[]")
    maxs = request.form.getlist("scale_max[]")
    scale = []
    seen = set()
    try:
        for i, raw_label in enumerate(labels):
            label = raw_label.strip()
            if not label:
                continue
            if label.casefold() in seen:
                raise ValueError("Each grade label must be unique.")
            seen.add(label.casefold())
            is_na = label.upper() == "N/A"
            min_value = None if is_na or i >= len(mins) or not mins[i].strip() else float(mins[i])
            max_value = None if is_na or i >= len(maxs) or not maxs[i].strip() else float(maxs[i])
            if not is_na:
                if min_value is None or max_value is None:
                    raise ValueError(f"{label}: enter a minimum and maximum percentage.")
                if min_value < 0 or max_value > 100 or min_value > max_value:
                    raise ValueError(f"{label}: percentage bounds must be between 0 and 100, with minimum no greater than maximum.")
            scale.append({"label": label, "min": min_value, "max": max_value})
        if not scale or not any(row["label"].upper() == "N/A" for row in scale):
            raise ValueError("Keep an N/A row so non-applicable results can be marked and excluded from averages.")
        numeric = [row for row in scale if row["label"].upper() != "N/A"]
        for i, row in enumerate(numeric):
            for other in numeric[i + 1:]:
                if max(row["min"], other["min"]) <= min(row["max"], other["max"]):
                    raise ValueError(f"The percentage ranges for {row['label']} and {other['label']} overlap.")
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("grades") + "#grading-scale")

    saved = GradeScaleSettings.query.filter_by(user_id=uid).first()
    if not saved:
        saved = GradeScaleSettings(user_id=uid, scale_json=json.dumps(scale))
        db.session.add(saved)
    else:
        saved.scale_json = json.dumps(scale)
    db.session.commit()
    flash("Grading reference saved. Letter grades and averages are calculated from percentages.", "success")
    return redirect(url_for("grades") + "#grading-scale")


@app.route("/grades/update/<int:assessment_id>", methods=["POST"])
def update_grade_row(assessment_id):
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    assessment = Assessment.query.filter_by(id=assessment_id, user_id=uid).first_or_404()
    scale = get_user_grade_scale(uid)
    try:
        score_text = request.form.get("score", "").strip()
        total_text = request.form.get("total_score", "").strip()
        assessment.score = float(score_text) if score_text else None
        assessment.total_score = float(total_text) if total_text else None
        if (assessment.score is None) != (assessment.total_score is None):
            raise ValueError("Enter both score and total score, or leave both blank.")
        if assessment.total_score is not None:
            if assessment.total_score <= 0 or assessment.score < 0 or assessment.score > assessment.total_score:
                raise ValueError("Score must be between 0 and a total score greater than 0.")
        # The Grades page no longer sends a percentage: it is calculated from
        # score and total. Keep any older saved percentage for results that
        # have no raw score, but never overwrite it here.
        if "percentage" in request.form:
            percentage_text = request.form.get("percentage", "").strip()
            if percentage_text:
                percentage = float(percentage_text)
                if percentage < 0 or percentage > 100:
                    raise ValueError("Percentage must be between 0 and 100.")
                assessment.percentage_override = percentage
            else:
                assessment.percentage_override = None
        selected_grade = request.form.get("grade", "").strip()
        if selected_grade and not any(str(row.get("label", "")).casefold() == selected_grade.casefold() for row in scale):
            raise ValueError("Choose a grade from your saved grading reference.")
        current_percentage = assessment_percentage(assessment)
        if selected_grade.upper() == "N/A":
            assessment.grade = "N/A"
        elif current_percentage is not None:
            # Never use a numeric grade equivalent: the percentage determines
            # the letter grade automatically from the editable percentage bands.
            assessment.grade = grade_for_percentage(current_percentage, scale)
        else:
            assessment.grade = selected_grade or None
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("grades"))
    db.session.commit()
    flash("Assessment result saved.", "success")
    return redirect(url_for("grades"))


# =========================================================
# CALENDAR
# =========================================================


def calendar_event_occurrence_date(event, target_date):
    """Return the occurrence date for an event on target_date, or None."""
    # Routes should pass date objects, but normalising here prevents accidental
    # datetime/date comparisons from breaking the calendar.
    if isinstance(target_date, datetime):
        target_date = target_date.date()

    # SQLAlchemy may return a string for older databases, while some existing
    # databases may contain a datetime/date value. Normalise everything to a
    # datetime.date before doing any comparisons.
    raw_first_date = event.event_date
    if isinstance(raw_first_date, datetime):
        first_date = raw_first_date.date()
    elif isinstance(raw_first_date, date):
        first_date = raw_first_date
    else:
        try:
            first_date = datetime.strptime(str(raw_first_date), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    if target_date < first_date:
        return None

    rule = (event.recurrence_rule or "none").strip().lower()
    if rule in ("", "none", "never"):
        return first_date if target_date == first_date else None

    until = None
    if event.recurrence_until:
        try:
            until = datetime.strptime(event.recurrence_until, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            until = None
    if until and target_date > until:
        return None

    exceptions = set()
    for value in (event.recurrence_exceptions or "").split(","):
        value = value.strip()
        if value:
            try:
                exceptions.add(datetime.strptime(value, "%Y-%m-%d").date())
            except ValueError:
                pass
    if target_date in exceptions:
        return None

    delta_days = (target_date - first_date).days

    if rule == "daily":
        try:
            interval = max(1, int(event.recurrence_interval or 1))
        except (TypeError, ValueError):
            interval = 1
        return target_date if delta_days % interval == 0 else None

    if rule == "weekly":
        try:
            interval = max(1, int(event.recurrence_interval or 1))
        except (TypeError, ValueError):
            interval = 1
        return target_date if delta_days % (7 * interval) == 0 else None

    if rule == "monthly":
        months = (target_date.year - first_date.year) * 12 + (target_date.month - first_date.month)
        if months < 0:
            return None
        try:
            interval = max(1, int(event.recurrence_interval or 1))
        except (TypeError, ValueError):
            interval = 1
        if months % interval != 0:
            return None
        # Apple Calendar-style monthly recurrence keeps the day-of-month where
        # possible. For dates such as the 31st, use the last day of shorter months.
        wanted_day = min(first_date.day, pycalendar.monthrange(target_date.year, target_date.month)[1])
        return target_date if target_date.day == wanted_day else None

    if rule == "yearly":
        years = target_date.year - first_date.year
        if years < 0:
            return None
        try:
            interval = max(1, int(event.recurrence_interval or 1))
        except (TypeError, ValueError):
            interval = 1
        if years % interval != 0 or target_date.month != first_date.month:
            return None
        wanted_day = min(first_date.day, pycalendar.monthrange(target_date.year, first_date.month)[1])
        return target_date if target_date.day == wanted_day else None

    return None


def calendar_event_occurs_on(event, target_date):
    return calendar_event_occurrence_date(event, target_date) is not None


def calendar_event_sort_key(event):
    # All-day events first, then timed events in chronological order.
    # Event id provides a stable tie-breaker for simultaneous events.
    time_value = event.start_time or "00:00"
    return (0 if not event.start_time else 1, time_value, event.end_time or "", event.id)


def calendar_event_payload(event, occurrence_date=None):
    occurrence = occurrence_date.strftime("%Y-%m-%d") if occurrence_date else event.event_date
    return {
        "id": event.id,
        "title": event.title,
        "subject": event.subject or "",
        "event_type": event.event_type or "Event",
        "start_time": event.start_time or "",
        "end_time": event.end_time or "",
        "notes": event.notes or "",
        "event_date": occurrence,
        "series_start": event.event_date,
        "recurrence_rule": event.recurrence_rule or "none",
        "recurrence_interval": event.recurrence_interval or 1,
        "recurrence_unit": event.recurrence_unit or "day",
        "recurrence_until": event.recurrence_until or "",
        "recurrence_exceptions": event.recurrence_exceptions or ""
    }

@app.route("/calendar")
def calendar():

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    all_subjects = Subject.query.filter_by(

        user_id=uid, archived=False

    ).order_by(

        Subject.name.asc()

    ).all()


    return render_template(

        "calendar.html",

        subjects=all_subjects

    )


@app.route(
    "/calendar/<date_string>"
)
def calendar_day(date_string):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    try:

        selected_date = datetime.strptime(

            date_string,

            "%Y-%m-%d"

        ).date()


    except ValueError:

        return redirect(
            url_for("calendar")
        )


    display_date = selected_date.strftime(
        "%A, %d/%m/%Y"
    )


    previous_day = (

        selected_date

        - timedelta(days=1)

    ).strftime(
        "%Y-%m-%d"
    )


    next_day = (

        selected_date

        + timedelta(days=1)

    ).strftime(
        "%Y-%m-%d"
    )


    homework = Task.query.filter_by(

        user_id=uid,

        due_date=date_string

    ).order_by(

        Task.id.asc()

    ).all()


    todos = Todo.query.filter_by(

        user_id=uid,

        date=date_string

    ).order_by(

        Todo.created_at.asc()

    ).all()


    assessments = Assessment.query.filter_by(

        user_id=uid,

        due_date=date_string

    ).order_by(

        Assessment.id.asc()

    ).all()


    events = [
        event
        for event in CalendarEvent.query.filter_by(user_id=uid).all()
        if calendar_event_occurs_on(event, selected_date)
    ]

    events.sort(key=calendar_event_sort_key)


    return render_template(

        "calendar_day.html",

        display_date=display_date,

        date_string=date_string,

        previous_day=previous_day,

        next_day=next_day,

        homework=homework,

        todos=todos,

        assessments=assessments,

        events=events,

        subjects=Subject.query.filter_by(user_id=uid, archived=False).order_by(Subject.name.asc()).all()

    )


@app.route("/home-calendar-data/<int:year>/<int:month>")
def home_calendar_data(year, month):
    required = login_required()
    if required:
        return jsonify({"error": "Not logged in"}), 401

    if month < 1 or month > 12:
        return jsonify({"error": "Invalid month"}), 400

    uid = current_user_id()
    import calendar as _calendar
    days_in_month = _calendar.monthrange(year, month)[1]

    tasks = Task.query.filter_by(user_id=uid).all()
    todos = Todo.query.filter_by(user_id=uid).all()
    assessments = Assessment.query.filter_by(user_id=uid).all()
    custom_events = CalendarEvent.query.filter_by(user_id=uid).all()

    result = {}
    for day in range(1, days_in_month + 1):
        target = date(year, month, day)
        key = target.isoformat()
        result[key] = {
            "homework": [
                {"id": item.id, "title": item.title, "subject": getattr(item, "subject", "")}
                for item in tasks
                if str(item.due_date)[:10] == key
            ],
            "todos": [
                {"id": item.id, "title": item.title}
                for item in todos
                if str(item.date)[:10] == key
            ],
            "assessments": [
                {"id": item.id, "title": item.title, "subject": getattr(item, "subject", "")}
                for item in assessments
                if str(item.due_date)[:10] == key
            ],
            "events": [
                calendar_event_payload(item, target)
                for item in custom_events
                if calendar_event_occurs_on(item, target)
            ]
        }

    return jsonify(result)


# =========================================================
# WEB PUSH REMINDERS
# =========================================================

VAPID_FILE = os.path.join(app.instance_path, "vapid_private.pem")
VAPID_SUBJECT = os.environ.get("STUDYOS_VAPID_SUBJECT", "mailto:studyos@example.com")
_push_thread_started = False


def get_vapid_private_pem():
    os.makedirs(app.instance_path, exist_ok=True)
    if not os.path.exists(VAPID_FILE):
        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        with open(VAPID_FILE, "wb") as key_file:
            key_file.write(pem)
        try:
            os.chmod(VAPID_FILE, 0o600)
        except OSError:
            pass
    with open(VAPID_FILE, "rb") as key_file:
        return key_file.read().decode("utf-8")


def get_vapid_public_key():
    pem = get_vapid_private_pem()
    private_key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    public = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(public).rstrip(b"=").decode("ascii")


def send_push_to_user(uid, title, body, url="/calendar#today", tag=None):
    try:
        from pywebpush import webpush, WebPushException
    except Exception:
        return 0
    subscriptions = PushSubscription.query.filter_by(user_id=uid).all()
    sent = 0
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=json.dumps({
                    "title": title,
                    "body": body,
                    "url": url,
                    "tag": tag or ("studyos-" + str(int(time.time()))),
                }),
                vapid_private_key=get_vapid_private_pem(),
                vapid_claims={"sub": VAPID_SUBJECT},
                timeout=10,
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                db.session.delete(sub)
                db.session.commit()
        except Exception:
            continue
    return sent


def send_due_push_reminders():
    """Send 15/10/5-minute web push reminders. Runs in a background thread."""
    now = datetime.now(ZoneInfo("Australia/Melbourne")).replace(tzinfo=None)
    today = now.date()
    events = CalendarEvent.query.all()
    for event in events:
        if not event.start_time:
            continue
        try:
            start_time = datetime.strptime(str(event.start_time)[:5], "%H:%M").time()
        except (TypeError, ValueError):
            continue
        for day_offset in range(0, 31):
            target_day = today + timedelta(days=day_offset)
            if not calendar_event_occurs_on(event, target_day):
                continue
            start_at = datetime.combine(target_day, start_time)
            for minutes in (15, 10, 5):
                notify_at = start_at - timedelta(minutes=minutes)
                if not (notify_at <= now <= notify_at + timedelta(minutes=2)):
                    continue
                key = "push:%s:%s:%s:%s" % (event.user_id, event.id, target_day.isoformat(), minutes)
                if PushReminderSent.query.filter_by(reminder_key=key).first():
                    continue
                if not PushSubscription.query.filter_by(user_id=event.user_id).first():
                    continue
                body = "Starts in %s minutes" % minutes
                if event.start_time:
                    body += " at " + str(event.start_time)[:5]
                if event.subject:
                    body += " · " + event.subject
                send_push_to_user(event.user_id, "SmartStride: " + event.title, body,
                                  url="/calendar#today", tag=key)
                db.session.add(PushReminderSent(user_id=event.user_id, reminder_key=key))
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()


def start_push_worker():
    global _push_thread_started
    if _push_thread_started:
        return
    _push_thread_started = True

    def loop():
        with app.app_context():
            while True:
                try:
                    send_due_push_reminders()
                except Exception:
                    app.logger.exception("Push reminder check failed")
                time.sleep(30)

    threading.Thread(target=loop, daemon=True, name="studyos-push-reminders").start()


@app.route("/sw.js")
def service_worker():
    response = send_from_directory("static", "sw.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/push/public-key")
def push_public_key():
    return jsonify({"publicKey": get_vapid_public_key()})


@app.route("/push/subscribe", methods=["POST"])
def push_subscribe():
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    payload = request.get_json(silent=True) or {}
    endpoint = (payload.get("endpoint") or "").strip()
    keys = payload.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "Invalid subscription"}), 400
    existing = PushSubscription.query.filter_by(user_id=current_user_id(), endpoint=endpoint).first()
    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
    else:
        db.session.add(PushSubscription(user_id=current_user_id(), endpoint=endpoint,
                                        p256dh=p256dh, auth=auth,
                                        user_agent=(request.user_agent.string or "")[:300]))
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/push/unsubscribe", methods=["POST"])
def push_unsubscribe():
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    payload = request.get_json(silent=True) or {}
    endpoint = (payload.get("endpoint") or "").strip()
    if endpoint:
        PushSubscription.query.filter_by(user_id=current_user_id(), endpoint=endpoint).delete()
        db.session.commit()
    return jsonify({"ok": True})


@app.route("/push/test", methods=["POST"])
def push_test():
    if not logged_in():
        return jsonify({"error": "Not logged in"}), 401
    sent = send_push_to_user(current_user_id(), "SmartStride: Test reminder",
                             "Desktop reminders are working. Click to open today’s calendar.",
                             url="/calendar#today", tag="studyos-test-" + str(int(time.time())))
    if not sent:
        return jsonify({"error": "No active push subscription. Enable reminders first."}), 400
    return jsonify({"ok": True, "sent": sent})


@app.route("/calendar-reminders")
def calendar_reminders():
    required = login_required()
    if required:
        return jsonify({"error": "Not logged in"}), 401

    uid = current_user_id()
    try:
        today = datetime.now(ZoneInfo("Australia/Melbourne")).date()
    except Exception:
        today = app_today()

    events = CalendarEvent.query.filter_by(user_id=uid).all()
    result = []
    for day_offset in range(0, 30):
        target_date = today + timedelta(days=day_offset)
        for event in events:
            occurrence = calendar_event_occurrence_date(event, target_date)
            if not occurrence or not event.start_time:
                continue
            try:
                start_time = datetime.strptime(str(event.start_time)[:5], "%H:%M").time()
            except (TypeError, ValueError):
                continue
            start_dt = datetime.combine(occurrence, start_time)
            result.append({
                "id": event.id,
                "title": event.title,
                "subject": event.subject or "",
                "event_type": event.event_type or "Event",
                "event_date": occurrence.strftime("%Y-%m-%d"),
                "start_time": start_time.strftime("%H:%M"),
                "start_at": start_dt.strftime("%Y-%m-%dT%H:%M:00"),
                "notes": event.notes or "",
            })

    result.sort(key=lambda item: (item["start_at"], item["id"]))
    return jsonify({"events": result})


@app.route(
    "/calendar-data/<date_string>"
)
def calendar_data(date_string):

    required = login_required()

    if required:

        return jsonify(
            {
                "error": "Not logged in"
            }
        ), 401


    uid = current_user_id()


    homework = Task.query.filter_by(

        user_id=uid,

        due_date=date_string

    ).all()


    todos = Todo.query.filter_by(

        user_id=uid,

        date=date_string

    ).all()


    assessments = Assessment.query.filter_by(

        user_id=uid,

        due_date=date_string

    ).all()


    try:
        target_date = datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date"}), 400

    events = [
        event
        for event in CalendarEvent.query.filter_by(user_id=uid).all()
        if calendar_event_occurs_on(event, target_date)
    ]
    events.sort(key=calendar_event_sort_key)


    return jsonify(

        {

            "homework": [

                {

                    "id": item.id,

                    "title": item.title,

                    "subject": item.subject

                }

                for item in homework

            ],

            "todos": [

                {

                    "id": item.id,

                    "title": item.title

                }

                for item in todos

            ],

            "assessments": [

                {

                    "id": item.id,

                    "title": item.title,

                    "subject": item.subject

                }

                for item in assessments

            ],

            "events": [
                calendar_event_payload(item, target_date)
                for item in events
            ]

        }

    )


@app.route(
    "/add-calendar-event",
    methods=["POST"]
)
def add_calendar_event():

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    title = request.form.get(
        "title",
        ""
    ).strip()


    event_date = request.form.get(
        "event_date",
        ""
    ).strip()


    recurrence_rule = request.form.get("recurrence_rule", "none").strip().lower() or "none"
    if recurrence_rule == "every_2_days":
        recurrence_rule = "daily"
        recurrence_interval = 2
    elif recurrence_rule == "every_2_weeks":
        recurrence_rule = "weekly"
        recurrence_interval = 2
    else:
        if recurrence_rule not in {"none", "daily", "weekly", "monthly", "yearly", "custom"}:
            recurrence_rule = "none"
        try:
            recurrence_interval = max(1, int(request.form.get("recurrence_interval", "1")))
        except (TypeError, ValueError):
            recurrence_interval = 1

        if recurrence_rule == "custom":
            recurrence_unit = request.form.get("recurrence_unit", "day").strip().lower() or "day"
            if recurrence_unit not in {"day", "week", "month", "year"}:
                recurrence_unit = "day"
            recurrence_rule = {"day": "daily", "week": "weekly", "month": "monthly", "year": "yearly"}[recurrence_unit]
    recurrence_unit = request.form.get("recurrence_unit", "day").strip().lower() or "day"
    if recurrence_unit not in {"day", "week", "month", "year"}:
        recurrence_unit = "day"

    recurrence_until = request.form.get("recurrence_until", "").strip() or None
    if recurrence_rule == "none":
        recurrence_interval = 1
        recurrence_unit = "day"
        recurrence_until = None

    if title and event_date:

        db.session.add(

            CalendarEvent(

                user_id=uid,

                title=title,

                event_date=event_date,

                event_type=request.form.get(
                    "event_type",
                    "Event"
                ).strip(),

                start_time=request.form.get(
                    "start_time",
                    ""
                ).strip(),

                end_time=request.form.get(
                    "end_time",
                    ""
                ).strip(),

                subject=request.form.get(
                    "subject",
                    ""
                ).strip(),

                notes=request.form.get(
                    "notes",
                    ""
                ).strip(),

                recurrence_rule=recurrence_rule,
                recurrence_interval=recurrence_interval,
                recurrence_unit=recurrence_unit,
                recurrence_until=recurrence_until

            )

        )


        db.session.commit()


    redirect_to = request.form.get("redirect_to", "").strip()
    if redirect_to.startswith("/calendar/"):
        return redirect(redirect_to)
    return redirect(url_for("calendar"))



# =========================================================
# EDIT AND DELETE CALENDAR EVENTS
# =========================================================

@app.route("/edit-calendar-event/<int:event_id>", methods=["POST"])
def edit_calendar_event(event_id):
    required = login_required()
    if required:
        return required

    event = CalendarEvent.query.filter_by(
        id=event_id,
        user_id=current_user_id()
    ).first_or_404()

    title = request.form.get("title", "").strip()
    event_date = request.form.get("event_date", "").strip()

    if not title or not event_date:
        flash("Event name and date are required.", "error")
        return redirect(request.form.get("redirect_to", url_for("calendar")))

    recurrence_rule = request.form.get("recurrence_rule", "none").strip().lower() or "none"
    if recurrence_rule == "every_2_days":
        recurrence_rule = "daily"
        recurrence_interval = 2
    elif recurrence_rule == "every_2_weeks":
        recurrence_rule = "weekly"
        recurrence_interval = 2
    else:
        if recurrence_rule not in {"none", "daily", "weekly", "monthly", "yearly", "custom"}:
            recurrence_rule = "none"
        try:
            recurrence_interval = max(1, int(request.form.get("recurrence_interval", "1")))
        except (TypeError, ValueError):
            recurrence_interval = 1
        recurrence_unit = request.form.get("recurrence_unit", "day").strip().lower() or "day"
        if recurrence_unit not in {"day", "week", "month", "year"}:
            recurrence_unit = "day"
        if recurrence_rule == "custom":
            recurrence_rule = {"day": "daily", "week": "weekly", "month": "monthly", "year": "yearly"}[recurrence_unit]

    recurrence_unit = request.form.get("recurrence_unit", "day").strip().lower() or "day"
    if recurrence_unit not in {"day", "week", "month", "year"}:
        recurrence_unit = "day"
    recurrence_until = request.form.get("recurrence_until", "").strip() or None
    if recurrence_rule == "none":
        recurrence_interval = 1
        recurrence_unit = "day"
        recurrence_until = None

    event.title = title
    event.event_date = event_date
    event.event_type = request.form.get("event_type", "Event").strip() or "Event"
    event.start_time = request.form.get("start_time", "").strip()
    event.end_time = request.form.get("end_time", "").strip()
    event.subject = request.form.get("subject", "").strip()
    event.notes = request.form.get("notes", "").strip()
    event.recurrence_rule = recurrence_rule
    event.recurrence_interval = recurrence_interval
    event.recurrence_unit = recurrence_unit
    event.recurrence_until = recurrence_until

    db.session.commit()
    flash("Event updated.", "success")

    redirect_to = request.form.get("redirect_to", "").strip()
    if redirect_to.startswith("/calendar/"):
        return redirect(redirect_to)
    return redirect(url_for("calendar"))

@app.route("/delete-calendar-event/<int:event_id>", methods=["POST"])
def delete_calendar_event(event_id):
    required = login_required()
    if required:
        return required

    event = CalendarEvent.query.filter_by(
        id=event_id,
        user_id=current_user_id()
    ).first_or_404()

    redirect_to = request.form.get("redirect_to", "").strip()
    occurrence_date = request.form.get("occurrence_date", "").strip()
    delete_mode = request.form.get("delete_mode", "this")

    # Non-recurring events can simply be removed.
    if not event.recurrence_rule or event.recurrence_rule == "none":
        db.session.delete(event)
        db.session.commit()
        flash("Event deleted.", "success")
    else:
        # For a recurring series, Apple Calendar-style choices are:
        #   this       = skip only this occurrence
        #   future     = stop the series before this occurrence
        #   all        = remove the entire series
        try:
            occurrence = datetime.strptime(occurrence_date, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            occurrence = None

        if delete_mode == "all":
            db.session.delete(event)
            db.session.commit()
            flash("Recurring event series deleted.", "success")
        elif occurrence is None:
            flash("The recurring event could not be deleted because its date was invalid.", "error")
        elif delete_mode == "future":
            previous_day = occurrence - timedelta(days=1)
            event.recurrence_until = previous_day.strftime("%Y-%m-%d")
            db.session.commit()
            flash("This and all future occurrences were deleted.", "success")
        else:
            existing = [v.strip() for v in (event.recurrence_exceptions or "").split(",") if v.strip()]
            value = occurrence.strftime("%Y-%m-%d")
            if value not in existing:
                existing.append(value)
            event.recurrence_exceptions = ",".join(sorted(existing))
            db.session.commit()
            flash("This occurrence was deleted.", "success")

    if redirect_to.startswith("/calendar/"):
        return redirect(redirect_to)
    return redirect(url_for("calendar"))

# =========================================================
# PANORAMA
# =========================================================

# Panorama music can live in either static/music or the older static/audio
# directory. The app checks both so existing music files continue to work.
MUSIC_DIRECTORIES = [
    os.path.join(BASE_DIR, "static", "music"),
    os.path.join(BASE_DIR, "static", "audio"),
]

for music_directory in MUSIC_DIRECTORIES:
    os.makedirs(music_directory, exist_ok=True)


# These are the selectable Panorama music options.
# White noise is intentionally NOT included.
PANORAMA_MUSIC_OPTIONS = [
    ("No music", "No music"),
    ("brown_noise.mp3", "Brown noise"),
    ("cafe.mp3", "Cafe ambience"),
    ("classical.mp3", "Classical"),
    ("lofi.mp3", "Lo-fi"),
    ("piano.mp3", "Piano"),
    ("rain.mp3", "Rain"),
]


# bell.mp3 is deliberately not required. Panorama uses a browser-generated
# transition beep, so the session still works when there is no bell file.
PANORAMA_INTERNAL_AUDIO = {
    "bell.mp3",
}


def get_music_options():
    return [filename for filename, _label in PANORAMA_MUSIC_OPTIONS]


def get_music_labels():
    # panorama.html uses .items(), so this must be a dictionary.
    return dict(PANORAMA_MUSIC_OPTIONS)


def find_panorama_music(filename):
    """Return the first existing Panorama music directory containing filename."""
    for directory in MUSIC_DIRECTORIES:
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            return directory
    return None


@app.route("/pomodoro")
def pomodoro():
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    all_subjects = Subject.query.filter_by(
        user_id=uid, archived=False
    ).order_by(Subject.name.asc()).all()

    sessions = PanoramaSession.query.filter_by(
        user_id=uid
    ).order_by(PanoramaSession.created_at.desc()).all()

    return render_template(
        "panorama.html",
        subjects=all_subjects,
        sessions=sessions,
        music_options=get_music_labels()
    )


@app.route("/panorama")
def panorama_legacy():
    return redirect(url_for("pomodoro"))


@app.route("/add-pomodoro-session", methods=["POST"])
def add_pomodoro_session():
    required = login_required()
    if required:
        return required

    uid = current_user_id()

    try:
        study_length = max(1, int(request.form.get("study_length", 25)))
        break_length = max(0, int(request.form.get("break_length", 5)))
        cycles = max(1, int(request.form.get("cycles", 4)))
    except (TypeError, ValueError):
        flash("Pomodoro times and cycles must be valid numbers.", "error")
        return redirect(url_for("pomodoro"))

    title = request.form.get("title", "").strip() or "Study Session"

    study_music = request.form.get("study_music", "No music").strip()
    break_music = request.form.get("break_music", "No music").strip()

    allowed_music = set(get_music_options())
    if study_music not in allowed_music:
        study_music = "No music"
    if break_music not in allowed_music:
        break_music = "No music"

    db.session.add(
        PanoramaSession(
            user_id=uid,
            title=title,
            subject=request.form.get("subject", "").strip(),
            study_length=study_length,
            break_length=break_length,
            cycles=cycles,
            study_music=study_music,
            break_music=break_music
        )
    )

    db.session.commit()
    flash("Pomodoro session saved.", "success")
    return redirect(url_for("pomodoro"))


@app.route("/delete-pomodoro/<int:session_id>", methods=["POST"])
def delete_pomodoro(session_id):
    required = login_required()
    if required:
        return required

    item = PanoramaSession.query.filter_by(
        id=session_id,
        user_id=current_user_id()
    ).first_or_404()

    db.session.delete(item)
    db.session.commit()
    flash("Pomodoro session deleted.", "success")
    return redirect(url_for("pomodoro"))


@app.route("/pomodoro/start/<int:session_id>")
def start_pomodoro_session(session_id):
    required = login_required()
    if required:
        return required

    item = PanoramaSession.query.filter_by(
        id=session_id,
        user_id=current_user_id()
    ).first_or_404()

    return render_template(
        "panorama_start.html",
        pomodoro_session=item
    )


@app.route("/pomodoro/complete/<int:session_id>", methods=["POST"])
def complete_pomodoro(session_id):
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    item = PanoramaSession.query.filter_by(id=session_id, user_id=uid).first_or_404()
    if not item.completed_at:
        item.completed_at = datetime.utcnow()
        award_xp(uid, 15, "Pomodoro completed", commit=False)
        log_audit(uid, "complete", "pomodoro", item.id, item.title)
        db.session.commit()
    return jsonify({"ok": True})


@app.route("/pomodoro/music/<path:filename>")
def pomodoro_music(filename):
    """Serve Pomodoro audio from either the current or legacy audio directory."""
    required = login_required()
    if required:
        return required

    allowed_files = set(get_music_options()) | PANORAMA_INTERNAL_AUDIO

    if filename not in allowed_files or filename == "No music":
        abort(404)

    directory = find_panorama_music(filename)
    if directory is None:
        abort(404)

    return send_from_directory(
        directory,
        filename,
        mimetype="audio/mpeg",
        conditional=True
    )


# =========================================================
# RESOURCES PAGE
# =========================================================

def resource_subject_names(uid):
    """Subjects shown in the Resources page and upload form."""
    names = {
        subject.name
        for subject in Subject.query.filter_by(user_id=uid, archived=False).all()
        if subject.name
    }
    names.update(
        assessment.subject
        for assessment in Assessment.query.filter_by(user_id=uid).all()
        if assessment.subject
    )
    names.update(
        task.subject
        for task in Task.query.filter_by(user_id=uid).all()
        if task.subject
    )
    names.update(
        item.subject
        for item in Resource.query.filter_by(user_id=uid).all()
        if item.subject
    )
    names.update(
        section.subject
        for section in ResourceSection.query.filter_by(user_id=uid).all()
        if section.subject
    )
    names.discard("General")
    return sorted(names) + ["General"]


@app.route("/resources")
def resources():
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    tree = {}

    def add_item(subject, subheading, item):
        subject = (subject or "General").strip() or "General"
        subheading = (subheading or "General").strip() or "General"
        tree.setdefault(subject, {}).setdefault(subheading, []).append(item)

    # Subjects with no resources still get an empty section.
    for subject in Subject.query.filter_by(user_id=uid, archived=False).all():
        if subject.name:
            tree.setdefault(subject.name, {})

    # Files attached to assessments.
    assessment_files = (
        AssessmentFile.query.filter_by(user_id=uid)
        .order_by(AssessmentFile.uploaded_at.desc())
        .all()
    )
    for item in assessment_files:
        assessment = item.assessment
        if not assessment:
            continue
        add_item(
            assessment.subject or "General",
            assessment.title,
            {
                "title": item.original_filename or item.filename,
                "source": "Assessment",
                "source_class": "assessment",
                "date": item.uploaded_at,
                "href": url_for("assessment_file", file_id=item.id),
                "resource_id": None,
                "note": None,
            },
        )

    # Files attached to homework.
    homework_files = (
        HomeworkResource.query.filter_by(user_id=uid)
        .order_by(HomeworkResource.uploaded_at.desc())
        .all()
    )
    task_ids = {item.task_id for item in homework_files}
    tasks = (
        {task.id: task for task in Task.query.filter(Task.id.in_(task_ids)).all()}
        if task_ids else {}
    )
    for item in homework_files:
        task = tasks.get(item.task_id)
        if not task:
            continue
        add_item(
            task.subject or "General",
            task.title,
            {
                "title": item.original_filename or item.filename,
                "source": "Homework",
                "source_class": "homework",
                "date": item.uploaded_at,
                "href": url_for("download_task_resource", resource_id=item.id),
                "resource_id": None,
                "note": None,
            },
        )

    # Finished homework files.
    finished_tasks = Task.query.filter(
        Task.user_id == uid,
        Task.finished_file.isnot(None),
        Task.finished_file != "",
    ).all()
    for task in finished_tasks:
        add_item(
            task.subject or "General",
            task.title,
            {
                "title": "Finished homework file",
                "source": "Finished homework",
                "source_class": "homework",
                "date": task.completed_at or task.created_at,
                "href": url_for("download_finished_task", task_id=task.id),
                "resource_id": None,
                "note": None,
            },
        )

    # Files and notes uploaded directly on the Resources page.
    custom_resources = (
        Resource.query.filter_by(user_id=uid)
        .order_by(Resource.uploaded_at.desc())
        .all()
    )
    for item in custom_resources:
        add_item(
            item.subject,
            item.subheading,
            {
                "title": item.title or item.original_filename or "Note",
                "source": "Uploaded" if item.filename else "Note",
                "source_class": "custom",
                "date": item.uploaded_at,
                "href": (
                    url_for("resource_file", resource_id=item.id)
                    if item.filename else None
                ),
                "resource_id": item.id,
                "note": item.note,
            },
        )

    # Empty subheadings the user created on purpose.
    for section in ResourceSection.query.filter_by(user_id=uid).all():
        tree.setdefault(section.subject or "General", {}).setdefault(section.name, [])

    subject_names = resource_subject_names(uid)
    for name in subject_names:
        tree.setdefault(name, {})
    tree.setdefault("General", {})

    subjects = []
    total_items = 0
    for name in subject_names:
        groups = tree.get(name, {})
        group_list = []
        for group_name in sorted(groups):
            items = sorted(
                groups[group_name],
                key=lambda entry: entry["date"] or datetime.min,
                reverse=True,
            )
            total_items += len(items)
            group_list.append({"name": group_name, "entries": items})
        subjects.append({
            "name": name,
            "groups": group_list,
            "count": sum(len(group["entries"]) for group in group_list),
        })

    subheading_options = sorted({
        group["name"]
        for subject in subjects
        for group in subject["groups"]
    })

    return render_template(
        "resources.html",
        subjects=subjects,
        subject_names=subject_names,
        subheading_options=subheading_options,
        total_items=total_items,
    )


@app.route("/resources/upload", methods=["POST"])
def upload_resource():
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    subject = request.form.get("subject", "General").strip() or "General"
    if subject not in resource_subject_names(uid):
        subject = "General"

    subheading = request.form.get("subheading", "General").strip()[:200] or "General"
    title = request.form.get("title", "").strip()[:200]
    note = request.form.get("note", "").strip()

    uploaded_file = request.files.get("file")
    stored_filename = None
    original_filename = None

    if uploaded_file and uploaded_file.filename:
        original_filename = uploaded_file.filename.strip()
        if not upload_is_allowed(original_filename):
            flash(
                "%s: that file type is not allowed." % original_filename,
                "error",
            )
            return redirect(url_for("resources"))

        extension = upload_extension(original_filename)
        stored_filename = "resource_" + secrets.token_hex(12) + extension
        try:
            uploaded_file.save(
                os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)
            )
        except (OSError, ValueError):
            flash("Could not save that file. Try again or use a smaller file.", "error")
            return redirect(url_for("resources"))

    if not stored_filename and not note:
        flash("Choose a file or write a note before uploading.", "error")
        return redirect(url_for("resources"))

    db.session.add(
        Resource(
            user_id=uid,
            subject=subject,
            subheading=subheading,
            title=title or None,
            filename=stored_filename,
            original_filename=original_filename,
            note=note or None,
        )
    )

    section = ResourceSection.query.filter_by(
        user_id=uid,
        subject=subject,
        name=subheading,
    ).first()
    if not section:
        db.session.add(
            ResourceSection(user_id=uid, subject=subject, name=subheading)
        )

    db.session.commit()
    flash("Resource added.", "success")
    return redirect(url_for("resources"))


@app.route("/resources/section", methods=["POST"])
def add_resource_section():
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    subject = request.form.get("subject", "General").strip() or "General"
    if subject not in resource_subject_names(uid):
        subject = "General"

    name = request.form.get("name", "").strip()[:200]
    if not name:
        flash("Enter a name for the subheading.", "error")
        return redirect(url_for("resources"))

    existing = ResourceSection.query.filter_by(
        user_id=uid,
        subject=subject,
        name=name,
    ).first()
    if not existing:
        db.session.add(ResourceSection(user_id=uid, subject=subject, name=name))
        db.session.commit()
        flash("Subheading added to %s." % subject, "success")
    else:
        flash("That subheading already exists.", "info")

    return redirect(url_for("resources"))


@app.route("/resources/file/<int:resource_id>")
def resource_file(resource_id):
    required = login_required()
    if required:
        return required

    item = Resource.query.filter_by(
        id=resource_id,
        user_id=current_user_id(),
    ).first_or_404()

    if not item.filename:
        abort(404)

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        item.filename,
        download_name=item.original_filename or item.filename,
        as_attachment=(
            upload_extension(item.filename) not in INLINE_IMAGE_EXTENSIONS
        ),
    )


@app.route("/resources/delete/<int:resource_id>", methods=["POST"])
def delete_resource(resource_id):
    required = login_required()
    if required:
        return required

    item = Resource.query.filter_by(
        id=resource_id,
        user_id=current_user_id(),
    ).first_or_404()

    if item.filename:
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], item.filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

    db.session.delete(item)
    db.session.commit()
    flash("Resource deleted.", "success")
    return redirect(url_for("resources"))


# =========================================================
# PRACTICE TEST BUILDER
# =========================================================

PRACTICE_STOPWORDS = set("""
the a an and or but if then than that this these those of to in on at by for with
from as is are was were be been being it its their there here which who whom whose
what when where why how not no can could should would may might will shall do does
did have has had about into over under between among during before after above below
more most less least very much many some any each other such only also own same so
because while both few all however therefore although though since until through
""".split())

PRACTICE_VERB_STARTS = (
    "absorbed", "released", "used", "transported", "found", "located", "made",
    "called", "known", "produced", "formed", "converted", "stored", "needed",
    "required", "measured", "caused", "created", "taken", "moved", "passed",
    "diffused", "broken", "combined", "covered", "filled", "contained",
)


def extract_document_text(filename, data):
    """Extract readable text from a PDF, Word, PowerPoint, or text file."""
    extension = upload_extension(filename)

    if extension == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            return "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except Exception:
            return ""

    if extension == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                xml = archive.read("word/document.xml").decode("utf-8", "ignore")
            xml = xml.replace("</w:p>", "\n")
            return re.sub(r"<[^>]+>", " ", xml)
        except Exception:
            return ""

    if extension == ".pptx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                parts = []
                for name in sorted(archive.namelist()):
                    if re.match(r"ppt/slides/slide\d+\.xml$", name):
                        xml = archive.read(name).decode("utf-8", "ignore")
                        parts.append(re.sub(r"<[^>]+>", " ", xml))
                return "\n".join(parts)
        except Exception:
            return ""

    if extension in (".txt", ".md", ".csv"):
        return data.decode("utf-8", "ignore")

    return ""


def safe_remote_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        if parsed.hostname.lower() in ("localhost",):
            return False
        address = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        return not (
            address.is_private or address.is_loopback
            or address.is_link_local or address.is_reserved
        )
    except Exception:
        return False


def fetch_remote_document(url):
    """Download a public OneDrive/share link and return (text, error)."""
    if not safe_remote_url(url):
        return "", "That link is not allowed. Use a public https link."

    try:
        response = requests.get(
            url,
            timeout=25,
            allow_redirects=True,
            headers={"User-Agent": "SmartStride/1.0"},
        )
        response.raise_for_status()
    except Exception as exc:
        return "", "Could not download that link: %s" % exc

    if len(response.content) > 15 * 1024 * 1024:
        return "", "That file is larger than the 15 MB limit."

    content_type = (response.headers.get("content-type") or "").lower()
    if "text/html" in content_type:
        return "", (
            "That link opened a web page, not a file. Use a direct download "
            "link, or download the file and upload it from your laptop."
        )

    if "pdf" in content_type:
        extension = ".pdf"
    elif "wordprocessingml" in content_type or "msword" in content_type:
        extension = ".docx"
    elif "presentationml" in content_type:
        extension = ".pptx"
    elif "text/plain" in content_type:
        extension = ".txt"
    else:
        extension = os.path.splitext(urlparse(response.url).path)[1].lower()

    if extension not in (".pdf", ".docx", ".pptx", ".txt", ".md", ".csv"):
        return "", (
            "That link did not return a supported document. "
            "Use a direct OneDrive download link."
        )

    text = extract_document_text("onedrive" + extension, response.content)
    if not text.strip():
        return "", "Could not read text from that file. It may be a scanned PDF or an image."
    return text, ""


def practice_resource_options(uid):
    """Existing SmartStride files that can be used as practice-test sources."""
    options = []

    for item in AssessmentFile.query.filter_by(user_id=uid).all():
        assessment = item.assessment
        if assessment:
            options.append({
                "value": "assessment:%d" % item.id,
                "label": "Assessment — %s — %s" % (
                    assessment.title,
                    item.original_filename or item.filename,
                ),
            })

    for item in HomeworkResource.query.filter_by(user_id=uid).all():
        task = Task.query.filter_by(id=item.task_id, user_id=uid).first()
        if task:
            options.append({
                "value": "homework:%d" % item.id,
                "label": "Homework — %s — %s" % (
                    task.title,
                    item.original_filename or item.filename,
                ),
            })

    for item in Resource.query.filter_by(user_id=uid).all():
        if item.filename:
            options.append({
                "value": "resource:%d" % item.id,
                "label": "Resources — %s — %s" % (
                    item.subheading,
                    item.original_filename or item.filename,
                ),
            })

    finished = Task.query.filter(
        Task.user_id == uid,
        Task.finished_file.isnot(None),
        Task.finished_file != "",
    ).all()
    for task in finished:
        options.append({
            "value": "finished:%d" % task.id,
            "label": "Finished homework — %s" % task.title,
        })

    return options


def practice_source_texts(uid, values):
    texts = []

    for value in values:
        kind, _, raw_id = value.partition(":")
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        filename = None
        display_name = None

        if kind == "assessment":
            item = AssessmentFile.query.filter_by(id=item_id, user_id=uid).first()
            if item:
                filename = item.filename
                display_name = item.original_filename or item.filename
        elif kind == "homework":
            item = HomeworkResource.query.filter_by(id=item_id, user_id=uid).first()
            if item:
                filename = item.filename
                display_name = item.original_filename or item.filename
        elif kind == "resource":
            item = Resource.query.filter_by(id=item_id, user_id=uid).first()
            if item:
                filename = item.filename
                display_name = item.original_filename or item.filename
        elif kind == "finished":
            item = Task.query.filter_by(id=item_id, user_id=uid).first()
            if item:
                filename = item.finished_file
                display_name = item.title

        if not filename:
            continue

        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if not os.path.isfile(path):
            continue

        try:
            with open(path, "rb") as source:
                data = source.read()
        except OSError:
            continue

        text = extract_document_text(display_name or filename, data)
        if text.strip():
            texts.append(text)

    return texts


def practice_sentences(text):
    text = re.sub(r"\s+", " ", text).strip()
    chunks = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text)
    sentences = []
    seen = set()
    for chunk in chunks:
        chunk = chunk.strip(" \"'")
        words = chunk.split()
        if 7 <= len(words) <= 50 and 40 <= len(chunk) <= 360 and chunk not in seen:
            seen.add(chunk)
            sentences.append(chunk)
    return sentences


def clean_term(term):
    term = re.sub(r"^(the|a|an)\s+", "", term.strip(), flags=re.I)
    return term.strip(" .,:;")


def shorten(text, limit=150):
    text = re.sub(r"\s+", " ", text).strip(" .")
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + "…"


def analyse_sentence(sentence):
    """Work out what kind of study fact a sentence contains."""
    text = sentence.strip()
    record = {"text": text, "kind": "general"}

    checks = [
        ("function", r"^(?:The |A |An )?(?P<term>[A-Z][A-Za-z0-9\s\-']{2,70}?)\s+(?:is used for|is used to|helps|allows|enables|serves to|functions to)\s+(?P<detail>.{8,})$"),
        ("location", r"^(?:The |A |An )?(?P<term>[A-Z][A-Za-z0-9\s\-']{2,70}?)\s+(?:is|are)\s+(?:found|located|present)\s+(?:in|inside|within|on)\s+(?P<detail>.{5,})$"),
        ("list", r"^(?:The |A |An )?(?P<term>[A-Z][A-Za-z0-9\s\-']{2,70}?)\s+(?:includes|consists of|contains|is made up of)\s+(?P<detail>.{5,})$"),
        ("definition", r"^(?:The |A |An )?(?P<term>[A-Z][A-Za-z0-9\s\-']{2,70}?)\s+(?:is|are|means|refers to|is defined as)\s+(?P<detail>.{10,})$"),
    ]
    for kind, pattern in checks:
        match = re.match(pattern, text, re.I)
        if match:
            record["kind"] = kind
            record["term"] = clean_term(match.group("term"))
            record["detail"] = match.group("detail").strip(" .")
            return record

    match = re.match(r"^(?P<effect>.{12,}?)\s+(?:because|since|as)\s+(?P<cause>.{8,})$", text, re.I)
    if match:
        record["kind"] = "cause"
        record["cause"] = match.group("cause").strip(" .")
        record["effect"] = match.group("effect").strip(" .")
        return record

    match = re.match(r"^(?P<cause>.{10,}?)\s+(?:causes|leads to|results in|produces)\s+(?P<effect>.{6,})$", text, re.I)
    if match:
        record["kind"] = "cause"
        record["cause"] = match.group("cause").strip(" .")
        record["effect"] = match.group("effect").strip(" .")
        return record

    match = re.match(r"^(?P<a>.{10,}?)\s+(?:whereas|while|but|unlike|compared (?:to|with))\s+(?P<b>.{8,})$", text, re.I)
    if match:
        record["kind"] = "comparison"
        record["a"] = match.group("a").strip(" .")
        record["b"] = match.group("b").strip(" .")
        return record

    lower = text.lower()
    if any(word in lower for word in ("first", "then", "next", "finally", "stage", "step", "process")):
        record["kind"] = "process"
        return record
    if any(word in lower for word in ("important", "essential", "crucial", "needed for", "vital")):
        record["kind"] = "importance"
        return record
    if any(word in lower for word in ("for example", "such as", "e.g.")):
        record["kind"] = "example"
        return record

    return record


def practice_terms(sentences):
    counts = {}
    for sentence in sentences:
        for match in re.findall(r"\b[A-Z][A-Za-z]{2,}(?:\s+[A-Z][A-Za-z]{2,}){0,2}\b", sentence):
            term = match.strip()
            if term.lower() in PRACTICE_STOPWORDS:
                continue
            counts[term] = counts.get(term, 0) + 1
        for match in re.findall(r"\b[a-z]{7,}\b", sentence):
            if match in PRACTICE_STOPWORDS or match.endswith(("ing", "ed", "ly")):
                continue
            counts[match] = counts.get(match, 0) + 1
    return sorted(counts, key=lambda term: (-counts[term], -len(term), term.lower()))


def build_practice_questions(text, types, count, difficulty, year_level="", subject="", topic=""):
    """Build real study questions (definitions, functions, causes, comparisons...)."""
    sentences = practice_sentences(text)
    if len(sentences) < 4:
        return []

    try:
        year = int(year_level)
    except (TypeError, ValueError):
        year = 9
    context = topic or subject or "this topic"

    records = [analyse_sentence(sentence) for sentence in sentences]
    by_kind = {}
    for record in records:
        by_kind.setdefault(record["kind"], []).append(record)

    mcq_pool = []
    fill_pool = []
    short_pool = []
    seen = set()

    def add(kind, question, answer, explanation, options=None):
        if question in seen:
            return
        seen.add(question)
        item = {
            "type": kind,
            "question": question,
            "answer": answer,
            "explanation": explanation,
            "options": options or [],
            "marks": 1 if kind in ("mcq", "fill") else 3,
            "marking_scheme": [explanation] if explanation else [],
            "evidence": explanation,
        }
        if kind == "mcq":
            mcq_pool.append(item)
        elif kind == "fill":
            fill_pool.append(item)
        else:
            short_pool.append(item)

    requested = [kind for kind in types if kind in ("mcq", "fill", "short")]
    if not requested:
        requested = ["short"]

    definitions = [
        r for r in by_kind.get("definition", [])
        if len(r.get("detail", "")) >= 12
        and not r["detail"].lower().startswith(PRACTICE_VERB_STARTS)
    ]
    for index, record in enumerate(definitions):
        term = record["term"]
        detail = shorten(record["detail"])
        others = list(dict.fromkeys(
            shorten(other["detail"]) for other in definitions if other is not record
        ))[:6]
        question_type = requested[index % len(requested)]

        if question_type == "mcq" and len(others) >= 3:
            term_options = list(dict.fromkeys(
                other["term"] for other in definitions if other is not record
            ))[:6]
            if len(term_options) >= 3 and random.random() < 0.5:
                options = [term] + random.sample(term_options, 3)
                random.shuffle(options)
                add(
                    "mcq",
                    "Which term matches this definition?\n\n\u201c%s\u201d" % detail,
                    term,
                    record["text"],
                    options,
                )
            else:
                options = [detail] + random.sample(others, 3)
                random.shuffle(options)
                add("mcq", "Which statement best describes %s?" % term, detail, record["text"], options)
        elif question_type == "fill":
            blanked = re.sub(r"\b" + re.escape(term) + r"\b", "_____", record["text"], count=1, flags=re.I)
            if "_____" in blanked:
                add("fill", "Fill in the blank: \u201c%s\u201d" % blanked, term, record["text"])
            else:
                add("short", "Define %s." % term, record["text"], record["text"])
        elif year >= 11:
            add("short", "Explain the significance of %s in %s." % (term, context), record["text"], record["text"])
        else:
            add("short", "Define %s." % term, record["text"], record["text"])

    functions = by_kind.get("function", [])
    for record in functions:
        term = record["term"]
        detail = shorten(record["detail"])
        others = list(dict.fromkeys(
            shorten(other["detail"]) for other in functions if other is not record
        ))[:6]
        if "mcq" in requested and len(others) >= 3:
            options = [detail] + random.sample(others, 3)
            random.shuffle(options)
            add("mcq", "What is the function of %s?" % term, detail, record["text"], options)
        else:
            add("short", "What is the function of %s?" % term, record["text"], record["text"])

    locations = by_kind.get("location", [])
    for record in locations:
        term = record["term"]
        detail = shorten(record["detail"])
        others = list(dict.fromkeys(
            shorten(other["detail"]) for other in locations if other is not record
        ))[:6]
        if "mcq" in requested and len(others) >= 3:
            options = [detail] + random.sample(others, 3)
            random.shuffle(options)
            add("mcq", "Where is %s found?" % term, detail, record["text"], options)
        else:
            add("short", "Where is %s found?" % term, record["text"], record["text"])

    for record in by_kind.get("cause", []):
        add("short", "Why does %s happen?" % shorten(record["effect"], 90), record["cause"], record["text"])
        add("short", "What is the effect of %s?" % shorten(record["cause"], 90), record["effect"], record["text"])

    for record in by_kind.get("comparison", []):
        add("short", "Compare %s and %s." % (shorten(record["a"], 70), shorten(record["b"], 70)), record["text"], record["text"])

    for record in by_kind.get("process", []):
        add("short", "Describe the process of %s." % context, record["text"], record["text"])

    for record in by_kind.get("list", []):
        add("short", "List what %s includes." % record["term"], record["text"], record["text"])

    for record in by_kind.get("importance", []):
        term = record.get("term") or context
        add("short", "Why is %s important?" % term, record["text"], record["text"])

    for record in by_kind.get("example", []):
        add("short", "Give an example of %s." % context, record["text"], record["text"])

    # Make sure there are enough questions even if the text has few patterns.
    if len(mcq_pool) + len(fill_pool) + len(short_pool) >= count:
        term_fallback = []
    else:
        term_fallback = practice_terms(sentences)

    for term in term_fallback:
        if len(short_pool) >= count:
            break
        if not term[0].isupper():
            continue
        if any(term.lower() in item["question"].lower() for item in mcq_pool + fill_pool + short_pool):
            continue
        sentence = next(
            (s for s in sentences if re.search(r"\b" + re.escape(term) + r"\b", s, re.I)),
            None,
        )
        if sentence:
            add(
                "short",
                "Explain %s in the context of %s." % (term, context),
                sentence,
                sentence,
            )

    if not mcq_pool and not short_pool and not fill_pool:
        return []

    # Easy tests get more multiple-choice/fill; hard tests get more explanation.
    if difficulty == "easy":
        requested.sort(key=lambda kind: 0 if kind in ("mcq", "fill") else 1)
    elif difficulty == "hard":
        requested.sort(key=lambda kind: 0 if kind == "short" else 1)

    pools = {"mcq": mcq_pool, "fill": fill_pool, "short": short_pool}
    for pool in pools.values():
        random.shuffle(pool)

    chosen = []
    indexes = {kind: 0 for kind in requested}
    while len(chosen) < count:
        added = False
        for kind in requested:
            pool = pools[kind]
            index = indexes[kind]
            if index < len(pool):
                chosen.append(pool[index])
                indexes[kind] = index + 1
                added = True
                if len(chosen) >= count:
                    break
        if not added:
            break

    return chosen



def parse_ai_questions(content, requested_types, count):
    """Parse and validate the JSON returned by the AI model."""
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return []

    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        try:
            payload = json.loads(text[start:end + 1])
        except (TypeError, ValueError):
            return []

    if isinstance(payload, list):
        raw_questions = payload
    elif isinstance(payload, dict):
        raw_questions = payload.get("questions", [])
    else:
        return []

    aliases = {
        "mcq": "mcq",
        "multiple choice": "mcq",
        "multiple-choice": "mcq",
        "fill": "fill",
        "fill in the blank": "fill",
        "fill-in-the-blank": "fill",
        "short": "short",
        "short answer": "short",
        "short-answer": "short",
    }

    questions = []
    seen = set()
    for item in raw_questions:
        if not isinstance(item, dict):
            continue

        question_type = aliases.get(str(item.get("type", "")).strip().lower())
        if not question_type:
            continue
        if requested_types and question_type not in requested_types:
            continue

        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        explanation = str(item.get("explanation", "")).strip()
        evidence = str(
            item.get("evidence") or item.get("source_quote") or ""
        ).strip()
        options = [
            str(option).strip()
            for option in (item.get("options") or [])
            if str(option).strip()
        ]

        scheme = item.get("marking_scheme") or item.get("markingScheme") or []
        if isinstance(scheme, str):
            scheme = [
                line.strip("-•; ").strip()
                for line in scheme.splitlines()
                if line.strip()
            ]
        elif isinstance(scheme, list):
            scheme = [str(point).strip() for point in scheme if str(point).strip()]
        else:
            scheme = []

        try:
            marks = int(item.get("marks", 1))
        except (TypeError, ValueError):
            marks = 1
        marks = max(1, min(10, marks))

        if question_type == "short" and not answer:
            answer = explanation or (scheme[0] if scheme else "")
        if not question or not answer or question in seen:
            continue

        if question_type == "mcq":
            if len(options) != 4:
                continue
            letter_match = re.match(r"^(?:option\s*)?([A-Da-d])(?:[\).:\s-]|$)", answer)
            if letter_match:
                index = "ABCD".index(letter_match.group(1).upper())
                if index < len(options):
                    answer = options[index]
            matching = next(
                (option for option in options if option.casefold() == answer.casefold()),
                None,
            )
            if not matching:
                matching = next(
                    (option for option in options
                     if option.casefold().startswith(answer.casefold())
                     or answer.casefold().startswith(option.casefold())),
                    None,
                )
            if not matching:
                continue
            answer = matching
            marks = 1
        elif question_type == "fill":
            if "____" not in question:
                continue
            marks = max(1, min(2, marks))
        else:
            if not scheme:
                scheme = [explanation] if explanation else []
            if not explanation:
                explanation = answer

        seen.add(question)
        questions.append({
            "type": question_type,
            "question": question,
            "options": options,
            "answer": answer,
            "explanation": explanation,
            "marks": marks,
            "marking_scheme": scheme,
            "evidence": evidence,
        })

    return questions[:count]


def source_excerpt(text, limit=8000):
    """Drop exam cover-page boilerplate and keep two useful slices."""
    skip = (
        "please", "do not", "time allowed", "instructions", "total marks",
        "name:", "student", "non-calc", "calculator", "this exam", "section",
        "reading time", "working time",
    )
    lines = []
    for line in (text or "").splitlines():
        clean = line.strip()
        if not clean:
            continue
        if any(clean.lower().startswith(prefix) for prefix in skip):
            continue
        lines.append(clean)
    cleaned = "\n".join(lines)
    if len(cleaned) <= limit:
        return cleaned
    half = limit // 2
    middle = len(cleaned) // 2
    return cleaned[:half] + "\n...\n" + cleaned[middle:middle + half]


def generate_ai_questions(text, types, count, difficulty, year_level, subject, topic, extra=""):
    """Generate a real practice test with the free AI endpoint."""
    type_names = {
        "mcq": "multiple choice",
        "fill": "fill in the blank",
        "short": "short answer",
    }
    requested = ", ".join(type_names[t] for t in types if t in type_names)
    if not requested:
        requested = "short answer"

    prompt = (
        "You are an expert Australian curriculum teacher.\n\n"
        "Write a practice test.\n"
        "Subject: " + (subject or "General") + "\n"
        "Topic: " + (topic or "the supplied material") + "\n"
        "Question types: " + requested + "\n"
        "Only these exact question types are allowed: " + requested + ". Do not include any other type.\n"
        "Number of questions: exactly " + str(count) + "\n"
        "You MUST return exactly " + str(count) + " questions. Count them before returning.\n"
"\n"
        "Use ONLY the SOURCE below. Do not use outside facts.\n"
        "Every question MUST be directly answerable from a specific sentence in the source.\n"
        "For every question, include an evidence field: copy a short exact quote from the source that supports the answer.\n"
        "Match the difficulty and year level. Do not make trick questions. Do not repeat a question.\n"
        "For every question include marks (a whole number) and marking_scheme (an array of short strings explaining how to award the marks).\n"
        "Multiple choice: exactly 4 options, the answer must exactly match one option, and marks must be 1.\n"
        "Short answer: give a model answer, marks between 2 and 5, and a marking_scheme listing the points required.\n"
        "Fill in the blank: the question must contain _____, marks between 1 and 2.\n\n"
        "Return ONLY valid JSON in this exact shape:\n"
        "{\"questions\":[\n"
        "  {\"type\":\"mcq\",\"question\":\"...\",\"options\":[\"...\",\"...\",\"...\",\"...\"],\"answer\":\"...\",\"marks\":1,\"explanation\":\"...\",\"marking_scheme\":[\"1 mark for the correct option\"],\"evidence\":\"...\"},\n"
        "  {\"type\":\"short\",\"question\":\"...\",\"options\":[],\"answer\":\"...\",\"marks\":3,\"explanation\":\"...\",\"marking_scheme\":[\"1 mark for ...\",\"1 mark for ...\"],\"evidence\":\"...\"},\n"
        "  {\"type\":\"fill\",\"question\":\"... _____ ...\",\"options\":[],\"answer\":\"...\",\"marks\":1,\"explanation\":\"...\",\"marking_scheme\":[\"1 mark for the correct word\"],\"evidence\":\"...\"}\n"
        "]}\n\n"
        + (extra + "\n\n" if extra else "")
        + "SOURCE:\n" + source_excerpt(text, 8000)
    )

    def read_key(env_name, file_name):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
        try:
            with open(os.path.join(BASE_DIR, "instance", file_name), "r", encoding="utf-8") as key_file:
                return key_file.read().strip()
        except OSError:
            return ""

    openai_key = read_key("OPENAI_API_KEY", "openai_key")
    groq_key = read_key("GROQ_API_KEY", "groq_key")

    if openai_key:
        endpoint = "https://api.openai.com/v1/chat/completions"
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        headers = {"Authorization": "Bearer " + openai_key}
    elif groq_key:
        endpoint = "https://api.groq.com/openai/v1/chat/completions"
        model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
        headers = {"Authorization": "Bearer " + groq_key}
    else:
        endpoint = "https://text.pollinations.ai/openai"
        model = "openai-fast"
        headers = {}

    max_tokens = 2500
    if openai_key or groq_key:
        max_tokens = min(8000, max(2500, 600 + count * 220))

    response = requests.post(
        endpoint,
        headers=headers,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an expert teacher. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    return parse_ai_questions(content, types, count)


@app.route("/practice")
def practice():
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    subject_names = sorted({
        value for value in (
            [subject.name for subject in Subject.query.filter_by(user_id=uid, archived=False).all()]
            + [assessment.subject for assessment in Assessment.query.filter_by(user_id=uid).all()]
            + [task.subject for task in Task.query.filter_by(user_id=uid).all()]
        ) if value
    })

    recent = (
        PracticeTest.query.filter_by(user_id=uid)
        .order_by(PracticeTest.created_at.desc())
        .limit(50)
        .all()
    )

    return render_template(
        "practice.html",
        subject_names=subject_names,
        resource_options=practice_resource_options(uid),
        recent_tests=recent,
    )


@app.route("/practice/generate", methods=["POST"])
def generate_practice():
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    subject = request.form.get("subject", "").strip()
    topic = request.form.get("topic", "").strip()
    year_level = request.form.get("year_level", "").strip()
    difficulty = request.form.get("difficulty", "medium").strip()
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"

    try:
        count = int(request.form.get("count", "10"))
    except (TypeError, ValueError):
        count = 10
    count = max(1, min(10, count))

    types = request.form.getlist("types") or ["mcq", "fill", "short"]
    test_name = (subject + (" — " + topic if topic else "")).strip() or "Practice test"
    texts = []
    sources = []

    for uploaded_file in request.files.getlist("files"):
        if not uploaded_file or not uploaded_file.filename:
            continue
        data = uploaded_file.read()
        text = extract_document_text(uploaded_file.filename, data)
        if text.strip():
            texts.append(text)
            sources.append(uploaded_file.filename)

        # Keep the original file in Resources under the subject and test name.
        if upload_is_allowed(uploaded_file.filename):
            stored_name = "practice_" + secrets.token_hex(12) + upload_extension(uploaded_file.filename)
            try:
                with open(os.path.join(app.config["UPLOAD_FOLDER"], stored_name), "wb") as saved_file:
                    saved_file.write(data)
                db.session.add(Resource(
                    user_id=uid,
                    subject=subject or "General",
                    subheading=test_name,
                    title=uploaded_file.filename,
                    filename=stored_name,
                    original_filename=uploaded_file.filename,
                ))
                section = ResourceSection.query.filter_by(
                    user_id=uid, subject=subject or "General", name=test_name
                ).first()
                if not section:
                    db.session.add(ResourceSection(
                        user_id=uid, subject=subject or "General", name=test_name
                    ))
            except OSError:
                pass

    onedrive_url = request.form.get("onedrive_url", "").strip()
    if onedrive_url:
        text, error = fetch_remote_document(onedrive_url)
        if error:
            flash(error, "error")
        elif text.strip():
            texts.append(text)
            sources.append("OneDrive link")

    selected = request.form.getlist("resources")
    selected_texts = practice_source_texts(uid, selected)
    texts.extend(selected_texts)
    if selected_texts:
        sources.append("%d SmartStride resource(s)" % len(selected_texts))

    combined = "\n".join(texts)
    if len(combined.strip()) < 250:
        flash(
            "I could not find enough text. Add a PDF, Word document, text file, "
            "or a SmartStride resource with readable text.",
            "error",
        )
        return redirect(url_for("practice"))

    ai_questions = []
    ai_error = ""
    batch_size = 10
    attempts = 0

    while len(ai_questions) < count and attempts < 5:
        attempts += 1
        need = min(batch_size, count - len(ai_questions))
        try:
            batch = generate_ai_questions(
                combined, types, min(30, need + 1),
                difficulty, year_level, subject, topic,
            )
        except Exception as exc:
            ai_error = str(exc)[:300]
            break

        existing = {item["question"] for item in ai_questions}
        added = 0
        for item in batch:
            if len(ai_questions) >= count:
                break
            if item["question"] not in existing:
                ai_questions.append(item)
                existing.add(item["question"])
                added += 1
        if added == 0:
            break

    questions = ai_questions[:count]
    generator = "ai"

    if not questions:
        flash(
            "The AI service could not generate a test, so no test was saved. "
            "Please wait 45 seconds and try again.",
            "error",
        )
        return redirect(url_for("practice"))

    total_marks = sum(int(item.get("marks", 1)) for item in questions)
    test = PracticeTest(
        user_id=uid,
        subject=subject or None,
        topic=topic or None,
        year_level=year_level or None,
        difficulty=difficulty,
        questions_json=json.dumps({
            "questions": questions,
            "sources": sources,
            "characters": len(combined),
            "generator": generator,
            "model": "openai-fast" if generator.startswith("ai") else "builtin",
            "ai_error": ai_error,
            "requested": count,
            "total_marks": total_marks,
        }),
        total_marks=total_marks,
    )
    db.session.add(test)
    db.session.commit()
    flash("Practice test saved. You can reopen it from Saved practice tests.", "success")
    return redirect(url_for("practice_test", test_id=test.id))


@app.route("/practice/test/<int:test_id>")
def practice_test(test_id):
    required = login_required()
    if required:
        return required

    test = PracticeTest.query.filter_by(
        id=test_id,
        user_id=current_user_id(),
    ).first_or_404()

    data = json.loads(test.questions_json)
    questions = data.get("questions", [])
    for question in questions:
        question.setdefault("marks", 1)
        question.setdefault("marking_scheme", [])
        question.setdefault("evidence", "")
    data["total_marks"] = sum(int(question.get("marks", 1)) for question in questions)

    return render_template(
        "practice_result.html",
        test=test,
        questions=questions,
        meta=data,
    )


@app.route("/practice/test/<int:test_id>/score", methods=["POST"])
def record_practice_score(test_id):
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    test = PracticeTest.query.filter_by(id=test_id, user_id=uid).first_or_404()
    data = json.loads(test.questions_json)
    total = sum(int(item.get("marks", 1)) for item in data.get("questions", []))
    if total <= 0:
        total = 1

    try:
        score = float(request.form.get("score", "0"))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(total, score))
    percentage = round((score / total) * 100, 1)
    grade = grade_for_percentage(percentage, get_user_grade_scale(uid)) or ""

    test.total_marks = total
    test.score = score
    test.percentage = percentage
    test.grade = grade
    test.completed_at = datetime.utcnow()
    db.session.commit()
    flash("Result saved: %s/%s (%s%%, %s)." % (score, total, percentage, grade or "—"), "success")
    return redirect(url_for("practice_test", test_id=test.id))


@app.route("/practice/delete/<int:test_id>", methods=["POST"])
def delete_practice_test(test_id):
    required = login_required()
    if required:
        return required

    test = PracticeTest.query.filter_by(
        id=test_id,
        user_id=current_user_id(),
    ).first_or_404()

    db.session.delete(test)
    db.session.commit()
    flash("Practice test deleted.", "success")
    return redirect(url_for("practice"))


# =========================================================
# SETTINGS
# =========================================================

@app.route("/settings")
def settings():
    required = login_required()
    if required:
        return required
    user = User.query.get(current_user_id())
    return render_template(
        "settings.html",
        user=user,
        smtp_configured=all([
            app.config.get("SMTP_SERVER"),
            app.config.get("SMTP_USERNAME"),
            app.config.get("SMTP_PASSWORD"),
            app.config.get("EMAIL_FROM"),
        ]),
        smtp_server=app.config.get("SMTP_SERVER", ""),
        smtp_port=app.config.get("SMTP_PORT", 587),
        smtp_username=app.config.get("SMTP_USERNAME", ""),
        smtp_from=app.config.get("EMAIL_FROM", ""),
        smtp_tls=app.config.get("SMTP_USE_TLS", True),
    )


@app.route("/settings/change-email", methods=["POST"])
def change_email_direct():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    user = User.query.get(uid)
    password = request.form.get("current_password", "")
    new_email = request.form.get("new_email", "").strip().lower()
    confirm_email = request.form.get("confirm_email", "").strip().lower()
    if not check_password_hash(user.password_hash, password):
        flash("Current password is not correct.", "error")
    elif not new_email or "@" not in new_email:
        flash("Enter a valid email address.", "error")
    elif new_email != confirm_email:
        flash("The two email addresses do not match.", "error")
    elif User.query.filter(db.func.lower(User.email) == new_email, User.id != uid).first():
        flash("That email is already used by another account.", "error")
    else:
        user.email = new_email
        user.email_verified = True
        log_audit(uid, "update", "email", uid, new_email)
        db.session.commit()
        flash("Email changed. No verification code needed.", "success")
    return redirect(url_for("settings"))


@app.route("/settings/profile", methods=["POST"])
def update_profile():
    required = login_required()
    if required:
        return required
    user = User.query.get(current_user_id())
    display_name = request.form.get("display_name", "").strip()[:100]
    username = request.form.get("username", "").strip()[:100]

    if len(username) < 3:
        flash("Username must be at least 3 characters.", "error")
        return redirect(url_for("settings"))

    existing = User.query.filter(
        db.func.lower(User.username) == username.lower(),
        User.id != user.id,
    ).first()
    if existing:
        flash("That username is already taken.", "error")
        return redirect(url_for("settings"))

    user.username = username
    user.display_name = display_name or None
    db.session.commit()
    session["username"] = username
    flash("Profile updated.", "success")
    return redirect(url_for("settings"))


@app.route("/settings/password", methods=["POST"])
def change_password():
    required = login_required()
    if required:
        return required
    user = User.query.get(current_user_id())
    current = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    if not check_password_hash(user.password_hash, current):
        flash("Your current password is incorrect.", "error")
    elif len(new_password) < 8:
        flash("New password must be at least 8 characters.", "error")
    elif new_password != confirm:
        flash("New passwords do not match.", "error")
    else:
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("Password changed.", "success")
    return redirect(url_for("settings"))


@app.route("/settings/email", methods=["POST"])
def update_email_settings():
    required = login_required()
    if required:
        return required

    server = request.form.get("server", "").strip()
    try:
        port = int(request.form.get("port", "587"))
    except (TypeError, ValueError):
        port = 587
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    from_email = request.form.get("from_email", "").strip()
    use_tls = request.form.get("use_tls") == "on"

    existing = {}
    try:
        with open(SMTP_SETTINGS_FILE, "r", encoding="utf-8") as settings_file:
            existing = json.load(settings_file)
    except (OSError, ValueError):
        pass

    if not password:
        password = existing.get("password", "")

    save_smtp_settings({
        "server": server,
        "port": port,
        "username": username,
        "password": password,
        "from_email": from_email,
        "use_tls": use_tls,
    })
    flash("Email settings saved.", "success")
    return redirect(url_for("settings"))


@app.route("/settings/test-email", methods=["POST"])
def send_test_email():
    required = login_required()
    if required:
        return required
    user = User.query.get(current_user_id())
    try:
        sent = send_email(
            user.email,
            "SmartStride test email",
            "This is a test email from SmartStride. Your SMTP settings are working.",
        )
    except Exception as exc:
        flash("Test email failed: %s" % exc, "error")
    else:
        if sent:
            flash("Test email sent to %s." % user.email, "success")
        else:
            flash("Could not send the email. Check the SMTP details in Settings.", "error")
    return redirect(url_for("settings"))


@app.route("/settings/email/request", methods=["POST"])
def request_email_change():
    required = login_required()
    if required:
        return required
    flash("Use Change email: enter your current password and the new email twice. No verification code is sent.", "info")
    return redirect(url_for("settings"))


@app.route("/settings/email/verify", methods=["GET", "POST"])
def verify_email_change():
    required = login_required()
    if required:
        return required
    flash("Email confirmation codes are turned off. Change your email from Settings with your current password.", "info")
    return redirect(url_for("settings"))


# =========================================================
# STUDYOS 0.5.0 — PLANNING, PROGRESS, DATA AND SHARING
# =========================================================

class UserPreference(db.Model):
    __tablename__ = "user_preference"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    appearance_json = db.Column(db.Text, nullable=True)
    language = db.Column(db.String(5), nullable=False, default="en")
    celebrations = db.Column(db.Boolean, nullable=False, default=True)
    dashboard_json = db.Column(db.Text, nullable=True)
    custom_wallpaper = db.Column(db.String(300), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class XpEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    points = db.Column(db.Integer, nullable=False, default=0)
    reason = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FocusSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject = db.Column(db.String(100), nullable=True)
    minutes = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    note = db.Column(db.String(300), nullable=True)


class DailyCheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    check_date = db.Column(db.String(10), nullable=False)
    mood = db.Column(db.Integer, nullable=True)
    energy = db.Column(db.Integer, nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "check_date", name="uq_checkin_user_date"),)


class QuestDone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    quest_date = db.Column(db.String(10), nullable=False)
    quest_key = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "quest_date", "quest_key", name="uq_quest_user_date_key"),)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(40), nullable=False)
    entity = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    detail = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TrashItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    entity = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(300), nullable=True)
    snapshot = db.Column(db.Text, nullable=False)
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow)


class EntityVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    entity = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(300), nullable=True)
    snapshot = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ShareLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token = db.Column(db.String(80), nullable=False, unique=True)
    kind = db.Column(db.String(30), nullable=False, default="planner")
    label = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)


class StudyGroupList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token = db.Column(db.String(80), nullable=False, unique=True)
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StudyGroupItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey("study_group_list.id"), nullable=False)
    text = db.Column(db.String(300), nullable=False)
    done = db.Column(db.Boolean, nullable=False, default=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =========================================================
# SMALL HELPERS
# =========================================================

LEVEL_STEPS = [0, 80, 200, 360, 560, 820, 1150, 1550, 2050, 2700, 3500, 4500, 5700, 7100, 8800,
               10800, 13100, 15700, 18600, 21800, 25300, 29100, 33200, 37600, 42300,
               47300, 52600, 58200, 64100, 70300]
LEVEL_TITLES = [
    "Spark", "Momentum", "Focus Keeper", "Task Slayer", "Quiz Whiz",
    "Grade Glider", "Study Strategist", "Deadline Dominator", "Master of Focus",
    "Study Legend", "Time Bender", "Unstoppable", "Brainiac", "Valedictorian", "Mythic",
    "Trailblazer", "Scholar", "Achiever", "Innovator", "Luminary",
    "Pathfinder", "Overachiever", "Sage", "Virtuoso", "Legendary",
    "Transcendent", "Cosmic", "Infinite", "Ascendant", "Eternal"
]
LEVEL_BADGES = ["🌱","🚀","🎯","⚔️","🧠","📈","🗺️","🏆","🔥","👑","⏳","⚡","💡","🎓","🌟"]
LEVEL_PRIZES = [
    "", "", "", "+5% XP boost", "", "", "", "+10% XP boost",
    "", "", "", "+15% XP boost", "", "", "", "+20% XP boost",
    "", "", "", "+25% XP boost", "", "", "", "+30% XP boost",
    "", "", "", "+35% XP boost", "", ""
]


def user_pref(uid):
    pref = UserPreference.query.filter_by(user_id=uid).first()
    if not pref:
        pref = UserPreference(user_id=uid, language="en", celebrations=True)
        db.session.add(pref)
        db.session.commit()
    return pref


def xp_total(uid):
    total = db.session.query(db.func.coalesce(db.func.sum(XpEvent.points), 0)).filter(XpEvent.user_id == uid).scalar()
    return int(total or 0)


def level_info(uid):
    total = xp_total(uid)
    level = 1
    for index, threshold in enumerate(LEVEL_STEPS):
        if total >= threshold:
            level = index + 1
    current = LEVEL_STEPS[level - 1]
    nxt = LEVEL_STEPS[level] if level < len(LEVEL_STEPS) else current
    if nxt <= current:
        percent = 100
    else:
        percent = int(round((total - current) * 100.0 / (nxt - current)))
    title = LEVEL_TITLES[min(level - 1, len(LEVEL_TITLES) - 1)]
    next_title = LEVEL_TITLES[min(level, len(LEVEL_TITLES) - 1)]
    prize = LEVEL_PRIZES[min(level - 1, len(LEVEL_PRIZES) - 1)]
    next_prize = LEVEL_PRIZES[min(level, len(LEVEL_PRIZES) - 1)]
    badge = LEVEL_BADGES[min(level - 1, len(LEVEL_BADGES) - 1)]
    return {"xp": total, "level": level, "current": current, "next": nxt,
            "percent": max(0, min(100, percent)), "title": title, "next_title": next_title,
            "prize": prize, "next_prize": next_prize, "badge": badge}


def award_xp(uid, points, reason, commit=True):
    if points:
        level = level_info(uid)["level"]
        multiplier = 1.0
        if level >= 28:
            multiplier = 1.35
        elif level >= 24:
            multiplier = 1.30
        elif level >= 20:
            multiplier = 1.25
        elif level >= 16:
            multiplier = 1.20
        elif level >= 12:
            multiplier = 1.15
        elif level >= 8:
            multiplier = 1.10
        elif level >= 4:
            multiplier = 1.05
        points = int(round(int(points) * multiplier))
        db.session.add(XpEvent(user_id=uid, points=points, reason=reason[:200]))
        if commit:
            db.session.commit()


def log_audit(uid, action, entity, entity_id=None, detail=""):
    db.session.add(AuditLog(user_id=uid, action=action[:40], entity=entity[:40], entity_id=entity_id, detail=(detail or "")[:500]))


def model_snapshot(obj):
    data = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column.name] = value
    return data


def save_version(uid, entity, obj):
    try:
        snapshot = json.dumps(model_snapshot(obj), ensure_ascii=False)
        db.session.add(EntityVersion(user_id=uid, entity=entity, entity_id=obj.id,
                                     title=getattr(obj, "title", getattr(obj, "name", "")) or "",
                                     snapshot=snapshot))
    except Exception:
        pass


def move_to_trash(uid, entity, obj, title):
    snapshot = json.dumps(model_snapshot(obj), ensure_ascii=False)
    db.session.add(TrashItem(user_id=uid, entity=entity, entity_id=obj.id,
                             title=(title or "")[:300], snapshot=snapshot))
    log_audit(uid, "delete", entity, obj.id, title)


def restore_snapshot(obj, snapshot):
    data = json.loads(snapshot)
    for column in obj.__table__.columns:
        if column.name in ("id",):
            continue
        if column.name in data:
            value = data[column.name]
            try:
                if isinstance(getattr(obj, column.name), datetime) and isinstance(value, str):
                    value = datetime.fromisoformat(value)
            except Exception:
                pass
            setattr(obj, column.name, value)


ACCREDIT = {
    "slate": "#475569", "blue": "#2563eb", "green": "#16a34a", "purple": "#7c3aed",
    "amber": "#b45309", "red": "#dc2626", "pink": "#db2777", "teal": "#0d9488",
    "indigo": "#4f46e5", "orange": "#ea580c", "cyan": "#0891b2", "rose": "#e11d48",
    "lime": "#65a30d", "brown": "#92400e",
}


def subject_meta(uid):
    return {s.name: {"colour": s.colour or "#4f5fd5", "icon": s.icon or "📘"} for s in Subject.query.filter_by(user_id=uid, archived=False).all()}


def public_base_url():
    explicit = os.environ.get("PUBLIC_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    host = request.host_url.rstrip("/")
    if host.startswith("http://127.") or host.startswith("http://localhost"):
        return "https://reimagined-robot-vpqpq6vwx9qr2xw75-5000.app.github.dev"
    return host


@app.context_processor
def inject_studyos_context():
    ctx = {"t": translate, "lang": current_lang(), "xp_info": None, "subject_meta_map": {},
           "public_base_url": public_base_url()}
    if logged_in():
        uid = current_user_id()
        try:
            ctx["xp_info"] = level_info(uid)
            ctx["subject_meta_map"] = subject_meta(uid)
            pref = UserPreference.query.filter_by(user_id=uid).first()
            ctx["user_language"] = pref.language if pref else session.get("lang", "en")
            ctx["user_wallpaper"] = getattr(pref, "custom_wallpaper", None)
            ctx["celebrations_on"] = bool(pref.celebrations) if pref else True
            try:
                ctx["user_appearance"] = json.loads(pref.appearance_json) if pref and pref.appearance_json else {}
            except Exception:
                ctx["user_appearance"] = {}
        except Exception:
            pass
    return ctx


TRANSLATIONS = {
    "zh": {
        "Home": "主页", "Today": "今天", "Subjects": "科目", "Homework": "作业", "To-Do": "待办",
        "Assessments": "考试与作业", "Grades": "成绩", "Calendar": "日历", "Pomodoro": "番茄钟",
        "Resources": "资料", "Settings": "设置", "Focus": "专注模式", "Inbox": "收集箱",
        "Recap": "每周回顾", "Progress": "进度", "Save": "保存", "Cancel": "取消",
        "Add": "添加", "Delete": "删除", "Archive": "归档", "Restore": "恢复", "Search": "搜索",
        "WORKSPACE": "工作区", "STUDY": "学习", "TOOLS": "工具", "Log out": "退出登录",
        "Overall average": "总平均分", "Homework due": "待交作业", "Upcoming assessments": "即将到来的考试",
        "Daily quests": "每日任务", "Daily check-in": "每日签到", "Study heatmap": "学习热力图",
        "Weekly recap": "每周回顾", "Next 3 tasks": "接下来 3 项任务", "Pinned": "已置顶",
        "Print weekly planner": "打印每周计划", "Print assessment timetable": "打印考试时间表",
        "Export CSV": "导出 CSV", "Import CSV": "导入 CSV", "Trash": "回收站", "Audit log": "操作记录",
        "Share links": "分享链接", "Archive": "归档", "Dark mode": "深色模式", "Language": "语言",
        "Your uploads": "我的上传", "No active To-Dos right now.": "目前没有待办事项。",
        "You're all caught up": "都完成了", "Add To-Do": "添加待办", "Open List": "打开列表",
        "View history": "查看历史", "Homework remaining": "剩余作业", "upcoming assessments": "场即将到来",
    }
}


def current_lang():
    if session.get("lang") in ("en", "zh"):
        return session.get("lang")
    if logged_in():
        pref = UserPreference.query.filter_by(user_id=current_user_id()).first()
        if pref and pref.language in ("en", "zh"):
            return pref.language
    return "en"


def translate(text):
    lang = current_lang()
    if lang == "zh":
        return TRANSLATIONS["zh"].get(text, text)
    return text


@app.route("/settings/language", methods=["POST"])
def save_language():
    required = login_required()
    if required:
        return required
    value = request.form.get("language", "en")
    if value not in ("en", "zh"):
        value = "en"
    session["lang"] = value
    pref = user_pref(current_user_id())
    pref.language = value
    db.session.commit()
    flash("Language saved." if value == "en" else "语言已保存。", "success")
    return redirect(url_for("settings"))


# =========================================================
# APPEARANCE WALLPAPER UPLOAD
# =========================================================

WALLPAPER_FOLDER = os.path.join(UPLOAD_FOLDER, "wallpapers")
os.makedirs(WALLPAPER_FOLDER, exist_ok=True)


@app.route("/settings/appearance", methods=["POST"])
def save_appearance():
    required = login_required()
    if required:
        return jsonify({"ok": False}), 401
    data = request.get_json(silent=True) or {}
    allowed = ("font", "accent", "theme", "wallpaper", "frame")
    clean = {key: str(data.get(key, ""))[:40] for key in allowed if data.get(key)}
    pref = user_pref(current_user_id())
    pref.appearance_json = json.dumps(clean)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/settings/celebrations", methods=["POST"])
def save_celebrations():
    required = login_required()
    if required:
        return required
    pref = user_pref(current_user_id())
    pref.celebrations = request.form.get("celebrations") == "on"
    db.session.commit()
    flash("Celebration setting saved.", "success")
    return redirect(url_for("settings"))


@app.route("/appearance/wallpaper", methods=["POST"])
def upload_wallpaper():
    required = login_required()
    if required:
        return required
    upload = request.files.get("wallpaper")
    if not upload or not upload.filename:
        flash("Choose an image first.", "error")
        return redirect(url_for("settings"))
    ext = upload_extension(upload.filename)
    if ext.lstrip(".") not in ("png", "jpg", "jpeg", "webp", "gif"):
        flash("Use a PNG, JPG, WEBP or GIF image.", "error")
        return redirect(url_for("settings"))
    uid = current_user_id()
    filename = "wallpaper_%s_%s%s" % (uid, secrets.token_hex(8), ext)
    upload.save(os.path.join(WALLPAPER_FOLDER, filename))
    pref = user_pref(uid)
    old = pref.custom_wallpaper
    pref.custom_wallpaper = filename
    db.session.commit()
    if old and old != filename:
        try:
            os.remove(os.path.join(WALLPAPER_FOLDER, old))
        except OSError:
            pass
    log_audit(uid, "upload", "wallpaper", None, filename)
    flash("Wallpaper uploaded and applied.", "success")
    return redirect(url_for("settings", uploaded=1))


@app.route("/appearance/wallpaper/remove", methods=["POST"])
def remove_wallpaper():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    pref = user_pref(uid)
    old = pref.custom_wallpaper
    pref.custom_wallpaper = None
    db.session.commit()
    if old:
        try:
            os.remove(os.path.join(WALLPAPER_FOLDER, old))
        except OSError:
            pass
    flash("Uploaded wallpaper removed.", "success")
    return redirect(url_for("settings"))


def custom_wallpaper_url():
    if not logged_in():
        return None
    pref = UserPreference.query.filter_by(user_id=current_user_id()).first()
    if pref and pref.custom_wallpaper:
        return url_for("wallpaper_file", filename=pref.custom_wallpaper)
    return None


@app.route("/wallpaper/<path:filename>")
def wallpaper_file(filename):
    required = login_required()
    if required:
        return required
    pref = UserPreference.query.filter_by(user_id=current_user_id()).first()
    if not pref or pref.custom_wallpaper != filename:
        abort(404)
    return send_from_directory(WALLPAPER_FOLDER, filename)


@app.route("/pin-task/<int:task_id>", methods=["POST"])
def pin_task(task_id):
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    task = Task.query.filter_by(id=task_id, user_id=uid).first_or_404()
    task.pinned = not bool(task.pinned)
    log_audit(uid, "pin" if task.pinned else "unpin", "task", task.id, task.title)
    db.session.commit()
    flash("Pinned to your dashboard." if task.pinned else "Unpinned.", "success")
    return redirect(request.referrer or url_for("tasks"))


# =========================================================
# XP / QUEST / STREAK HELPERS
# =========================================================

def completed_today(uid, day=None):
    day = day or app_today()
    start, end = local_day_bounds_utc(day)
    tasks = Task.query.filter(Task.user_id == uid, Task.completed.is_(True),
                              Task.completed_at >= start, Task.completed_at < end).count()
    assessments = Assessment.query.filter(Assessment.user_id == uid, Assessment.completed.is_(True),
                                          Assessment.completed_at >= start, Assessment.completed_at < end).count()
    todos = Todo.query.filter(Todo.user_id == uid, Todo.completed.is_(True),
                              Todo.completed_at >= start, Todo.completed_at < end).count()
    return tasks + assessments + todos


def pomodoro_count_on(uid, day):
    start, end = local_day_bounds_utc(day)
    return PanoramaSession.query.filter(
        PanoramaSession.user_id == uid,
        PanoramaSession.completed_at >= start,
        PanoramaSession.completed_at < end,
    ).count()


def pomodoro_minutes_on(uid, day):
    start, end = local_day_bounds_utc(day)
    sessions = PanoramaSession.query.filter(
        PanoramaSession.user_id == uid,
        PanoramaSession.completed_at >= start,
        PanoramaSession.completed_at < end,
    ).all()
    return sum(max(1, s.study_length or 25) * max(1, s.cycles or 1) for s in sessions)


def get_daily_quests(uid, day=None):
    day = day or app_today()
    key = day.isoformat()
    done_keys = {row.quest_key for row in QuestDone.query.filter_by(user_id=uid, quest_date=key).all()}
    tasks_done = completed_today(uid, day)
    pomodoros = pomodoro_count_on(uid, day)
    has_checkin = DailyCheckIn.query.filter_by(user_id=uid, check_date=key).first() is not None
    quests = [
        {"key": "homework", "label": "Finish one piece of homework", "progress": min(tasks_done, 1), "target": 1, "unit": "task", "done": tasks_done >= 1},
        {"key": "pomodoro", "label": "Finish one Pomodoro session", "progress": min(pomodoros, 1), "target": 1, "unit": "session", "done": pomodoros >= 1},
        {"key": "checkin", "label": "Do your daily check-in", "progress": 1 if has_checkin else 0, "target": 1, "unit": "", "done": has_checkin},
    ]
    for quest in quests:
        quest["claimed"] = quest["key"] in done_keys
    return {"date": key, "quests": quests, "done_count": sum(1 for q in quests if q["done"])}


@app.route("/quests/claim", methods=["POST"])
def claim_quest():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    key = request.form.get("key", "")
    day = app_today()
    info = get_daily_quests(uid, day)
    if key == "bonus":
        claimed = QuestDone.query.filter_by(user_id=uid, quest_date=day.isoformat(), quest_key="bonus").first()
        if info["done_count"] < 3:
            flash("Finish all three daily quests first.", "error")
        elif claimed:
            flash("Daily bonus already claimed.", "error")
        else:
            db.session.add(QuestDone(user_id=uid, quest_date=day.isoformat(), quest_key="bonus"))
            award_xp(uid, 20, "Daily bonus", commit=False)
            db.session.commit()
            flash("Daily bonus: +20 XP", "success")
        return redirect(request.referrer or url_for("today_page"))
    quest = next((q for q in info["quests"] if q["key"] == key), None)
    if not quest or not quest["done"]:
        flash("That quest is not finished yet.", "error")
        return redirect(request.referrer or url_for("today_page"))
    if not quest["claimed"]:
        db.session.add(QuestDone(user_id=uid, quest_date=day.isoformat(), quest_key=key))
        award_xp(uid, 10, "Daily quest: " + key, commit=False)
        db.session.commit()
        flash("Quest complete: +10 XP", "success")
    return redirect(request.referrer or url_for("today_page"))


def check_streak(uid):
    streak = 0
    day = app_today()
    while True:
        has = DailyCheckIn.query.filter_by(user_id=uid, check_date=day.isoformat()).first()
        if not has:
            if day == app_today():
                day -= timedelta(days=1)
                continue
            break
        streak += 1
        day -= timedelta(days=1)
        if streak > 365:
            break
    return streak


# =========================================================
# TODAY DASHBOARD
# =========================================================

def assessment_next_action(assessment):
    if assessment.completed:
        return "Finished — review your feedback."
    due = parse_homework_date(assessment.due_date)
    if not due:
        return "Add a due date so SmartStride can plan backwards."
    days = (due - app_today()).days
    if days < 0:
        return "Overdue — do the smallest next step now, then ask your teacher for help."
    if days == 0:
        return "Due today — check the task sheet and finish the final section."
    if days <= 2:
        return "Do one timed practice run tonight, then fix your mistakes."
    if days <= 7:
        return "Make a one-page summary and do 20 minutes of practice."
    if days <= 14:
        return "Split the work into chunks and start the first chunk this week."
    return "Read the task sheet and write a simple plan."




@app.route("/check-in", methods=["POST"])
def save_check_in():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    today = app_today().isoformat()
    mood = request.form.get("mood", "3")
    energy = request.form.get("energy", "3")
    note = request.form.get("note", "").strip()
    try:
        mood_value = max(1, min(5, int(mood)))
        energy_value = max(1, min(5, int(energy)))
    except ValueError:
        mood_value = energy_value = 3
    row = DailyCheckIn.query.filter_by(user_id=uid, check_date=today).first()
    new = row is None
    if row is None:
        row = DailyCheckIn(user_id=uid, check_date=today)
        db.session.add(row)
    row.mood = mood_value
    row.energy = energy_value
    row.note = note[:2000]
    if new:
        award_xp(uid, 5, "Daily check-in", commit=False)
    log_audit(uid, "update" if not new else "create", "checkin", row.id, today)
    db.session.commit()
    flash("Check-in saved. +5 XP" if new else "Check-in updated.", "success")
    return redirect(request.referrer or url_for("today_page"))


# =========================================================
# SMART INBOX
# =========================================================

@app.route("/inbox")
def inbox():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    unsorted_tasks = [t for t in Task.query.filter_by(user_id=uid, completed=False, archived=False).all()
                      if not getattr(t, "archived", False) and (not t.due_date or not t.subject)]
    unsorted_assessments = [a for a in Assessment.query.filter_by(user_id=uid, completed=False, archived=False).all()
                            if not getattr(a, "archived", False) and not a.due_date]
    unsorted_todos = [t for t in Todo.query.filter_by(user_id=uid, completed=False, archived=False).all()
                      if not getattr(t, "archived", False) and not t.date]
    quick_added = [t for t in unsorted_tasks if not t.due_date and not t.subject]
    return render_template("inbox.html", tasks=unsorted_tasks, assessments=unsorted_assessments,
                           todos=unsorted_todos, quick_added=quick_added,
                           subjects=Subject.query.filter_by(user_id=uid, archived=False).order_by(Subject.name.asc()).all())


@app.route("/inbox/update", methods=["POST"])
def inbox_update():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    entity = request.form.get("entity")
    item_id = request.form.get("id", type=int)
    due = normalise_homework_date(request.form.get("due_date", ""))
    subject = request.form.get("subject", "").strip()
    title = request.form.get("title", "").strip()

    if entity == "task":
        obj = Task.query.filter_by(id=item_id, user_id=uid).first()
        if obj:
            if due:
                obj.due_date = due
            if subject:
                obj.subject = subject
            if title:
                obj.title = title[:200]
            log_audit(uid, "update", "task", obj.id, "inbox")
            db.session.commit()
    elif entity == "assessment":
        obj = Assessment.query.filter_by(id=item_id, user_id=uid).first()
        if obj:
            if due:
                obj.due_date = due
            if subject:
                obj.subject = subject
            if title:
                obj.title = title[:200]
            log_audit(uid, "update", "assessment", obj.id, "inbox")
            db.session.commit()
    elif entity == "todo":
        obj = Todo.query.filter_by(id=item_id, user_id=uid).first()
        if obj:
            if due:
                obj.date = due
            if title:
                obj.title = title[:200]
            log_audit(uid, "update", "todo", obj.id, "inbox")
            db.session.commit()
    flash("Item sorted.", "success")
    return redirect(url_for("inbox"))


# =========================================================
# GRADE GOAL CALCULATOR
# =========================================================

def grade_goal_average(uid):
    """Return the same simple average shown on the Grades page, plus how many results count."""
    assessments = Assessment.query.filter_by(user_id=uid).filter(Assessment.archived.is_(False)).all()
    values = []
    for item in assessments:
        percentage = assessment_percentage(item)
        if percentage is None:
            continue
        if (item.grade or "").strip().upper() == "N/A":
            continue
        values.append(percentage)
    if not values:
        return None, 0
    return sum(values) / len(values), len(values)


def _grade_goal_result(current, target, weight):
    if weight <= 0 or weight > 100:
        return {"error": "The exam weight must be between 1 and 100 percent."}
    current = max(0.0, min(100.0, current))
    target = max(0.0, min(100.0, target))
    weight_fraction = weight / 100.0
    needed = (target - current * (1 - weight_fraction)) / weight_fraction
    possible = needed <= 100
    return {"needed": max(0.0, min(999.0, needed)), "possible": possible,
            "current": current, "target": target, "weight": weight}


@app.route("/levels")
def levels_page():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    recent = XpEvent.query.filter_by(user_id=uid).order_by(XpEvent.created_at.desc()).limit(12).all()
    ladder = []
    for index, threshold in enumerate(LEVEL_STEPS):
        ladder.append({
            "level": index + 1,
            "xp": threshold,
            "title": LEVEL_TITLES[min(index, len(LEVEL_TITLES) - 1)],
            "badge": LEVEL_BADGES[min(index, len(LEVEL_BADGES) - 1)],
            "prize": LEVEL_PRIZES[min(index, len(LEVEL_PRIZES) - 1)],
            "reached": xp_total(uid) >= threshold,
        })
    return render_template("levels.html", xp=level_info(uid), recent=recent, ladder=ladder)


@app.route("/grade-goal", methods=["GET", "POST"])
def grade_goal():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    current_average, graded_count = grade_goal_average(uid)
    current_default = round(current_average, 1) if current_average is not None else 75
    result = None
    if request.method == "POST":
        try:
            current = float(request.form.get("current", "0"))
            target = float(request.form.get("target", "0"))
            weight = float(request.form.get("weight", "50"))
        except ValueError:
            flash("Enter numbers for current mark, target and exam weight.", "error")
            return redirect(url_for("grade_goal"))
        result = _grade_goal_result(current, target, weight)
        if result and not result.get("error"):
            w = result["weight"] / 100.0
            result["max_overall"] = result["current"] * (1 - w) + 100 * w
            result["final_overall"] = result["current"] * (1 - w) + result["needed"] * w
            result["needed_grade"] = grade_for_percentage(min(100, result["needed"]), get_user_grade_scale(uid))
            result["target_grade"] = grade_for_percentage(result["target"], get_user_grade_scale(uid))
        log_audit(uid, "calculate", "grade_goal", None, "target %.1f weight %.1f" % (target, weight))
        db.session.commit()
    return render_template("grade_goal.html", result=result, scale=get_user_grade_scale(uid),
                           subjects=Subject.query.filter_by(user_id=uid, archived=False).order_by(Subject.name.asc()).all(),
                           current_average=current_average, graded_count=graded_count,
                           current_default=current_default)


# =========================================================
# RECAP + HEATMAP
# =========================================================

def activity_counts(uid, start_day, end_day):
    counts = {}
    day = start_day
    while day <= end_day:
        counts[day.isoformat()] = 0
        day += timedelta(days=1)

    def add(dt, amount=1):
        if not dt:
            return
        key = local_date_of(dt).isoformat()
        if key in counts:
            counts[key] += amount

    for obj in Task.query.filter(Task.user_id == uid, Task.completed_at.isnot(None)).all():
        add(obj.completed_at)
    for obj in Assessment.query.filter(Assessment.user_id == uid, Assessment.completed_at.isnot(None)).all():
        add(obj.completed_at)
    for obj in Todo.query.filter(Todo.user_id == uid, Todo.completed_at.isnot(None)).all():
        add(obj.completed_at)
    for obj in PanoramaSession.query.filter(PanoramaSession.user_id == uid,
                                             PanoramaSession.completed_at.isnot(None)).all():
        add(obj.completed_at)
    return counts


@app.route("/recap")
def recap():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    today = app_today()
    monday = today - timedelta(days=today.weekday())
    week_start, week_end = local_day_bounds_utc(monday)
    week_end = week_start + timedelta(days=7)

    week_tasks = Task.query.filter(Task.user_id == uid, Task.completed_at >= week_start, Task.completed_at < week_end).all()
    week_assessments = Assessment.query.filter(Assessment.user_id == uid, Assessment.completed_at >= week_start,
                                                Assessment.completed_at < week_end).all()
    week_todos = Todo.query.filter(Todo.user_id == uid, Todo.completed_at >= week_start, Todo.completed_at < week_end).all()
    week_pomodoros = PanoramaSession.query.filter(PanoramaSession.user_id == uid,
                                                   PanoramaSession.completed_at >= week_start,
                                                   PanoramaSession.completed_at < week_end).all()
    week_xp = db.session.query(db.func.coalesce(db.func.sum(XpEvent.points), 0)).filter(
        XpEvent.user_id == uid, XpEvent.created_at >= week_start, XpEvent.created_at < week_end).scalar() or 0

    by_subject = {}
    for obj in week_tasks + week_assessments:
        name = obj.subject or "General"
        by_subject[name] = by_subject.get(name, 0) + 1
    best_subject = max(by_subject.items(), key=lambda pair: pair[1])[0] if by_subject else None

    next_week = []
    for task in Task.query.filter_by(user_id=uid, completed=False, archived=False).all():
        due = parse_homework_date(task.due_date)
        if due and monday + timedelta(days=7) <= due < monday + timedelta(days=14):
            next_week.append(("Homework", task.title, due))
    for assessment in Assessment.query.filter_by(user_id=uid, completed=False, archived=False).all():
        due = parse_homework_date(assessment.due_date)
        if due and monday + timedelta(days=7) <= due < monday + timedelta(days=14):
            next_week.append(("Assessment", assessment.title, due))
    next_week.sort(key=lambda row: row[2])

    heat_start = today - timedelta(days=55)
    counts = activity_counts(uid, heat_start, today)
    weeks = []
    cursor = heat_start - timedelta(days=heat_start.weekday())
    while cursor <= today:
        week = []
        for offset in range(7):
            day = cursor + timedelta(days=offset)
            week.append({"date": day, "count": counts.get(day.isoformat(), 0) if day <= today else None})
        weeks.append(week)
        cursor += timedelta(days=7)
    visible_days = [day for week in weeks for day in week if day["date"] <= today]
    active_days = sum(1 for day in visible_days if (day["count"] or 0) > 0)
    best_day = max(visible_days, key=lambda day: day["count"] or 0) if visible_days else None
    total_days = len(visible_days)

    week_counts = activity_counts(uid, monday, today)
    week_days = []
    for offset in range(7):
        day_value = monday + timedelta(days=offset)
        week_days.append({
            "date": day_value,
            "label": day_value.strftime("%a"),
            "short": day_value.strftime("%d/%m"),
            "count": week_counts.get(day_value.isoformat(), 0) if day_value <= today else None,
        })
    week_total = sum((day["count"] or 0) for day in week_days)
    week_best = max(week_days, key=lambda day: day["count"] or 0)

    return render_template("recap.html", monday=monday, today=today,
                           week_tasks=week_tasks, week_assessments=week_assessments,
                           week_todos=week_todos, week_pomodoros=week_pomodoros,
                           week_minutes=sum(max(1, p.study_length or 25) * max(1, p.cycles or 1) for p in week_pomodoros),
                           week_xp=int(week_xp), best_subject=best_subject,
                           by_subject=sorted(by_subject.items(), key=lambda pair: -pair[1]),
                           next_week=next_week, weeks=weeks, active_days=active_days,
                           total_days=total_days, best_day=best_day, week_days=week_days,
                           week_total=week_total, week_best=week_best, xp=level_info(uid),
                           streak=check_streak(uid), quests=get_daily_quests(uid, today))


# =========================================================
# ARCHIVE, TRASH, VERSIONS, AUDIT
# =========================================================

def _entity_model(entity):
    return {"task": Task, "assessment": Assessment, "todo": Todo, "subject": Subject}.get(entity)


@app.route("/archive/<entity>/<int:item_id>", methods=["POST"])
def archive_item(entity, item_id):
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    model = _entity_model(entity)
    obj = model.query.filter_by(id=item_id, user_id=uid).first() if model else None
    if not obj:
        abort(404)
    obj.archived = True
    log_audit(uid, "archive", entity, item_id, getattr(obj, "title", getattr(obj, "name", "")))
    db.session.commit()
    flash("Moved to archive. You can restore it any time.", "success")
    return redirect(request.referrer or url_for("home"))


@app.route("/unarchive/<entity>/<int:item_id>", methods=["POST"])
def unarchive_item(entity, item_id):
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    model = _entity_model(entity)
    obj = model.query.filter_by(id=item_id, user_id=uid).first() if model else None
    if not obj:
        abort(404)
    obj.archived = False
    log_audit(uid, "unarchive", entity, item_id, getattr(obj, "title", getattr(obj, "name", "")))
    db.session.commit()
    flash("Restored from archive.", "success")
    return redirect(request.referrer or url_for("archive_page"))


@app.route("/archive")
def archive_page():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    tasks = Task.query.filter_by(user_id=uid, archived=True).order_by(Task.completed_at.desc()).all()
    assessments = Assessment.query.filter_by(user_id=uid, archived=True).order_by(Assessment.completed_at.desc()).all()
    todos = Todo.query.filter_by(user_id=uid, archived=True).order_by(Todo.completed_at.desc()).all()
    subjects = Subject.query.filter_by(user_id=uid, archived=True).order_by(Subject.name.asc()).all()
    return render_template("archive.html", tasks=tasks, assessments=assessments, todos=todos, subjects=subjects)


@app.route("/trash")
def trash_page():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    items = TrashItem.query.filter_by(user_id=uid).order_by(TrashItem.deleted_at.desc()).all()
    return render_template("trash.html", items=items)


@app.route("/trash/restore/<int:item_id>", methods=["POST"])
def trash_restore(item_id):
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    item = TrashItem.query.filter_by(id=item_id, user_id=uid).first()
    if not item:
        abort(404)
    model = _entity_model(item.entity)
    restored = False
    if model:
        obj = model.query.filter_by(id=item.entity_id, user_id=uid).first()
        if obj:
            restore_snapshot(obj, item.snapshot)
            obj.archived = False
            obj.completed = False
            restored = True
    if not restored:
        flash("That item can no longer be restored (it was removed permanently).", "error")
        return redirect(url_for("trash_page"))
    log_audit(uid, "restore", item.entity, item.entity_id, item.title)
    db.session.delete(item)
    db.session.commit()
    flash("Restored “%s”." % (item.title or "item"), "success")
    return redirect(url_for("trash_page"))


@app.route("/trash/purge/<int:item_id>", methods=["POST"])
def trash_purge(item_id):
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    item = TrashItem.query.filter_by(id=item_id, user_id=uid).first()
    if not item:
        abort(404)
    model = _entity_model(item.entity)
    obj = model.query.filter_by(id=item.entity_id, user_id=uid).first() if model else None
    if obj is not None:
        if item.entity == "task":
            for resource in HomeworkResource.query.filter_by(task_id=obj.id, user_id=uid).all():
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], resource.filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
                db.session.delete(resource)
            if obj.finished_file:
                finished_path = os.path.join(app.config["UPLOAD_FOLDER"], obj.finished_file)
                if os.path.exists(finished_path):
                    try:
                        os.remove(finished_path)
                    except OSError:
                        pass
        elif item.entity == "assessment":
            for uploaded_file in list(obj.uploaded_files):
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], uploaded_file.filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
                db.session.delete(uploaded_file)
        db.session.delete(obj)
    log_audit(uid, "purge", item.entity, item.entity_id, item.title)
    db.session.delete(item)
    db.session.commit()
    flash("Deleted permanently.", "success")
    return redirect(url_for("trash_page"))


@app.route("/versions/<entity>/<int:item_id>")
def versions_page(entity, item_id):
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    versions = EntityVersion.query.filter_by(user_id=uid, entity=entity, entity_id=item_id).order_by(
        EntityVersion.created_at.desc()).all()
    model = _entity_model(entity)
    obj = model.query.filter_by(id=item_id, user_id=uid).first() if model else None
    return render_template("versions.html", versions=versions, entity=entity, item=obj)


@app.route("/versions/restore/<int:version_id>", methods=["POST"])
def version_restore(version_id):
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    version = EntityVersion.query.filter_by(id=version_id, user_id=uid).first()
    if not version:
        abort(404)
    model = _entity_model(version.entity)
    obj = model.query.filter_by(id=version.entity_id, user_id=uid).first() if model else None
    if not obj:
        flash("The item no longer exists.", "error")
        return redirect(url_for("versions_page", entity=version.entity, item_id=version.entity_id))
    save_version(uid, version.entity, obj)
    restore_snapshot(obj, version.snapshot)
    log_audit(uid, "restore_version", version.entity, version.entity_id, "version %s" % version.id)
    db.session.commit()
    flash("Previous version restored.", "success")
    return redirect(url_for("versions_page", entity=version.entity, item_id=version.entity_id))


@app.route("/audit")
def audit_page():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    entries = AuditLog.query.filter_by(user_id=uid).order_by(AuditLog.created_at.desc()).limit(400).all()
    return render_template("audit.html", entries=entries)


# =========================================================
# CSV EXPORT / IMPORT
# =========================================================

import csv as csv_module


@app.route("/export/csv")
def export_csv():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    kind = request.args.get("type", "homework")
    buffer = io.StringIO()
    writer = csv_module.writer(buffer)
    if kind == "assessments":
        writer.writerow(["title", "subject", "due_date", "score", "total_score", "percentage", "weight", "grade", "completed", "feedback"])
        for row in Assessment.query.filter_by(user_id=uid).order_by(Assessment.due_date.asc()).all():
            writer.writerow([row.title, row.subject or "", row.due_date or "", row.score if row.score is not None else "",
                             row.total_score if row.total_score is not None else "",
                             assessment_percentage(row) if assessment_percentage(row) is not None else "",
                             row.weight if row.weight is not None else "", row.grade or "",
                             "yes" if row.completed else "no", (row.feedback or "").replace("\n", " ")])
        filename = "assessments.csv"
    elif kind == "todos":
        writer.writerow(["title", "date", "completed", "completed_at"])
        for row in Todo.query.filter_by(user_id=uid).order_by(Todo.date.asc()).all():
            writer.writerow([row.title, row.date or "", "yes" if row.completed else "no",
                             row.completed_at.isoformat() if row.completed_at else ""])
        filename = "todos.csv"
    elif kind == "grades":
        writer.writerow(["title", "subject", "due_date", "percentage", "grade", "weight"])
        for row in Assessment.query.filter_by(user_id=uid).all():
            pct = assessment_percentage(row)
            if pct is not None:
                writer.writerow([row.title, row.subject or "", row.due_date or "", "%.2f" % pct, row.grade or "", row.weight or 1])
        filename = "grades.csv"
    else:
        writer.writerow(["title", "subject", "assigned_date", "due_date", "completed", "completed_at", "notes"])
        for row in Task.query.filter_by(user_id=uid).order_by(Task.due_date.asc()).all():
            writer.writerow([row.title, row.subject or "", row.assigned_date or "", row.due_date or "",
                             "yes" if row.completed else "no",
                             row.completed_at.isoformat() if row.completed_at else "", (row.notes or "").replace("\n", " ")])
        filename = "homework.csv"
    log_audit(uid, "export", "csv", None, kind)
    db.session.commit()
    data = buffer.getvalue()
    return app.response_class(data, mimetype="text/csv",
                              headers={"Content-Disposition": "attachment; filename=%s" % filename})


@app.route("/import/csv/sample")
def import_csv_sample():
    required = login_required()
    if required:
        return required
    kind = request.args.get("type", "homework")
    buffer = io.StringIO()
    writer = csv_module.writer(buffer)
    if kind == "assessments":
        writer.writerow(["title", "subject", "due_date"])
        writer.writerow(["Science topic test", "Science", "2026-11-20"])
        writer.writerow(["Maths exam", "Mathematics", "2026-11-28"])
        filename = "sample-assessments.csv"
    else:
        writer.writerow(["title", "subject", "due_date"])
        writer.writerow(["Maths worksheet", "Mathematics", "2026-11-10"])
        writer.writerow(["English essay draft", "English", "2026-11-14"])
        filename = "sample-homework.csv"
    return app.response_class(buffer.getvalue(), mimetype="text/csv",
                              headers={"Content-Disposition": "attachment; filename=%s" % filename})


@app.route("/import/csv", methods=["GET", "POST"])
def import_csv():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    report = None
    if request.method == "POST":
        upload = request.files.get("csv_file")
        kind = request.form.get("type", "homework")
        if not upload or not upload.filename:
            flash("Choose a CSV file first.", "error")
            return redirect(url_for("import_csv"))
        try:
            raw = upload.read().decode("utf-8-sig", errors="replace")
            rows = list(csv_module.DictReader(io.StringIO(raw)))
        except Exception:
            flash("That file could not be read as CSV.", "error")
            return redirect(url_for("import_csv"))
        created = 0
        skipped = 0
        for row in rows:
            title = (row.get("title") or row.get("name") or "").strip()
            if not title:
                skipped += 1
                continue
            subject = (row.get("subject") or "").strip() or None
            due = normalise_homework_date(row.get("due_date") or row.get("date") or "")
            if kind == "assessments":
                db.session.add(Assessment(user_id=uid, title=title[:200], subject=subject, due_date=due,
                                          completed=False, weight=1.0))
            else:
                db.session.add(Task(user_id=uid, title=title[:200], subject=subject,
                                    assigned_date=app_today().isoformat(), due_date=due, completed=False))
            created += 1
        log_audit(uid, "import", "csv", None, "%s: %s rows" % (kind, created))
        db.session.commit()
        report = {"created": created, "skipped": skipped, "kind": kind}
        flash("Imported %s item(s). Skipped %s row(s) without a title." % (created, skipped), "success")
    return render_template("import_csv.html", report=report)


# =========================================================
# PRINT
# =========================================================

@app.route("/print/week")
def print_week():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    today = app_today()

    def parse_start(value):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    tasks = Task.query.filter_by(user_id=uid, archived=False).all()
    todos = Todo.query.filter_by(user_id=uid, archived=False).all()
    assessments = Assessment.query.filter_by(user_id=uid, archived=False).all()
    events = CalendarEvent.query.filter_by(user_id=uid).all()

    def build_week(start):
        days = [start + timedelta(days=offset) for offset in range(7)]
        columns = []
        counts = {"events": 0, "homework": 0, "assessments": 0, "todos": 0}
        for day in days:
            items = []
            for task in tasks:
                if parse_homework_date(task.due_date) == day:
                    items.append({"kind": "Homework", "category": "homework", "title": task.title,
                                  "subject": task.subject or "", "time": "",
                                  "status": "Done" if task.completed else "Open"})
            for todo in todos:
                if parse_homework_date(todo.date) == day:
                    items.append({"kind": "To-Do", "category": "todo", "title": todo.title,
                                  "subject": "", "time": "",
                                  "status": "Done" if todo.completed else "Open"})
            for assessment in assessments:
                if parse_homework_date(assessment.due_date) == day:
                    items.append({"kind": "Assessment", "category": "assessment", "title": assessment.title,
                                  "subject": assessment.subject or "", "time": "",
                                  "status": "Completed" if assessment.completed else "Due"})
            for event in events:
                if calendar_event_occurs_on(event, day):
                    items.append({"kind": event.event_type or "Event", "category": "event",
                                  "title": event.title, "subject": event.subject or "",
                                  "time": event.start_time or "", "status": ""})
            items.sort(key=lambda row: (0 if not row["time"] else 1, row["time"],
                                        row["kind"], row["title"].lower()))
            for item in items:
                key = {"event": "events", "homework": "homework",
                       "assessment": "assessments", "todo": "todos"}[item["category"]]
                counts[key] += 1
            columns.append({"day": day, "items": items})
        return columns, counts

    def useful_week(start):
        columns, _ = build_week(start)
        for column in columns:
            for item in column["items"]:
                if item["category"] in ("event", "assessment"):
                    return True
                if item["status"] == "Open":
                    return True
        return False

    requested = parse_start(request.args.get("start", ""))
    current_start = today - timedelta(days=today.weekday())
    # The weekly planner always opens on the current week. Previous/Next are
    # explicit navigation only; the calendar having no items must not move it.
    start = (requested - timedelta(days=requested.weekday())) if requested else current_start
    fallback_note = ""

    columns, counts = build_week(start)
    end = start + timedelta(days=6)
    upcoming_assessments = []
    recent_assessments = []
    for item in sorted(assessments, key=lambda a: (parse_homework_date(a.due_date) or date.max, a.title.lower())):
        due = parse_homework_date(item.due_date)
        row = {"title": item.title, "subject": item.subject or "", "due_date": item.due_date,
               "days_left": (due - today).days if due else "",
               "status": "Completed" if item.completed else ("No date" if not due else "Due")}
        (recent_assessments if item.completed or (due and due < today) else upcoming_assessments).append(row)
    if upcoming_assessments:
        assessment_rows = upcoming_assessments[:6]
    else:
        assessment_rows = list(reversed(recent_assessments))[:5]
    next_assessment = upcoming_assessments[0] if upcoming_assessments else None

    return render_template("print_week.html", columns=columns, start=start, end=end,
                           prev_start=(start - timedelta(days=7)).isoformat(),
                           next_start=(start + timedelta(days=7)).isoformat(),
                           current_start=current_start.isoformat(),
                           counts=counts, fallback_note=fallback_note,
                           assessment_rows=assessment_rows, next_assessment=next_assessment,
                           today=today, user=User.query.get(uid))


@app.route("/print/timetable")
def print_timetable():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    today = app_today()
    assessments = Assessment.query.filter_by(user_id=uid, archived=False).all()
    upcoming_rows = []
    completed_rows = []
    undated_rows = []
    for item in assessments:
        due = parse_homework_date(item.due_date)
        percentage = assessment_percentage(item)
        row = {
            "title": item.title, "subject": item.subject or "No subject", "due_date": item.due_date,
            "days_left": (due - today).days if due else None,
            "action": assessment_next_action(item),
            "percentage": round(percentage, 1) if percentage is not None else None,
            "grade": grade_for_percentage(percentage, get_user_grade_scale(uid)) if percentage is not None else "",
        }
        if item.completed:
            completed_rows.append(row)
        elif due is None:
            undated_rows.append(row)
        else:
            upcoming_rows.append(row)
    upcoming_rows.sort(key=lambda row: (row["days_left"], row["title"].lower()))
    completed_rows.sort(key=lambda row: (parse_homework_date(row["due_date"]) or date.min), reverse=True)
    undated_rows.sort(key=lambda row: row["title"].lower())

    event_rows = []
    for event in CalendarEvent.query.filter_by(user_id=uid).order_by(CalendarEvent.event_date.asc()).all():
        event_rows.append({"title": event.title, "type": event.event_type or "Event",
                           "date": parse_homework_date(event.event_date),
                           "time": event.start_time or "",
                           "subject": event.subject or "",
                           "repeat": event.recurrence_rule or "none"})
    event_rows.sort(key=lambda row: (row["date"] or date.max, row["time"]))
    return render_template("print_timetable.html", upcoming_rows=upcoming_rows,
                           completed_rows=completed_rows, undated_rows=undated_rows,
                           event_rows=event_rows, today=today,
                           next_due=upcoming_rows[0] if upcoming_rows else None,
                           user=User.query.get(uid))


@app.route("/print/calendar")
def print_calendar():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    today = app_today()

    def parse_month(value):
        try:
            year, month = [int(part) for part in (value or "").split("-")[:2]]
            if 1 <= month <= 12 and 1900 <= year <= 2200:
                return year, month
        except (TypeError, ValueError):
            pass
        return None

    requested = parse_month(request.args.get("month"))
    tasks = Task.query.filter_by(user_id=uid).all()
    todos = Todo.query.filter_by(user_id=uid).all()
    assessments = Assessment.query.filter_by(user_id=uid).all()
    events = CalendarEvent.query.filter_by(user_id=uid).all()

    # The monthly calendar always opens on the current month. Previous/Next
    # month are explicit navigation only; saved items must not move it.
    if requested:
        year, month = requested
    else:
        year, month = today.year, today.month

    days_in_month = pycalendar.monthrange(year, month)[1]
    month_items = {}
    for day in range(1, days_in_month + 1):
        target = date(year, month, day)
        items = []
        for item in tasks:
            if parse_homework_date(item.due_date) == target:
                items.append({"kind": "Homework", "title": item.title, "subject": item.subject or "",
                              "time": "", "status": "Done" if item.completed else ""})
        for item in todos:
            if parse_homework_date(item.date) == target:
                items.append({"kind": "To-Do", "title": item.title, "subject": "",
                              "time": "", "status": "Done" if item.completed else ""})
        for item in assessments:
            if parse_homework_date(item.due_date) == target:
                items.append({"kind": "Assessment", "title": item.title, "subject": item.subject or "",
                              "time": "", "status": "Done" if item.completed else "Due"})
        for event in events:
            if calendar_event_occurs_on(event, target):
                items.append({"kind": event.event_type or "Event", "title": event.title,
                              "subject": event.subject or "", "time": event.start_time or "",
                              "status": ""})
        items.sort(key=lambda row: (0 if not row["time"] else 1, row["time"], row["title"].lower()))
        month_items[target] = items

    first_day = date(year, month, 1)
    grid_start = first_day - timedelta(days=first_day.weekday())
    last_day = date(year, month, days_in_month)
    grid_end = last_day + timedelta(days=(6 - last_day.weekday()))
    weeks = []
    cursor = grid_start
    while cursor <= grid_end:
        week = []
        for offset in range(7):
            day = cursor + timedelta(days=offset)
            week.append({"date": day, "in_month": day.month == month, "entries": month_items.get(day, [])})
        weeks.append(week)
        cursor += timedelta(days=7)

    prev_month = (first_day - timedelta(days=1)).strftime("%Y-%m")
    next_month = (last_day + timedelta(days=1)).strftime("%Y-%m")
    has_any = any(items for items in month_items.values())
    has_assessments = any(str(item.due_date or "")[:7] == "%04d-%02d" % (year, month) for item in assessments)
    return render_template("print_calendar.html", weeks=weeks, year=year, month=month,
                           month_name=first_day.strftime("%B %Y"), prev_month=prev_month,
                           next_month=next_month, today=today, has_any=has_any,
                           has_assessments=has_assessments, user=User.query.get(uid))


# =========================================================
# SHARING
# =========================================================

def make_share(kind, label=None, days=30):
    uid = current_user_id()
    token = secrets.token_urlsafe(18)
    expires = datetime.utcnow() + timedelta(days=days) if days else None
    link = ShareLink(user_id=uid, token=token, kind=kind, label=label, expires_at=expires)
    db.session.add(link)
    db.session.commit()
    log_audit(uid, "share", kind, link.id, label or "")
    db.session.commit()
    return link


@app.route("/share")
def share_page():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    links = ShareLink.query.filter_by(user_id=uid).order_by(ShareLink.created_at.desc()).all()
    groups = StudyGroupList.query.filter_by(user_id=uid).order_by(StudyGroupList.created_at.desc()).all()
    return render_template("share.html", links=links, groups=groups)


@app.route("/share/create", methods=["POST"])
def share_create():
    required = login_required()
    if required:
        return required
    kind = request.form.get("kind", "planner")
    if kind not in ("planner", "summary", "pack"):
        kind = "planner"
    make_share(kind, {"planner": "Read-only planner", "summary": "Parent weekly summary", "pack": "Resource pack"}[kind], 30)
    flash("Share link created. It expires in 30 days.", "success")
    return redirect(url_for("share_page"))


@app.route("/share/revoke/<int:link_id>", methods=["POST"])
def share_revoke(link_id):
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    link = ShareLink.query.filter_by(id=link_id, user_id=uid).first()
    if link:
        db.session.delete(link)
        db.session.commit()
        flash("Share link revoked.", "success")
    return redirect(url_for("share_page"))


def _share_context(token):
    link = ShareLink.query.filter_by(token=token).first()
    if not link:
        return None, None
    if link.expires_at and link.expires_at < datetime.utcnow():
        return None, None
    user = User.query.get(link.user_id)
    return link, user


@app.route("/s/<token>")
def shared_view(token):
    link, user = _share_context(token)
    if not link or not user:
        abort(404)
    uid = user.id
    if link.kind == "summary":
        return shared_summary(link, user)
    if link.kind == "pack":
        return shared_pack(link, user)
    tasks = [t for t in Task.query.filter_by(user_id=uid, completed=False, archived=False).all() if not getattr(t, "archived", False)]
    tasks.sort(key=lambda t: (parse_homework_date(t.due_date) or date.max, t.title.lower()))
    assessments = [a for a in Assessment.query.filter_by(user_id=uid, completed=False, archived=False).all() if not getattr(a, "archived", False)]
    assessments.sort(key=lambda a: (parse_homework_date(a.due_date) or date.max, a.title.lower()))
    return render_template("share_planner.html", owner=user, tasks=tasks, assessments=assessments,
                           link=link, now=datetime.utcnow())


def shared_summary(link, user):
    uid = user.id
    today = app_today()
    monday = today - timedelta(days=today.weekday())
    start, end = local_day_bounds_utc(monday)
    end = start + timedelta(days=7)
    tasks = Task.query.filter(Task.user_id == uid, Task.completed_at >= start, Task.completed_at < end).all()
    assessments = Assessment.query.filter(Assessment.user_id == uid, Assessment.completed_at >= start,
                                           Assessment.completed_at < end).all()
    sessions = PanoramaSession.query.filter(PanoramaSession.user_id == uid,
                                             PanoramaSession.completed_at >= start,
                                             PanoramaSession.completed_at < end).all()
    next_week = []
    for task in Task.query.filter_by(user_id=uid, completed=False, archived=False).all():
        due = parse_homework_date(task.due_date)
        if due and monday + timedelta(days=7) <= due < monday + timedelta(days=14):
            next_week.append((task.title, due, "Homework"))
    for assessment in Assessment.query.filter_by(user_id=uid, completed=False, archived=False).all():
        due = parse_homework_date(assessment.due_date)
        if due and monday + timedelta(days=7) <= due < monday + timedelta(days=14):
            next_week.append((assessment.title, due, "Assessment"))
    next_week.sort(key=lambda row: row[1])

    # Grades, averages and all-time study time for parents / tutors.
    scale = get_user_grade_scale(uid)
    all_assessments = Assessment.query.filter_by(user_id=uid).filter(Assessment.archived.is_(False)).all()
    graded_rows = []
    subject_values = {}
    for item in all_assessments:
        percentage = assessment_percentage(item)
        if percentage is None or (item.grade or "").strip().upper() == "N/A":
            continue
        subject = (item.subject or "Unassigned").strip() or "Unassigned"
        subject_values.setdefault(subject, []).append(percentage)
        graded_rows.append({
            "title": item.title, "subject": subject, "percentage": percentage,
            "grade": grade_for_percentage(percentage, scale) or "—",
            "due": parse_homework_date(item.due_date),
        })
    graded_rows.sort(key=lambda row: (row["due"] or date.max), reverse=True)
    overall_average = (sum(row["percentage"] for row in graded_rows) / len(graded_rows)) if graded_rows else None
    overall_grade = grade_for_percentage(overall_average, scale) if overall_average is not None else None
    subject_averages = []
    for subject, values in subject_values.items():
        average = sum(values) / len(values)
        subject_averages.append({
            "subject": subject, "average": average, "count": len(values),
            "grade": grade_for_percentage(average, scale) or "—",
        })
    subject_averages.sort(key=lambda row: row["subject"].lower())

    all_sessions = PanoramaSession.query.filter(PanoramaSession.user_id == uid,
                                                PanoramaSession.completed_at.isnot(None)).all()
    total_minutes = sum(max(1, item.study_length or 25) * max(1, item.cycles or 1) for item in all_sessions)
    week_minutes = sum(max(1, item.study_length or 25) * max(1, item.cycles or 1) for item in sessions)
    return render_template("share_summary.html", owner=user, monday=monday, tasks=tasks,
                           assessments=assessments, minutes=week_minutes,
                           total_minutes=total_minutes, session_count=len(all_sessions),
                           graded_rows=graded_rows[:8], graded_count=len(graded_rows),
                           overall_average=overall_average, overall_grade=overall_grade,
                           subject_averages=subject_averages,
                           next_week=next_week, link=link)


def shared_pack(link, user):
    uid = user.id
    files = []
    notes = []
    for item in Resource.query.filter_by(user_id=uid).order_by(Resource.subject.asc(), Resource.uploaded_at.desc()).all():
        if item.filename:
            files.append({"kind": "resource", "id": item.id, "title": item.title or item.original_filename,
                          "subject": item.subject, "subheading": item.subheading or ""})
        if item.note:
            notes.append({"kind": "resource", "id": item.id, "title": item.title or "Note",
                          "subject": item.subject, "note": item.note})
    for item in AssessmentFile.query.filter_by(user_id=uid).all():
        if not item.filename:
            continue
        assessment = item.assessment
        files.append({"kind": "assessment", "id": item.id,
                      "title": item.original_filename or item.filename,
                      "subject": (assessment.subject if assessment else "") or "",
                      "subheading": (item.category or "Assessment").replace("_", " ").title()})
    for item in HomeworkResource.query.filter_by(user_id=uid).all():
        if not item.filename:
            continue
        task = Task.query.get(item.task_id)
        files.append({"kind": "homework", "id": item.id,
                      "title": item.original_filename or item.filename,
                      "subject": (task.subject if task else "") or "",
                      "subheading": "Homework"})
    files.sort(key=lambda row: (row["subject"].lower(), row["title"].lower()))
    notes.sort(key=lambda row: (row["subject"].lower(), row["title"].lower()))
    return render_template("share_pack.html", owner=user, files=files, notes=notes, link=link)


@app.route("/share/pack/file/<kind>/<int:item_id>")
def shared_pack_file(kind, item_id):
    token = request.args.get("token", "")
    link, user = _share_context(token)
    if not link or link.kind != "pack":
        abort(404)
    if kind == "resource":
        item = Resource.query.filter_by(id=item_id, user_id=user.id).first()
    elif kind == "assessment":
        item = AssessmentFile.query.filter_by(id=item_id, user_id=user.id).first()
    elif kind == "homework":
        item = HomeworkResource.query.filter_by(id=item_id, user_id=user.id).first()
    else:
        abort(404)
    if not item or not item.filename:
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, item.filename, as_attachment=True,
                               download_name=getattr(item, "original_filename", None) or item.filename)


# =========================================================
# STUDY GROUP CHECKLISTS
# =========================================================

@app.route("/groups/create", methods=["POST"])
def group_create():
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    title = request.form.get("title", "").strip()
    if not title:
        flash("Give the checklist a title.", "error")
        return redirect(url_for("share_page"))
    lst = StudyGroupList(user_id=uid, token=secrets.token_urlsafe(12), title=title[:200],
                         subject=request.form.get("subject", "").strip() or None)
    db.session.add(lst)
    db.session.commit()
    for line in (request.form.get("items", "") or "").splitlines():
        if line.strip():
            db.session.add(StudyGroupItem(list_id=lst.id, text=line.strip()[:300], position=0))
    log_audit(uid, "share", "group", lst.id, title)
    db.session.commit()
    flash("Study group checklist created.", "success")
    return redirect(url_for("share_page"))


@app.route("/g/<token>", methods=["GET", "POST"])
def group_view(token):
    lst = StudyGroupList.query.filter_by(token=token).first()
    if not lst:
        abort(404)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            text = request.form.get("text", "").strip()
            if text:
                db.session.add(StudyGroupItem(list_id=lst.id, text=text[:300]))
        elif action == "toggle":
            item = StudyGroupItem.query.filter_by(id=request.form.get("item_id", type=int), list_id=lst.id).first()
            if item:
                item.done = not item.done
        elif action == "clear":
            StudyGroupItem.query.filter_by(list_id=lst.id, done=True).delete()
        db.session.commit()
        return redirect(url_for("group_view", token=token))
    items = StudyGroupItem.query.filter_by(list_id=lst.id).order_by(StudyGroupItem.id.asc()).all()
    return render_template("group_checklist.html", group=lst, items=items,
                           owner=User.query.get(lst.user_id))


# =========================================================
# DATA TOOLS PAGE
# =========================================================

@app.route("/data")
def data_tools():
    required = login_required()
    if required:
        return required
    return render_template("data_tools.html")


# =========================================================
# DATABASE
# =========================================================

with app.app_context():
    db.create_all()
    # Lightweight SQLite migration for existing SmartStride databases.
    from sqlalchemy import text, inspect
    inspector = inspect(db.engine)
    user_columns = {column["name"] for column in inspector.get_columns("user")}
    panorama_columns = {column["name"] for column in inspector.get_columns("panorama_session")}
    calendar_event_columns = {column["name"] for column in inspector.get_columns("calendar_event")}
    assessment_columns = {column["name"] for column in inspector.get_columns("assessment")}
    assessment_file_table_exists = "assessment_file" in inspector.get_table_names()
    with db.engine.begin() as connection:
        if not assessment_file_table_exists:
            connection.execute(text("""
                CREATE TABLE assessment_file (
                    id INTEGER NOT NULL PRIMARY KEY,
                    assessment_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    category VARCHAR(30) NOT NULL,
                    filename VARCHAR(500) NOT NULL,
                    original_filename VARCHAR(300) NOT NULL,
                    uploaded_at DATETIME,
                    FOREIGN KEY(assessment_id) REFERENCES assessment (id),
                    FOREIGN KEY(user_id) REFERENCES user (id)
                )
            """))
        if "email_verified" not in user_columns:
            connection.execute(text("ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0"))
        if "verification_token" not in user_columns:
            connection.execute(text("ALTER TABLE user ADD COLUMN verification_token VARCHAR(300)"))
        if "percentage_override" not in assessment_columns:
            connection.execute(text("ALTER TABLE assessment ADD COLUMN percentage_override FLOAT"))
        if "title" not in panorama_columns:
            connection.execute(text("ALTER TABLE panorama_session ADD COLUMN title VARCHAR(200) DEFAULT 'Study Session'"))
        if "recurrence_rule" not in calendar_event_columns:
            connection.execute(text("ALTER TABLE calendar_event ADD COLUMN recurrence_rule VARCHAR(50) DEFAULT 'none' NOT NULL"))
        if "recurrence_interval" not in calendar_event_columns:
            connection.execute(text("ALTER TABLE calendar_event ADD COLUMN recurrence_interval INTEGER DEFAULT 1 NOT NULL"))
        if "recurrence_unit" not in calendar_event_columns:
            connection.execute(text("ALTER TABLE calendar_event ADD COLUMN recurrence_unit VARCHAR(20) DEFAULT 'day' NOT NULL"))
        if "recurrence_until" not in calendar_event_columns:
            connection.execute(text("ALTER TABLE calendar_event ADD COLUMN recurrence_until VARCHAR(20)"))
        if "recurrence_exceptions" not in calendar_event_columns:
            connection.execute(text("ALTER TABLE calendar_event ADD COLUMN recurrence_exceptions TEXT"))
        if "instructions" not in assessment_columns:
            connection.execute(text("ALTER TABLE assessment ADD COLUMN instructions TEXT"))
        if "happy_with_grade" not in assessment_columns:
            connection.execute(text("ALTER TABLE assessment ADD COLUMN happy_with_grade VARCHAR(20)"))
        if "effort" not in assessment_columns:
            connection.execute(text("ALTER TABLE assessment ADD COLUMN effort INTEGER"))
        if "feedback" not in assessment_columns:
            connection.execute(text("ALTER TABLE assessment ADD COLUMN feedback TEXT"))
        if "weight" not in assessment_columns:
            connection.execute(text("ALTER TABLE assessment ADD COLUMN weight FLOAT DEFAULT 1.0"))


# =========================================================
# RUN APPLICATION
# =========================================================

with app.app_context():
    from sqlalchemy import text as sql_text, inspect as sql_inspect
    inspector = sql_inspect(db.engine)
    if "practice_test" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("practice_test")}
        with db.engine.begin() as connection:
            for name, ddl in (
                ("total_marks", "FLOAT"),
                ("score", "FLOAT"),
                ("percentage", "FLOAT"),
                ("grade", "VARCHAR(20)"),
                ("completed_at", "DATETIME"),
            ):
                if name not in columns:
                    connection.execute(sql_text("ALTER TABLE practice_test ADD COLUMN %s %s" % (name, ddl)))


with app.app_context():
    from sqlalchemy import text as settings_text, inspect as settings_inspect
    settings_inspector = settings_inspect(db.engine)
    if "user" in settings_inspector.get_table_names():
        user_columns = {column["name"] for column in settings_inspector.get_columns("user")}
        if "display_name" not in user_columns:
            with db.engine.begin() as connection:
                connection.execute(settings_text("ALTER TABLE user ADD COLUMN display_name VARCHAR(100)"))
        if "onboarded" not in user_columns:
            with db.engine.begin() as connection:
                connection.execute(settings_text("ALTER TABLE user ADD COLUMN onboarded BOOLEAN DEFAULT 1"))
        if "year_level" not in user_columns:
            with db.engine.begin() as connection:
                connection.execute(settings_text("ALTER TABLE user ADD COLUMN year_level VARCHAR(50)"))


# =========================================================
# 0.5.0 SCHEMA MIGRATIONS
# =========================================================

with app.app_context():
    from sqlalchemy import text as v5_text, inspect as v5_inspect
    v5_inspector = v5_inspect(db.engine)
    v5_tables = set(v5_inspector.get_table_names())
    extra_columns = {
        "subject": [("icon", "VARCHAR(20) DEFAULT '📘' NOT NULL"), ("archived", "BOOLEAN DEFAULT 0 NOT NULL")],
        "task": [("archived", "BOOLEAN DEFAULT 0 NOT NULL"), ("pinned", "BOOLEAN DEFAULT 0 NOT NULL")],
        "assessment": [("archived", "BOOLEAN DEFAULT 0 NOT NULL")],
        "todo": [("archived", "BOOLEAN DEFAULT 0 NOT NULL")],
    }
    with db.engine.begin() as v5_connection:
        for table_name, columns in extra_columns.items():
            if table_name not in v5_tables:
                continue
            existing = {column["name"] for column in v5_inspector.get_columns(table_name)}
            for column_name, ddl in columns:
                if column_name not in existing:
                    v5_connection.execute(v5_text("ALTER TABLE %s ADD COLUMN %s %s" % (table_name, column_name, ddl)))


# Fix check-ins and quests saved with the old UTC date
with app.app_context():
    try:
        changed = False
        for row in DailyCheckIn.query.all():
            if row.created_at:
                local_day = local_date_of(row.created_at).isoformat()
                if row.check_date != local_day:
                    row.check_date = local_day
                    changed = True
        for row in QuestDone.query.all():
            if row.created_at:
                local_day = local_date_of(row.created_at).isoformat()
                if row.quest_date != local_day:
                    row.quest_date = local_day
                    changed = True
        if changed:
            db.session.commit()
    except Exception:
        db.session.rollback()


if __name__ == "__main__":

    start_push_worker()

    app.run(

        host=os.environ.get("HOST", "0.0.0.0"),

        port=int(os.environ.get("PORT", "5000")),

        debug=os.environ.get("FLASK_DEBUG", "0") == "1"

    )
