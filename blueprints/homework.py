"""Homework list route.

Small extraction from the legacy app.py monolith. The old `tasks` endpoint is
kept as an alias in app.py so existing links and url_for() calls still work.
"""
import os
import secrets
import sys
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

homework_bp = Blueprint("homework", __name__)


@homework_bp.route("/tasks")
def tasks():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    Task = app_module.Task
    Subject = app_module.Subject
    parse_homework_date = app_module.parse_homework_date
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    all_tasks = Task.query.filter_by(

        user_id=uid,

        completed=False, archived=False

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

        user_id=uid, archived=False

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


@homework_bp.route(
    "/add-task",
    methods=["POST"]
)
def add_task():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    Task = app_module.Task
    db = app_module.db
    normalise_homework_date = app_module.normalise_homework_date
    log_audit = app_module.log_audit
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

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

    log_audit(uid, "create", "task", None, title)

    db.session.commit()


    return redirect(

        request.form.get(
            "redirect_page",
            url_for("tasks")
        )

    )


@homework_bp.route(
    "/task/<int:task_id>"
)
def view_task(task_id):

    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    Task = app_module.Task
    Subject = app_module.Subject
    HomeworkResource = app_module.HomeworkResource
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

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

        user_id=uid, archived=False

    ).order_by(

        Subject.name.asc()

    ).all()


    current_tasks = Task.query.filter_by(

        user_id=uid,

        completed=False, archived=False

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


@homework_bp.route(
    "/edit-task/<int:task_id>",
    methods=["POST"]
)
def edit_task(task_id):
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    Task = app_module.Task
    db = app_module.db
    save_version = app_module.save_version
    log_audit = app_module.log_audit
    normalise_homework_date = app_module.normalise_homework_date
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

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


    save_version(uid, "task", task)

    log_audit(uid, "update", "task", task.id, title)

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


@homework_bp.route(
    "/save-task-notes/<int:task_id>",
    methods=["POST"]
)
def save_task_notes(task_id):
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    Task = app_module.Task
    db = app_module.db
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

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


@homework_bp.route(
    "/complete-task/<int:task_id>",
    methods=["POST"]
)
def complete_task(task_id):
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    Task = app_module.Task
    app = app_module.app
    db = app_module.db
    award_xp = app_module.award_xp
    log_audit = app_module.log_audit
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    task = Task.query.filter_by(

        id=task_id,

        user_id=uid

    ).first_or_404()


    was_completed = bool(task.completed)


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


    if not was_completed:
        award_xp(uid, 10, "Homework completed", commit=False)

    log_audit(uid, "complete", "task", task.id, task.title)

    db.session.commit()


    return redirect(

        request.form.get(

            "redirect_page",

            url_for("task_history")

        )

    )


# Multiple route names are intentionally kept as compatibility aliases so older
# copies of the Homework History page cannot produce a 404 after an update.


@homework_bp.route("/uncomplete-task/<int:task_id>", methods=["POST"])
@homework_bp.route("/incomplete-task/<int:task_id>", methods=["POST"])
@homework_bp.route("/mark-incomplete/<int:task_id>", methods=["POST"])
@homework_bp.route("/mark-as-incomplete/<int:task_id>", methods=["POST"])
def uncomplete_task(task_id):
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    Task = app_module.Task
    db = app_module.db
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

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


@homework_bp.route("/tasks/history")
def task_history():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    Task = app_module.Task
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

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


@homework_bp.route(
    "/delete-task/<int:task_id>",
    methods=["POST"]
)
def delete_task(task_id):
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    Task = app_module.Task
    app = app_module.app
    db = app_module.db
    HomeworkResource = app_module.HomeworkResource
    move_to_trash = app_module.move_to_trash
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

    required = login_required()

    if required:

        return required


    uid = current_user_id()


    task = Task.query.filter_by(

        id=task_id,

        user_id=uid

    ).first_or_404()


    move_to_trash(uid, "task", task, task.title)

    task.archived = True

    task.completed = True

    task.completed_at = task.completed_at or datetime.utcnow()

    db.session.commit()

    flash("Moved to Trash. You can restore it from Data tools → Trash.", "success")

    return redirect(request.form.get("redirect_page", url_for("tasks")))


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


@homework_bp.route(
    "/upload-task-resource/<int:task_id>",
    methods=["POST"]
)
def upload_task_resource(task_id):
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    Task = app_module.Task
    HomeworkResource = app_module.HomeworkResource
    db = app_module.db
    app = app_module.app
    upload_is_allowed = app_module.upload_is_allowed
    upload_extension = app_module.upload_extension
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

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


        if not upload_is_allowed(
            original_filename
        ):

            flash(
                "%s: that file type is not allowed." % original_filename,
                "error"
            )

            continue


        safe_filename = secure_filename(
            original_filename
        )


        extension = upload_extension(
            original_filename
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


@homework_bp.route(
    "/download-task-resource/<int:resource_id>"
)
def download_task_resource(resource_id):
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    HomeworkResource = app_module.HomeworkResource
    app = app_module.app
    upload_extension = app_module.upload_extension
    INLINE_IMAGE_EXTENSIONS = app_module.INLINE_IMAGE_EXTENSIONS
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

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

        as_attachment=(
            upload_extension(resource.filename)
            not in INLINE_IMAGE_EXTENSIONS
        ),

        download_name=(
            resource.original_filename
            or resource.filename
        )

    )


@homework_bp.route(
    "/download-finished-task/<int:task_id>"
)
def download_finished_task(task_id):
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    Task = app_module.Task
    app = app_module.app
    abort = app_module.abort
    upload_extension = app_module.upload_extension
    INLINE_IMAGE_EXTENSIONS = app_module.INLINE_IMAGE_EXTENSIONS
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

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

        as_attachment=(
            upload_extension(task.finished_file)
            not in INLINE_IMAGE_EXTENSIONS
        ),

        download_name=task.finished_file

    )


@homework_bp.route(
    "/delete-task-resource/<int:resource_id>",
    methods=["POST"]
)
def delete_task_resource(resource_id):
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    HomeworkResource = app_module.HomeworkResource
    db = app_module.db
    app = app_module.app
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id

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
