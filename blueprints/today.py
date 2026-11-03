"""Today dashboard route.

Kept as a separate blueprint with lazy access to the legacy app module while
the monolith is split up. The old `today_page` endpoint is kept as an alias in
app.py so every existing url_for() call continues to work.
"""
import sys
from datetime import date, timedelta

from flask import Blueprint, render_template

today_bp = Blueprint("today", __name__)


@today_bp.route("/today")
def today_page():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    Task = app_module.Task
    Todo = app_module.Todo
    Assessment = app_module.Assessment
    DailyCheckIn = app_module.DailyCheckIn
    QuestDone = app_module.QuestDone
    User = app_module.User
    app_today = app_module.app_today
    parse_homework_date = app_module.parse_homework_date
    assessment_next_action = app_module.assessment_next_action
    get_daily_quests = app_module.get_daily_quests
    pomodoro_count_on = app_module.pomodoro_count_on
    check_streak = app_module.check_streak
    current_lang = app_module.current_lang
    completed_today = app_module.completed_today
    level_info = app_module.level_info
    login_required = app_module.login_required
    current_user_id = app_module.current_user_id
    required = login_required()
    if required:
        return required
    uid = current_user_id()
    today = app_today()

    tasks = Task.query.filter_by(user_id=uid, completed=False, archived=False).all()
    tasks = [t for t in tasks if not getattr(t, "archived", False)]
    overdue = []
    due_today = []
    upcoming_tasks = []
    for task in tasks:
        due = parse_homework_date(task.due_date)
        if due is None:
            continue
        if due < today:
            overdue.append(task)
        elif due == today:
            due_today.append(task)
        elif due <= today + timedelta(days=3):
            upcoming_tasks.append(task)
    overdue.sort(key=lambda t: parse_homework_date(t.due_date) or date.max)
    due_today.sort(key=lambda t: t.title.lower())
    upcoming_tasks.sort(key=lambda t: parse_homework_date(t.due_date) or date.max)

    todos = Todo.query.filter_by(user_id=uid, completed=False, archived=False).filter(Todo.date.isnot(None)).all()
    todos = [t for t in todos if not getattr(t, "archived", False)]
    today_todos = [t for t in todos if parse_homework_date(t.date) == today]
    overdue_todos = [t for t in todos if parse_homework_date(t.date) and parse_homework_date(t.date) < today]

    assessments = Assessment.query.filter_by(user_id=uid, completed=False, archived=False).all()
    assessments = [a for a in assessments if not getattr(a, "archived", False)]
    assessment_rows = []
    for assessment in assessments:
        due = parse_homework_date(assessment.due_date)
        if not due:
            continue
        days = (due - today).days
        if days <= 21:
            assessment_rows.append({"assessment": assessment, "days": days, "action": assessment_next_action(assessment)})
    assessment_rows.sort(key=lambda row: row["days"])

    checkin = DailyCheckIn.query.filter_by(user_id=uid, check_date=today.isoformat()).first()
    quests = get_daily_quests(uid, today)
    pomodoro_today = pomodoro_count_on(uid, today)
    streak = check_streak(uid)

    workload = len(overdue) * 3 + len(due_today) * 2 + len(upcoming_tasks) + sum(1 for row in assessment_rows if row["days"] <= 7) * 3
    if workload == 0:
        suggestion = "Light day. Use 20 minutes for revision or get ahead on one assessment."
    elif workload <= 3:
        suggestion = "A normal day. Do the hardest item first, then take a short break."
    elif workload <= 7:
        suggestion = "A busy day. Pick the top three items and ignore the rest until they are done."
    else:
        suggestion = "A heavy day. Do one 25-minute Pomodoro now and ask for help with the rest."

    greeter = "Welcome to SmartStride"
    weekday_zh = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][today.weekday()]
    today_label = ("%d年%d月%d日 %s" % (today.year, today.month, today.day, weekday_zh)
                   if current_lang() == "zh" else today.strftime("%A %d %B %Y"))

    if current_lang() == "zh":
        greeter = "欢迎使用 SmartStride"
        suggestion = {
            "Light day. Use 20 minutes for revision or get ahead on one assessment.": "今天比较轻松。用 20 分钟复习，或提前做一点考试准备。",
            "A normal day. Do the hardest item first, then take a short break.": "正常的一天。先做最难的一项，然后短暂休息。",
            "A busy day. Pick the top three items and ignore the rest until they are done.": "今天很忙。只挑最重要的三件事，做完再看其他。",
            "A heavy day. Do one 25-minute Pomodoro now and ask for help with the rest.": "今天任务很重。先做一个 25 分钟番茄钟，剩下的事情记得求助。",
        }.get(suggestion, suggestion)

    wins_today = completed_today(uid, today)
    bonus_done = QuestDone.query.filter_by(user_id=uid, quest_date=today.isoformat(), quest_key="bonus").first() is not None
    momentum = min(100, quests["done_count"] * 25 + min(pomodoro_today, 2) * 15 + (15 if checkin else 0) + min(wins_today, 5) * 4)

    return render_template(
        "today.html", today=today, today_label=today_label, greeter=greeter, user=User.query.get(uid), overdue=overdue, due_today=due_today,
        upcoming_tasks=upcoming_tasks, today_todos=today_todos, overdue_todos=overdue_todos,
        assessment_rows=assessment_rows, checkin=checkin, quests=quests,
        pomodoro_today=pomodoro_today, streak=streak, suggestion=suggestion,
        momentum=momentum, wins_today=wins_today, bonus_available=(quests["done_count"] >= 3 and not bonus_done),
        bonus_claimed=bonus_done, xp=level_info(uid),
    )

