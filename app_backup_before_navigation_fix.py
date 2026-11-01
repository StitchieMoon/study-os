from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    url_for,
    flash,
    send_from_directory
)

from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

import os
import secrets
import smtplib
from email.message import EmailMessage

from datetime import datetime, timedelta


# =========================================================
# APP
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "study-os-development-secret-change-this"
)


# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///"
    + os.path.join(BASE_DIR, "study_os.db")
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["UPLOAD_FOLDER"] = os.path.join(
    BASE_DIR,
    "uploads"
)

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

db = SQLAlchemy(app)

os.makedirs(
    app.config["UPLOAD_FOLDER"],
    exist_ok=True
)


# =========================================================
# DATE FORMATTING
# =========================================================

def format_date(date_string):

    if not date_string:
        return ""

    try:

        date = datetime.strptime(
            date_string,
            "%Y-%m-%d"
        )

        return date.strftime(
            "%d/%m/%Y"
        )

    except ValueError:

        return date_string


app.jinja_env.filters["date_format"] = format_date


# =========================================================
# LOGIN HELPERS
# =========================================================

def logged_in():

    return "user_id" in session


def current_user_id():

    return session.get("user_id")


def login_required():

    if not logged_in():
        return redirect("/login")

    return None


def current_user():

    if not logged_in():
        return None

    return User.query.get(
        session["user_id"]
    )


# =========================================================
# USER
# =========================================================

class User(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
        nullable=False,
        unique=True
    )

    email = db.Column(
        db.String(255),
        nullable=False,
        unique=True
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# SUBJECT
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
        db.String(20),
        nullable=False,
        default="#6C63FF"
    )


# =========================================================
# HOMEWORK
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

    completed = db.Column(
        db.Boolean,
        default=False
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    reflection = db.Column(
        db.Text,
        nullable=True
    )

    finished_file = db.Column(
        db.String(300),
        nullable=True
    )


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
        nullable=False
    )

    filename = db.Column(
        db.String(300),
        nullable=False
    )

    uploaded_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template(
        "index.html"
    )


# =========================================================
# TO-DO
# =========================================================

# =========================================================
# TO-DO
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

    return render_template(
        "todos.html",
        todos=todos
    )


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

    date = request.form.get(
        "date",
        ""
    ).strip()

    if title:

        todo = Todo(
            user_id=uid,
            title=title,
            date=date if date else None,
            completed=False,
            created_at=datetime.now()
        )

        db.session.add(todo)
        db.session.commit()

    return redirect(
        request.form.get(
            "redirect_page",
            "/todos"
        )
    )


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
    todo.completed_at = datetime.now()

    db.session.commit()

    return redirect(
        request.form.get(
            "redirect_page",
            "/todos"
        )
    )


@app.route(
    "/uncomplete-todo/<int:todo_id>",
    methods=["POST"]
)
def uncomplete_todo(todo_id):

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
            "/todos/history"
        )
    )


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

    db.session.delete(todo)
    db.session.commit()

    return redirect(
        request.form.get(
            "redirect_page",
            "/todos"
        )
    )


@app.route("/todos/history")
def todo_history():

    required = login_required()

    if required:
        return required

    uid = current_user_id()

    todos = Todo.query.filter_by(
        user_id=uid,
        completed=True
    ).order_by(
        Todo.completed_at.desc()
    ).all()

    return render_template(
        "todo_history.html",
        todos=todos
    )


@app.route("/assessments")
def assessments():

    required = login_required()

    if required:
        return required

    uid = current_user_id()

    all_assessments = Assessment.query.filter_by(
        user_id=uid
    ).order_by(
        Assessment.due_date.asc()
    ).all()

    subjects = Subject.query.filter_by(
        user_id=uid
    ).all()

    return render_template(
        "assessments.html",
        assessments=all_assessments,
        subjects=subjects
    )


