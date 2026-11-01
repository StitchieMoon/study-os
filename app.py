import os
import json
import secrets
import smtplib
import calendar as pycalendar
from email.message import EmailMessage
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from datetime import date, datetime, timedelta

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


# =========================================================
# APP SETUP
# =========================================================

BASE_DIR = os.path.abspath(
    os.path.dirname(__file__)
)


UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)


os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


app = Flask(__name__)


app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "study-os-development-secret"
)


app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///study_os.db"
)


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SMTP_SERVER"] = os.environ.get("SMTP_SERVER", "")
app.config["SMTP_PORT"] = int(os.environ.get("SMTP_PORT", "587"))
app.config["SMTP_USERNAME"] = os.environ.get("SMTP_USERNAME", "")
app.config["SMTP_PASSWORD"] = os.environ.get("SMTP_PASSWORD", "")
app.config["EMAIL_FROM"] = os.environ.get("EMAIL_FROM", app.config["SMTP_USERNAME"])
app.config["SMTP_USE_TLS"] = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

db = SQLAlchemy(app)
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])


# =========================================================
# TEMPLATE FILTERS
# =========================================================

def parse_homework_date(value):

    if not value:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()

    # ISO format is the canonical format stored by Study OS.
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except (ValueError, TypeError):
            continue

    # Study OS uses Australian DD/MM/YYYY whenever a slash-formatted date is
    # encountered. This is important for dates such as 09/11/2026, where
    # interpreting the value as MM/DD/YYYY silently changes the due date.
    if "/" in text:
        parts = text.split("/")
        if len(parts) == 3 and all(part.isdigit() for part in parts):
            day, month, year = (int(part) for part in parts)
            try:
                return date(year, month, day)
            except ValueError:
                return None

    return None


def normalise_homework_date(value):

    parsed = parse_homework_date(value)

    if parsed is None:
        return ""

    return parsed.strftime("%Y-%m-%d")


@app.template_filter("date_format")
def date_format(value):

    if not value:
        return ""

    parsed = parse_homework_date(value)

    if parsed is not None:
        return parsed.strftime("%d/%m/%Y")

    return str(value)


@app.template_filter("homework_date_input")
def homework_date_input(value):

    parsed = parse_homework_date(value)

    if parsed is None:
        return ""

    return parsed.strftime("%Y-%m-%d")


# =========================================================
# USER MODEL
# =========================================================

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


# =========================================================
# SUBJECT MODEL
# =========================================================

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


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# HOMEWORK MODEL
# =========================================================

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


# =========================================================
# HOMEWORK RESOURCE MODEL
# =========================================================

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


