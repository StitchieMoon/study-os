"""Authentication routes.

Owns logout, login, register, forgot/reset, email verification and the
legacy /signup redirect. Compatibility aliases in app.py preserve old
endpoint names and URLs.
"""
import sys
from datetime import datetime

from itsdangerous import BadSignature, SignatureExpired
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # When Flask is started with `python app.py`, the app module is __main__;
    # under WSGI it is imported as `app`. Never import it a second time:
    # doing so would define every SQLAlchemy model twice.
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    User = app_module.User
    db = app_module.db
    check_password_hash = app_module.check_password_hash
    logged_in = app_module.logged_in

    if logged_in():
        return redirect(url_for("home"))

    if request.method == "POST":
        identifier = (request.form.get("email") or request.form.get("identifier", "")).strip()
        password = request.form.get("password", "")

        if not identifier or not password:
            flash("Please enter your email and password.", "error")
            return redirect(url_for("auth.login"))

        user = User.query.filter(
            db.or_(
                db.func.lower(User.email) == identifier.lower(),
                db.func.lower(User.username) == identifier.lower(),
            )
        ).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Email or password is incorrect.", "error")
            return redirect(url_for("auth.login"))

        try:
            needs_verify = (
                not user.email_verified
                and user.created_at
                and user.created_at >= datetime(2026, 11, 3)
            )
        except Exception:
            needs_verify = False
        if needs_verify:
            session["pending_verify_email"] = user.email
            flash("Confirm your email and password to continue.", "error")
            return redirect(url_for("verify_email_pending"))

        session.clear()
        session["user_id"] = user.id
        session["username"] = user.username
        # Flask's default session cookie is a browser-session cookie. Only
        # make it a 30-day cookie when the person ticks the box.
        session.permanent = bool(request.form.get("remember"))
        flash(f"Welcome back, {user.username}.", "success")
        return redirect(url_for("home"))

    return render_template("login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    User = app_module.User
    db = app_module.db
    generate_password_hash = app_module.generate_password_hash
    logged_in = app_module.logged_in

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
                url_for("auth.register")
            )


        if len(username) < 3:

            flash(
                "Username must be at least 3 characters.",
                "error"
            )

            return redirect(
                url_for("auth.register")
            )


        if len(password) < 8:

            flash(
                "Password must be at least 8 characters.",
                "error"
            )

            return redirect(
                url_for("auth.register")
            )


        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return redirect(
                url_for("auth.register")
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
                url_for("auth.register")
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
                url_for("auth.register")
            )


        user = User(

            username=username,

            email=email,

            password_hash=generate_password_hash(
                password
            ),

            onboarded=True

        )


        db.session.add(
            user
        )


        db.session.commit()

        session.clear()
        session["pending_verify_email"] = user.email
        flash("Account created. Confirm your email to continue.", "success")
        return redirect(url_for("verify_email_pending"))


    return render_template(
        "register.html"
    )


@auth_bp.route("/signup")
def signup():
    """Legacy signup URL: send people to the current registration page."""
    return redirect(url_for("register"))


def mask_email(email):
    email = (email or "").strip()
    if len(email) <= 7:
        return (email[:1] + "•" * max(1, len(email) - 2) + email[-1:]) if email else "•••••"
    return email[:2] + "•" * (len(email) - 7) + email[-5:]


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    User = app_module.User
    db = app_module.db

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Please enter the email linked to your account.", "error")
            return redirect(url_for("auth.forgot_password"))
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user:
            session["reset_email"] = user.email
            return render_template("forgot_password_confirm.html", masked_email=mask_email(user.email), error=None)
        flash("If that email is linked to an account, you can continue.", "success")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")


@auth_bp.route("/forgot-password/confirm", methods=["POST"])
def forgot_password_confirm():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    make_token = app_module.make_token
    expected = session.get("reset_email")
    if not expected:
        flash("Start again from Forgot password.", "error")
        return redirect(url_for("auth.forgot_password"))
    entered = request.form.get("email", "").strip().lower()
    if entered != expected.lower():
        return render_template("forgot_password_confirm.html", masked_email=mask_email(expected),
                               error="That email does not match. Check the missing letters and try again.")
    token = make_token(expected, "reset")
    session.pop("reset_email", None)
    return redirect(url_for("auth.reset_password", token=token))


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    User = app_module.User
    db = app_module.db
    generate_password_hash = app_module.generate_password_hash
    read_token = app_module.read_token
    try:
        email = read_token(token, "reset", 3600)
    except (BadSignature, SignatureExpired):
        flash("This password reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))
    user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    if not user:
        flash("Account not found.", "error")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not password or not confirm_password:
            flash("Please complete both password fields.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        else:
            user.password_hash = generate_password_hash(password)
            db.session.commit()
            flash("Your password has been changed. You can now log in.", "success")
            return redirect(url_for("login"))
    return render_template("reset_password.html", token=token)

@auth_bp.route("/verify-email/pending", methods=["GET", "POST"])
def verify_email_pending():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    User = app_module.User
    db = app_module.db
    check_password_hash = app_module.check_password_hash
    email = session.get("pending_verify_email")
    if not email:
        return redirect(url_for("auth.login"))
    user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    if not user:
        session.pop("pending_verify_email", None)
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        entered = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if entered == email.lower() and check_password_hash(user.password_hash, password):
            user.email_verified = True
            db.session.commit()
            session.pop("pending_verify_email", None)
            session["user_id"] = user.id
            session["username"] = user.username
            flash("Email confirmed. Welcome to SmartStride.", "success")
            return redirect(url_for("home"))
        return render_template("verify_email_pending.html", pending_email=email,
                               error="Email or password does not match. Try again.")
    return render_template("verify_email_pending.html", pending_email=email, error=None)


@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    User = app_module.User
    db = app_module.db
    read_token = app_module.read_token
    logged_in = app_module.logged_in
    try:
        email = read_token(token, "verify", 86400)
    except (BadSignature, SignatureExpired):
        flash("This verification link is invalid or has expired.", "error")
        return redirect(url_for("auth.login"))
    user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    if user:
        user.email_verified = True
        user.verification_token = None
        db.session.commit()
    flash("Your email has been verified.", "success")
    return redirect(url_for("home" if logged_in() else "login"))