@app.route(
    "/add-assessment",
    methods=["POST"]
)
def add_assessment():

    required = login_required()

    if required:
        return required

    uid = current_user_id()

    name = request.form.get(
        "name",
        ""
    ).strip()

    if name:

        assessment = Assessment(
            user_id=uid,
            name=name,
            subject=request.form.get(
                "subject",
                ""
            ),
            due_date=request.form.get(
                "due_date",
                ""
            ),
            rubric=request.form.get(
                "rubric",
                ""
            ),
            resources=request.form.get(
                "resources",
                ""
            )
        )

        db.session.add(
            assessment
        )

        db.session.commit()

    return redirect(
        "/assessments"
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

    except ValueError:

        flash(
            "Score must be a number.",
            "error"
        )

        return redirect(
            "/assessments"
        )

    assessment.grade = request.form.get(
        "grade",
        ""
    )

    assessment.happy_with_grade = request.form.get(
        "happy_with_grade",
        ""
    )

    assessment.completed = True

    assessment.completed_at = datetime.now()

    db.session.commit()

    return redirect(
        "/grades"
    )


@app.route("/grades")
def grades():

    required = login_required()

    if required:
        return required

    uid = current_user_id()

    subjects = Subject.query.filter_by(
        user_id=uid
    ).all()

    graded_assessments = Assessment.query.filter(
        Assessment.user_id == uid,
        Assessment.score.isnot(None),
        Assessment.total_score.isnot(None)
    ).all()

    overall_percentages = []

    for assessment in graded_assessments:

        if assessment.total_score:

            percentage = (
                assessment.score
                / assessment.total_score
            ) * 100

            overall_percentages.append(
                percentage
            )

    overall_average = None

    if overall_percentages:

        overall_average = (
            sum(overall_percentages)
            / len(overall_percentages)
        )

    subject_data = []

    for subject in subjects:

        subject_assessments = Assessment.query.filter(
            Assessment.user_id == uid,
            Assessment.subject == subject.name,
            Assessment.score.isnot(None),
            Assessment.total_score.isnot(None)
        ).all()

        percentages = []

        for assessment in subject_assessments:

            if assessment.total_score:

                percentages.append(
                    (
                        assessment.score
                        / assessment.total_score
                    ) * 100
                )

        average = None

        if percentages:

            average = (
                sum(percentages)
                / len(percentages)
            )

        subject_data.append({
            "subject": subject,
            "assessments": subject_assessments,
            "average": average
        })

    return render_template(
        "grades.html",
        assessments=graded_assessments,
        subjects=subjects,
        subject_data=subject_data,
        overall_average=overall_average
    )


# =========================================================
# CALENDAR
# =========================================================

@app.route("/calendar")
def calendar():

    required = login_required()

    if required:
        return required

    uid = current_user_id()

    subjects = Subject.query.filter_by(
        user_id=uid
    ).all()

    return render_template(
        "calendar.html",
        subjects=subjects
    )


@app.route("/calendar/<date_string>")
def calendar_day(date_string):

    required = login_required()

    if required:
        return required

    uid = current_user_id()

    try:

        selected_date = datetime.strptime(
            date_string,
            "%Y-%m-%d"
        )

    except ValueError:

        return redirect("/calendar")

    display_date = selected_date.strftime(
        "%A, %d/%m/%Y"
    )

    homework = Task.query.filter(
        Task.user_id == uid,
        Task.due_date == date_string,
        Task.completed == False
    ).order_by(
        Task.due_date.asc()
    ).all()

    todos = Todo.query.filter(
        Todo.user_id == uid,
        Todo.date == date_string,
        Todo.completed == False
    ).order_by(
        Todo.created_at.asc()
    ).all()

    assessments = Assessment.query.filter(
        Assessment.user_id == uid,
        Assessment.due_date == date_string,
        Assessment.completed == False
    ).order_by(
        Assessment.due_date.asc()
    ).all()

    events = CalendarEvent.query.filter(
        CalendarEvent.user_id == uid,
        CalendarEvent.event_date == date_string
    ).order_by(
        CalendarEvent.start_time.asc()
    ).all()

    previous_day = (
        selected_date - timedelta(days=1)
    ).strftime("%Y-%m-%d")

    next_day = (
        selected_date + timedelta(days=1)
    ).strftime("%Y-%m-%d")

    return render_template(
        "calendar_day.html",
        selected_date=selected_date,
        display_date=display_date,
        homework=homework,
        todos=todos,
        assessments=assessments,
        events=events,
        previous_day=previous_day,
        next_day=next_day
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
    )

    if not title or not event_date:

        return redirect("/calendar")

    event = CalendarEvent(
        user_id=uid,
        title=title,
        event_date=event_date,
        start_time=request.form.get(
            "start_time",
            ""
        ),
        end_time=request.form.get(
            "end_time",
            ""
        ),
        subject=request.form.get(
            "subject",
            ""
        ),
        event_type=request.form.get(
            "event_type",
            "Event"
        ),
        notes=request.form.get(
            "notes",
            ""
        )
    )

    db.session.add(event)

    db.session.commit()

    return redirect(
        f"/calendar/{event_date}"
    )


@app.route(
    "/calendar-data/<date_string>"
)
def calendar_data(date_string):

    required = login_required()

    if required:
        return required

    uid = current_user_id()

    try:

        datetime.strptime(
            date_string,
            "%Y-%m-%d"
        )

    except ValueError:

        return {
            "homework": [],
            "todos": [],
            "assessments": [],
            "events": []
        }

    homework = Task.query.filter(
        Task.user_id == uid,
        Task.due_date == date_string,
        Task.completed == False
    ).all()

    todos = Todo.query.filter(
        Todo.user_id == uid,
        Todo.date == date_string,
        Todo.completed == False
    ).all()

    assessments = Assessment.query.filter(
        Assessment.user_id == uid,
        Assessment.due_date == date_string,
        Assessment.completed == False
    ).all()

    events = CalendarEvent.query.filter(
        CalendarEvent.user_id == uid,
        CalendarEvent.event_date == date_string
    ).all()

    return {

        "homework": [

            {
                "id": item.id,
                "title": item.title,
                "subject": item.subject or "",
                "type": "homework"
            }

            for item in homework

        ],

        "todos": [

            {
                "id": item.id,
                "title": item.title,
                "type": "todo"
            }

            for item in todos

        ],

        "assessments": [

            {
                "id": item.id,
                "title": item.name,
                "subject": item.subject or "",
                "type": "assessment"
            }

            for item in assessments

        ],

        "events": [

            {
                "id": item.id,
                "title": item.title,
                "start_time": item.start_time or "",
                "end_time": item.end_time or "",
                "subject": item.subject or "",
                "type": item.event_type or "Event"
            }

            for item in events

        ]

    }




# =========================================================
# PRACTICE EXAMS
# =========================================================

@app.route(
    "/practice-exams"
)
def practice_exams():

    required = login_required()

    if required:
        return required

    uid = current_user_id()

    exams = PracticeExam.query.filter_by(
        user_id=uid
    ).order_by(
        PracticeExam.created_at.desc()
    ).all()

    subjects = Subject.query.filter_by(
        user_id=uid
    ).all()

    return render_template(
        "practice_exams.html",
        exams=exams,
        subjects=subjects
    )


@app.route(
    "/add-practice-exam",
    methods=["POST"]
)
def add_practice_exam():

    required = login_required()

    if required:
        return required

    uid = current_user_id()

    title = request.form.get(
        "title",
        ""
    ).strip()

    if title:

        exam = PracticeExam(
            user_id=uid,
            title=title,
            subject=request.form.get(
                "subject",
                ""
            )
        )

        db.session.add(
            exam
        )

        db.session.commit()

    return redirect(
        "/practice-exams"
    )


# =========================================================
# SETTINGS
# =========================================================

@app.route(
    "/settings",
    methods=["GET", "POST"]
)
def settings():

    required = login_required()

    if required:
        return required

    uid = current_user_id()

    user = current_user()

    user_settings = UserSettings.query.filter_by(
        user_id=uid
    ).first()

    if not user_settings:

        user_settings = UserSettings(
            user_id=uid
        )

        db.session.add(
            user_settings
        )

        db.session.commit()

    if request.method == "POST":

        new_username = request.form.get(
            "username",
            user.username
        ).strip()

        new_email = request.form.get(
            "email",
            user.email
        ).strip().lower()

        if new_username:

            duplicate_username = User.query.filter(
                User.id != uid,
                db.func.lower(User.username)
                == new_username.lower()
            ).first()

            if duplicate_username:

                flash(
                    "That username is already taken.",
                    "error"
                )

                return redirect(
                    "/settings"
                )

            user.username = new_username

            session["username"] = new_username

        if new_email:

            duplicate_email = User.query.filter(
                User.id != uid,
                db.func.lower(User.email)
                == new_email
            ).first()

            if duplicate_email:

                flash(
                    "That email is already registered.",
                    "error"
                )

                return redirect(
                    "/settings"
                )

            user.email = new_email

        user_settings.theme = request.form.get(
            "theme",
            user_settings.theme
        )

        user_settings.accent_colour = request.form.get(
            "accent_colour",
            user_settings.accent_colour
        )

        db.session.commit()

        flash(
            "Settings saved.",
            "success"
        )

        return redirect(
            "/settings"
        )

    return render_template(
        "settings.html",
        user=user,
        settings=user_settings
    )


# =========================================================
# SAVE PANORAMA SESSION
# =========================================================




# =========================================================
# DELETE PANORAMA
# =========================================================



# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True
    )