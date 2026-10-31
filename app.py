import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

CATEGORIES = ["Work", "Study", "Personal", "Health"]
PRIORITIES = ["High", "Medium", "Low"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'Personal', priority TEXT NOT NULL DEFAULT 'Medium',
  due TEXT, done INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, day TEXT NOT NULL,
  start_time TEXT NOT NULL DEFAULT '09:00', end_time TEXT NOT NULL DEFAULT '10:00',
  category TEXT NOT NULL DEFAULT 'Personal', note TEXT DEFAULT '');
"""


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or os.environ.get("DB_PATH", "daybook.db")
    version = os.environ.get("APP_VERSION", "dev")

    # ---------- helpers ----------
    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB_PATH"])
            g.db.row_factory = sqlite3.Row
        return g.db

    def q(sql, args=()):
        return db().execute(sql, args).fetchall()

    def one(sql, args=()):
        return db().execute(sql, args).fetchone()[0]

    def run(sql, args=()):
        db().execute(sql, args)
        db().commit()

    def clean(value, allowed, default):
        return value if value in allowed else default

    def vdate(value, default=None):
        try:
            return date.fromisoformat(value).isoformat()
        except (ValueError, TypeError):
            return default

    def vtime(value, default):
        try:
            return datetime.strptime(value, "%H:%M").strftime("%H:%M")
        except (ValueError, TypeError):
            return default

    def back(default):
        nxt = request.form.get("next", "")
        ok = nxt.startswith("/") and not nxt.startswith("//")
        return redirect(nxt if ok else default)

    @app.teardown_appcontext
    def close_db(_):
        conn = g.pop("db", None)
        if conn:
            conn.close()

    @app.context_processor
    def inject():
        return {"categories": CATEGORIES, "priorities": PRIORITIES, "version": version}

    with app.app_context():
        db().executescript(SCHEMA)

    # ---------- pages ----------
    @app.get("/")
    def index():
        w = request.args.get("w", 0, type=int)
        today = date.today()
        monday = today - timedelta(days=today.weekday()) + timedelta(weeks=w)
        days = []
        for i in range(7):
            d = monday + timedelta(days=i)
            iso = d.isoformat()
            days.append({
                "date": d, "iso": iso,
                "events": q("SELECT * FROM events WHERE day=? ORDER BY start_time", (iso,)),
                "tasks": q("SELECT * FROM tasks WHERE due=? AND done=0", (iso,)),
            })
        t = today.isoformat()
        return render_template(
            "index.html", w=w, days=days, today=today, today_iso=t,
            agenda=q("SELECT * FROM events WHERE day=? ORDER BY start_time", (t,)),
            due_today=q("SELECT * FROM tasks WHERE due=? AND done=0", (t,)),
            upcoming=q("SELECT * FROM events WHERE day>? ORDER BY day, start_time LIMIT 5", (t,)),
            stats={
                "open": one("SELECT COUNT(*) FROM tasks WHERE done=0"),
                "done": one("SELECT COUNT(*) FROM tasks WHERE done=1"),
                "overdue": one("SELECT COUNT(*) FROM tasks WHERE done=0 AND due<?", (t,)),
            },
        )

    @app.get("/tasks")
    def tasks():
        cat = request.args.get("category", "")
        status = request.args.get("status", "all")
        sql, args = "SELECT * FROM tasks WHERE 1=1", []
        if cat in CATEGORIES:
            sql += " AND category=?"
            args.append(cat)
        if status == "open":
            sql += " AND done=0"
        elif status == "done":
            sql += " AND done=1"
        sql += (" ORDER BY done, CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END,"
                " COALESCE(due,'9999')")
        edit_id = request.args.get("edit", type=int)
        edit = q("SELECT * FROM tasks WHERE id=?", (edit_id,)) if edit_id else []
        return render_template("tasks.html", items=q(sql, args), cat=cat, status=status,
                               edit=edit[0] if edit else None)

    @app.get("/planner")
    def planner():
        t = date.today().isoformat()
        edit_id = request.args.get("edit", type=int)
        edit = q("SELECT * FROM events WHERE id=?", (edit_id,)) if edit_id else []
        return render_template(
            "planner.html", today_iso=t, edit=edit[0] if edit else None,
            upcoming=q("SELECT * FROM events WHERE day>=? ORDER BY day, start_time", (t,)),
            past=q("SELECT * FROM events WHERE day<? ORDER BY day DESC LIMIT 10", (t,)),
        )

    # ---------- task actions ----------
    def task_values():
        return (
            request.form.get("title", "").strip()[:120],
            clean(request.form.get("category"), CATEGORIES, "Personal"),
            clean(request.form.get("priority"), PRIORITIES, "Medium"),
            vdate(request.form.get("due", "")),
        )

    @app.post("/tasks/add")
    def task_add():
        v = task_values()
        if v[0]:
            run("INSERT INTO tasks(title,category,priority,due) VALUES(?,?,?,?)", v)
        return back(url_for("tasks"))

    @app.post("/tasks/<int:tid>/update")
    def task_update(tid):
        v = task_values()
        if v[0]:
            run("UPDATE tasks SET title=?, category=?, priority=?, due=? WHERE id=?", (*v, tid))
        return back(url_for("tasks"))

    @app.post("/tasks/<int:tid>/toggle")
    def task_toggle(tid):
        run("UPDATE tasks SET done = 1 - done WHERE id=?", (tid,))
        return back(url_for("tasks"))

    @app.post("/tasks/<int:tid>/delete")
    def task_delete(tid):
        run("DELETE FROM tasks WHERE id=?", (tid,))
        return back(url_for("tasks"))

    # ---------- event actions ----------
    def event_values():
        return (
            request.form.get("title", "").strip()[:120],
            vdate(request.form.get("day", ""), date.today().isoformat()),
            vtime(request.form.get("start_time"), "09:00"),
            vtime(request.form.get("end_time"), "10:00"),
            clean(request.form.get("category"), CATEGORIES, "Personal"),
            request.form.get("note", "").strip()[:300],
        )

    @app.post("/events/add")
    def event_add():
        v = event_values()
        if v[0]:
            run("INSERT INTO events(title,day,start_time,end_time,category,note) VALUES(?,?,?,?,?,?)", v)
        return back(url_for("planner"))

    @app.post("/events/<int:eid>/update")
    def event_update(eid):
        v = event_values()
        if v[0]:
            run("UPDATE events SET title=?, day=?, start_time=?, end_time=?, category=?, note=? WHERE id=?",
                (*v, eid))
        return back(url_for("planner"))

    @app.post("/events/<int:eid>/delete")
    def event_delete(eid):
        run("DELETE FROM events WHERE id=?", (eid,))
        return back(url_for("planner"))

    # ---------- ops ----------
    @app.get("/health")
    def health():
        one("SELECT 1")
        return jsonify(status="ok", version=version)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
