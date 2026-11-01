from pathlib import Path

path = Path("app.py")
text = path.read_text()

start_marker = "# =========================================================\n# TO-DO\n# ========================================================="
end_marker = "# =========================================================\n# ASSESSMENTS\n# ========================================================="

start = text.find(start_marker)
end = text.find(end_marker, start + len(start_marker))

if start == -1:
    raise SystemExit("ERROR: Could not find the TO-DO section in app.py")

if end == -1:
    raise SystemExit("ERROR: Could not find the ASSESSMENTS section in app.py")

todo_routes = r'''# =========================================================
# TO-DO
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

    due_date = request.form.get(
        "date",
        ""
    ).strip()

    if title:
        todo = Todo(
            user_id=uid,
            title=title,
            date=due_date if due_date else None,
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
            "/todos"
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
'''

new_text = (
    text[:start]
    + todo_routes
    + "\n\n"
    + text[end:]
)

path.write_text(new_text)

print("TO-DO ROUTES REPAIRED")