# =========================================================
# ASSESSMENT MODEL
# =========================================================

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


    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


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
    with smtplib.SMTP(app.config["SMTP_SERVER"], app.config["SMTP_PORT"]) as server:
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
            "Please log in to access Study OS.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    return None


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
        completed=False
    ).count()


    assessment_count = Assessment.query.filter_by(
        user_id=uid,
        completed=False
    ).count()


    todo_count = Todo.query.filter_by(
        user_id=uid,
        completed=False
    ).count()


    todos = Todo.query.filter_by(
        user_id=uid,
        completed=False
    ).order_by(
        Todo.date.asc(),
        Todo.created_at.asc()
    ).all()

    tasks = Task.query.filter_by(
        user_id=uid,
        completed=False
    ).order_by(Task.due_date.asc()).all()

    assessments = Assessment.query.filter_by(
        user_id=uid,
        completed=False
    ).order_by(Assessment.due_date.asc()).all()

    return render_template(
        "index.html",
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
        assessments=assessments
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if logged_in():

        return redirect(
            url_for("home")
        )


    if request.method == "POST":

        identifier = request.form.get(
            "identifier",
            ""
        ).strip()


        password = request.form.get(
            "password",
            ""
        )


        if not identifier or not password:

            flash(
                "Please enter your username or email and password.",
                "error"
            )

            return redirect(
                url_for("login")
            )


        user = User.query.filter(
            db.or_(
                db.func.lower(
                    User.username
                ) == identifier.lower(),

                db.func.lower(
                    User.email
                ) == identifier.lower()
            )
        ).first()


        if not user:

            flash(
                "Invalid username, email, or password.",
                "error"
            )

            return redirect(
                url_for("login")
            )


        if not check_password_hash(
            user.password_hash,
            password
        ):

            flash(
                "Invalid username, email, or password.",
                "error"
            )

            return redirect(
                url_for("login")
            )


        session.clear()


        session["user_id"] = user.id


        session["username"] = user.username


        flash(
            f"Welcome back, {user.username}.",
            "success"
        )


        return redirect(
            url_for("home")
        )


    return render_template(
        "login.html"
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if logged_in():

        return redirect(
            url_for("home")
        )


    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()


        email = request.form.get(
            "email",
            ""
        ).strip().lower()


        password = request.form.get(
            "password",
            ""
        )


        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        if (
            not username
            or not email
            or not password
            or not confirm_password
        ):

            flash(
                "Please complete all fields.",
                "error"
            )

            return redirect(
                url_for("register")
            )


        if len(username) < 3:

            flash(
                "Username must be at least 3 characters.",
                "error"
            )

            return redirect(
                url_for("register")
            )


        if len(password) < 6:

            flash(
                "Password must be at least 6 characters.",
                "error"
            )

            return redirect(
                url_for("register")
            )


        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return redirect(
                url_for("register")
            )


        existing_username = User.query.filter(
            db.func.lower(
                User.username
            ) == username.lower()
        ).first()


        if existing_username:

            flash(
                "That username is already taken.",
                "error"
            )

            return redirect(
                url_for("register")
            )


        existing_email = User.query.filter(
            db.func.lower(
                User.email
            ) == email
        ).first()


        if existing_email:

            flash(
                "That email is already registered.",
                "error"
            )

            return redirect(
                url_for("register")
            )


        user = User(

            username=username,

            email=email,

            password_hash=generate_password_hash(
                password
            )

        )


        db.session.add(
            user
        )


        db.session.commit()

        token = make_token(user.email, "verify")
        user.verification_token = token
        db.session.commit()
        try:
            verify_url = url_for("verify_email", token=token, _external=True)
            send_email(user.email, "Verify your Study OS email", f"Welcome to Study OS. Verify your email using this link (valid for 24 hours):\n\n{verify_url}")
        except Exception:
            pass

        session.clear()


        session["user_id"] = user.id


        session["username"] = user.username


        flash(
            "Your Study OS account has been created successfully.",
            "success"
        )


        return redirect(
            url_for("home")
        )


    return render_template(
        "register.html"
    )


# =========================================================
# SIGNUP COMPATIBILITY
# =========================================================

@app.route("/signup")
def signup():

    return redirect(
        url_for("register")
    )


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Please enter the email linked to your account.", "error")
            return redirect(url_for("forgot_password"))
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user:
            token = make_token(user.email, "reset")
            reset_url = url_for("reset_password", token=token, _external=True)
            try:
                sent = send_email(user.email, "Reset your Study OS password", f"Use this link to reset your password (valid for 1 hour):\n\n{reset_url}")
            except Exception:
                sent = False
            if not sent:
                flash("Email sending is not configured. Set SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD and EMAIL_FROM before using password reset.", "error")
                return redirect(url_for("forgot_password"))
        flash("If that email is linked to an account, a password reset link has been sent.", "success")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = read_token(token, "reset", 3600)
    except (BadSignature, SignatureExpired):
        flash("This password reset link is invalid or has expired.", "error")
        return redirect(url_for("forgot_password"))
    user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    if not user:
        flash("Account not found.", "error")
        return redirect(url_for("forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not password or not confirm_password:
            flash("Please complete both password fields.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        else:
            user.password_hash = generate_password_hash(password)
            db.session.commit()
            flash("Your password has been changed. You can now log in.", "success")
            return redirect(url_for("login"))
    return render_template("reset_password.html", token=token)

@app.route("/verify-email/<token>")
def verify_email(token):
    try:
        email = read_token(token, "verify", 86400)
    except (BadSignature, SignatureExpired):
        flash("This verification link is invalid or has expired.", "error")
        return redirect(url_for("login"))
    user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    if user:
        user.email_verified = True
        user.verification_token = None
        db.session.commit()
    flash("Your email has been verified.", "success")
    return redirect(url_for("home" if logged_in() else "login"))

# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()


    flash(
        "You have been logged out.",
        "success"
    )


    return redirect(
        url_for("login")
    )


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
        user_id=uid
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

            completed=False

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

        user_id=uid

    ).first_or_404()


    all_subjects = Subject.query.filter_by(

        user_id=uid

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

            completed=False

        ).count()


    subject_tasks = Task.query.filter_by(

        user_id=uid,

        subject=subject.name,

        completed=False

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

                    colour=colour

                )

            )


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

        user_id=uid

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


    subject.name = new_name

    subject.colour = new_colour


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

        user_id=uid

    ).first_or_404()


    db.session.delete(
        subject
    )


    db.session.commit()


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

        user_id=uid

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

@app.route("/tasks")
def tasks():

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    all_tasks = Task.query.filter_by(

        user_id=uid,

        completed=False

    ).all()

    # Sort by the actual calendar date so both old YYYY-MM-DD records
    # and any legacy DD/MM/YYYY records appear in true chronological order.
    all_tasks.sort(
        key=lambda item: (
            parse_homework_date(item.due_date) or date.max,
            item.id
        )
    )


    all_subjects = Subject.query.filter_by(

        user_id=uid

    ).order_by(

        Subject.name.asc()

    ).all()


    return render_template(

        "tasks.html",

        tasks=all_tasks,

        subjects=all_subjects,

        viewing_task=False,

        task=None,

        resources=[]

    )


@app.route(
    "/add-task",
    methods=["POST"]
)
def add_task():

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    title = request.form.get(
        "title",
        ""
    ).strip()


    if not title:

        return redirect(
            url_for("tasks")
        )


    task = Task(

        user_id=uid,

        title=title,

        subject=request.form.get(
            "subject",
            ""
        ).strip(),

        assigned_date=normalise_homework_date(
            request.form.get("assigned_date", "").strip()
        ),

        due_date=normalise_homework_date(
            request.form.get("due_date", "").strip()
        ),

        notes=request.form.get(
            "notes",
            ""
        ).strip(),

        completed=False

    )


    db.session.add(
        task
    )


    db.session.commit()


    return redirect(

        request.form.get(
            "redirect_page",
            url_for("tasks")
        )

    )


@app.route(
    "/task/<int:task_id>"
)
def view_task(task_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    task = Task.query.filter_by(

        id=task_id,

        user_id=uid

    ).first_or_404()


    resources = HomeworkResource.query.filter_by(

        task_id=task.id,

        user_id=uid

    ).order_by(

        HomeworkResource.uploaded_at.desc()

    ).all()


    all_subjects = Subject.query.filter_by(

        user_id=uid

    ).order_by(

        Subject.name.asc()

    ).all()


    current_tasks = Task.query.filter_by(

        user_id=uid,

        completed=False

    ).order_by(

        Task.due_date.asc(),

        Task.id.asc()

    ).all()


    return render_template(

        "tasks.html",

        tasks=current_tasks,

        subjects=all_subjects,

        viewing_task=True,

        task=task,

        resources=resources

    )


@app.route(
    "/edit-task/<int:task_id>",
    methods=["POST"]
)
def edit_task(task_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    task = Task.query.filter_by(

        id=task_id,

        user_id=uid

    ).first_or_404()


    title = request.form.get(
        "title",
        ""
    ).strip()


    if not title:

        flash(
            "Homework name cannot be empty.",
            "error"
        )

        return redirect(
            url_for(
                "view_task",
                task_id=task_id
            )
        )


    task.title = title


    task.subject = request.form.get(
        "subject",
        ""
    ).strip()


    task.assigned_date = normalise_homework_date(
        request.form.get("assigned_date", "").strip()
    )


    task.due_date = normalise_homework_date(
        request.form.get("due_date", "").strip()
    )


    db.session.commit()


    return redirect(
        url_for(
            "view_task",
            task_id=task_id
        )
    )


@app.route(
    "/save-task-notes/<int:task_id>",
    methods=["POST"]
)
def save_task_notes(task_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    task = Task.query.filter_by(

        id=task_id,

        user_id=uid

    ).first_or_404()


    task.notes = request.form.get(
        "notes",
        ""
    ).strip()


    db.session.commit()


    return redirect(
        url_for(
            "view_task",
            task_id=task_id
        )
    )


@app.route(
    "/upload-task-resource/<int:task_id>",
    methods=["POST"]
)
def upload_task_resource(task_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    task = Task.query.filter_by(

        id=task_id,

        user_id=uid

    ).first_or_404()


    uploaded_files = request.files.getlist(
        "resources"
    )


    for uploaded_file in uploaded_files:

        if not uploaded_file:

            continue


        original_filename = (
            uploaded_file.filename
            or ""
        ).strip()


        if not original_filename:

            continue


        safe_filename = secure_filename(
            original_filename
        )


        extension = ""


        if "." in safe_filename:

            extension = (
                "."
                + safe_filename.rsplit(
                    ".",
                    1
                )[1]
            )


        stored_filename = (
            secrets.token_hex(12)
            + extension
        )


        uploaded_file.save(

            os.path.join(

                app.config["UPLOAD_FOLDER"],

                stored_filename

            )

        )


        db.session.add(

            HomeworkResource(

                user_id=uid,

                task_id=task.id,

                filename=stored_filename,

                original_filename=original_filename

            )

        )


    db.session.commit()


    return redirect(
        url_for(
            "view_task",
            task_id=task_id
        )
    )


@app.route(
    "/download-task-resource/<int:resource_id>"
)
def download_task_resource(resource_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    resource = HomeworkResource.query.filter_by(

        id=resource_id,

        user_id=uid

    ).first_or_404()


    return send_from_directory(

        app.config["UPLOAD_FOLDER"],

        resource.filename,

        as_attachment=False,

        download_name=(
            resource.original_filename
            or resource.filename
        )

    )


@app.route(
    "/download-finished-task/<int:task_id>"
)
def download_finished_task(task_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    task = Task.query.filter_by(

        id=task_id,

        user_id=uid

    ).first_or_404()


    if not task.finished_file:

        abort(404)


    file_path = os.path.join(

        app.config["UPLOAD_FOLDER"],

        task.finished_file

    )


    if not os.path.isfile(file_path):

        abort(404)


    return send_from_directory(

        app.config["UPLOAD_FOLDER"],

        task.finished_file,

        as_attachment=False,

        download_name=task.finished_file

    )


@app.route(
    "/delete-task-resource/<int:resource_id>",
    methods=["POST"]
)
def delete_task_resource(resource_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    resource = HomeworkResource.query.filter_by(

        id=resource_id,

        user_id=uid

    ).first_or_404()


    task_id = resource.task_id


    file_path = os.path.join(

        app.config["UPLOAD_FOLDER"],

        resource.filename

    )


    if os.path.exists(file_path):

        try:

            os.remove(file_path)

        except OSError:

            pass


    db.session.delete(
        resource
    )


    db.session.commit()


    return redirect(
        url_for(
            "view_task",
            task_id=task_id
        )
    )


@app.route(
    "/complete-task/<int:task_id>",
    methods=["POST"]
)
def complete_task(task_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    task = Task.query.filter_by(

        id=task_id,

        user_id=uid

    ).first_or_404()


    task.completed = True


    task.completed_at = datetime.utcnow()


    task.reflection = request.form.get(
        "reflection",
        ""
    ).strip()


    finished_file = request.files.get(
        "finished_file"
    )


    if finished_file:

        original_filename = (
            finished_file.filename
            or ""
        ).strip()


        if original_filename:

            safe_filename = secure_filename(
                original_filename
            )


            extension = ""


            if "." in safe_filename:

                extension = (

                    "."

                    + safe_filename.rsplit(
                        ".",
                        1
                    )[1]

                )


            stored_filename = (

                "finished_"

                + secrets.token_hex(12)

                + extension

            )


            finished_file.save(

                os.path.join(

                    app.config["UPLOAD_FOLDER"],

                    stored_filename

                )

            )


            task.finished_file = stored_filename


    db.session.commit()


    return redirect(

        request.form.get(

            "redirect_page",

            url_for("task_history")

        )

    )


# Multiple route names are intentionally kept as compatibility aliases so older
# copies of the Homework History page cannot produce a 404 after an update.
@app.route("/uncomplete-task/<int:task_id>", methods=["POST"])
@app.route("/incomplete-task/<int:task_id>", methods=["POST"])
@app.route("/mark-incomplete/<int:task_id>", methods=["POST"])
@app.route("/mark-as-incomplete/<int:task_id>", methods=["POST"])
def uncomplete_task(task_id):

    required = login_required()

    if required:
        return required

    uid = current_user_id()

    task = Task.query.filter_by(
        id=task_id,
        user_id=uid
    ).first_or_404()

    task.completed = False
    task.completed_at = None

    db.session.commit()

    return redirect(
        request.form.get(
            "redirect_page",
            url_for("task_history")
        )
    )

@app.route("/tasks/history")
def task_history():

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    completed_tasks = Task.query.filter_by(

        user_id=uid,

        completed=True

    ).order_by(

        Task.completed_at.desc()

    ).all()


    return render_template(

        "task_history.html",

        completed_tasks=completed_tasks

    )


@app.route(
    "/delete-task/<int:task_id>",
    methods=["POST"]
)
def delete_task(task_id):

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    task = Task.query.filter_by(

        id=task_id,

        user_id=uid

    ).first_or_404()


    resources = HomeworkResource.query.filter_by(

        task_id=task.id,

        user_id=uid

    ).all()


    for resource in resources:

        file_path = os.path.join(

            app.config["UPLOAD_FOLDER"],

            resource.filename

        )


        if os.path.exists(file_path):

            try:

                os.remove(file_path)

            except OSError:

                pass


        db.session.delete(
            resource
        )


    if task.finished_file:

        finished_path = os.path.join(

            app.config["UPLOAD_FOLDER"],

            task.finished_file

        )


        if os.path.exists(finished_path):

            try:

                os.remove(finished_path)

            except OSError:

                pass


    db.session.delete(
        task
    )


    db.session.commit()


    return redirect(

        request.form.get(

            "redirect_page",

            url_for("tasks")

        )

    )


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

        completed=False

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


    todo.completed = True


    todo.completed_at = datetime.utcnow()


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


    db.session.delete(
        todo
    )


    db.session.commit()


    return redirect(

        request.form.get(

            "redirect_page",

            url_for("todos_page")

        )

    )



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
        "todos_history.html",
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

    todo.title = title
    todo.date = date_value
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

        # Do not reject a file just because its name contains characters
        # that secure_filename cannot transliterate (for example, some
        # non-Latin filenames). The stored filename is generated separately,
        # so the original filename can safely remain display-only metadata.
        safe_filename = secure_filename(
            original_filename
        )

        extension = ""
        source_name = safe_filename or original_filename
        if "." in source_name:
            extension = (
                "."
                + source_name.rsplit(
                    ".",
                    1
                )[1][:20]
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

    query = Assessment.query.filter_by(user_id=uid)

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
        user_id=uid
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
        user_id=uid
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
        value = round(float(percentage))
    except (TypeError, ValueError):
        return None
    eligible = [row for row in scale if str(row.get("label", "")).upper() != "N/A"
                and row.get("min") is not None and row.get("max") is not None]
    for row in eligible:
        try:
            if float(row["min"]) <= value <= float(row["max"]):
                return str(row["label"])
        except (TypeError, ValueError, KeyError):
            continue
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
    all_subjects = Subject.query.filter_by(user_id=uid).order_by(Subject.name.asc()).all()
    all_assessments = Assessment.query.filter_by(user_id=uid).order_by(
        Assessment.subject.asc(), Assessment.due_date.asc(), Assessment.created_at.asc(), Assessment.id.asc()
    ).all()

    rows = []
    percentages = []
    subject_stats = {}
    for assessment in all_assessments:
        percentage = assessment_percentage(assessment)
        saved_label = (assessment.grade or "").strip()
        # A result with a percentage always receives an automatic letter grade
        # from the percentage bands. Manually selected labels are retained only
        # for results without a percentage (or an explicit N/A).
        if saved_label.upper() == "N/A":
            grade_label = "N/A"
        elif percentage is not None:
            grade_label = grade_for_percentage(percentage, DEFAULT_GRADE_SCALE) or ""
        else:
            grade_label = saved_label

        subject_name = (assessment.subject or "Unassigned").strip() or "Unassigned"
        stats = subject_stats.setdefault(subject_name, {"percentages": [], "count": 0, "graded_count": 0})
        if percentage is not None and grade_label.upper() != "N/A":
            percentages.append(percentage)
            stats["percentages"].append(percentage)
            stats["graded_count"] += 1
        if percentage is not None or grade_label:
            stats["count"] += 1
        rows.append({"assessment": assessment, "percentage": percentage, "grade_label": grade_label})

    overall_average = sum(percentages) / len(percentages) if percentages else None
    average_grade_label = grade_for_percentage(overall_average, DEFAULT_GRADE_SCALE) if overall_average is not None else None

    for stats in subject_stats.values():
        stats["average_percentage"] = (
            sum(stats["percentages"]) / len(stats["percentages"])
            if stats["percentages"] else None
        )
        stats["average_grade_label"] = (
            grade_for_percentage(stats["average_percentage"], DEFAULT_GRADE_SCALE)
            if stats["average_percentage"] is not None else None
        )

    graded_assessment_count = sum(1 for row in rows if row["percentage"] is not None and row["grade_label"].upper() != "N/A")
    return render_template(
        "grades.html", assessments=all_assessments, rows=rows, subjects=all_subjects,
        subject_stats=subject_stats, overall_average=overall_average,
        average_grade_label=average_grade_label, grade_scale=scale,
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
        percentage_text = request.form.get("percentage", "").strip()
        assessment.score = float(score_text) if score_text else None
        assessment.total_score = float(total_text) if total_text else None
        if (assessment.score is None) != (assessment.total_score is None):
            raise ValueError("Enter both score and total score, or leave both blank.")
        if assessment.total_score is not None:
            if assessment.total_score <= 0 or assessment.score < 0 or assessment.score > assessment.total_score:
                raise ValueError("Score must be between 0 and a total score greater than 0.")
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
            assessment.grade = grade_for_percentage(current_percentage, DEFAULT_GRADE_SCALE)
        else:
            assessment.grade = selected_grade or None
    except ValueError as exc:
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

        user_id=uid

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

        due_date=date_string,

        completed=False

    ).order_by(

        Task.id.asc()

    ).all()


    todos = Todo.query.filter_by(

        user_id=uid,

        date=date_string,

        completed=False

    ).order_by(

        Todo.created_at.asc()

    ).all()


    assessments = Assessment.query.filter_by(

        user_id=uid,

        due_date=date_string,

        completed=False

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

        subjects=Subject.query.filter_by(user_id=uid).order_by(Subject.name.asc()).all()

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

    tasks = Task.query.filter_by(user_id=uid, completed=False).all()
    todos = Todo.query.filter_by(user_id=uid, completed=False).all()
    assessments = Assessment.query.filter_by(user_id=uid, completed=False).all()
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

        due_date=date_string,

        completed=False

    ).all()


    todos = Todo.query.filter_by(

        user_id=uid,

        date=date_string,

        completed=False

    ).all()


    assessments = Assessment.query.filter_by(

        user_id=uid,

        due_date=date_string,

        completed=False

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


@app.route("/panorama")
def panorama():
    required = login_required()
    if required:
        return required

    uid = current_user_id()
    all_subjects = Subject.query.filter_by(
        user_id=uid
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


@app.route("/add-panorama-session", methods=["POST"])
def add_panorama_session():
    required = login_required()
    if required:
        return required

    uid = current_user_id()

    try:
        study_length = max(1, int(request.form.get("study_length", 25)))
        break_length = max(0, int(request.form.get("break_length", 5)))
        cycles = max(1, int(request.form.get("cycles", 4)))
    except (TypeError, ValueError):
        flash("Panorama times and cycles must be valid numbers.", "error")
        return redirect(url_for("panorama"))

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
    flash("Panorama session saved.", "success")
    return redirect(url_for("panorama"))


@app.route("/delete-panorama/<int:session_id>", methods=["POST"])
def delete_panorama(session_id):
    required = login_required()
    if required:
        return required

    item = PanoramaSession.query.filter_by(
        id=session_id,
        user_id=current_user_id()
    ).first_or_404()

    db.session.delete(item)
    db.session.commit()
    flash("Panorama session deleted.", "success")
    return redirect(url_for("panorama"))


@app.route("/panorama/start/<int:session_id>")
def start_panorama_session(session_id):
    required = login_required()
    if required:
        return required

    item = PanoramaSession.query.filter_by(
        id=session_id,
        user_id=current_user_id()
    ).first_or_404()

    return render_template(
        "panorama_start.html",
        panorama_session=item
    )


@app.route("/panorama/music/<path:filename>")
def panorama_music(filename):
    """Serve Panorama audio from either the current or legacy audio directory."""
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
# DATABASE
# =========================================================

with app.app_context():
    db.create_all()
    # Lightweight SQLite migration for existing Study OS databases.
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


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )