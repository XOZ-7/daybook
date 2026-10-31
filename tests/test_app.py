from datetime import date

import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    app.testing = True
    return app.test_client()


def test_pages_load(client):
    for path in ("/", "/tasks", "/planner"):
        assert client.get(path).status_code == 200


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json["status"] == "ok"


def test_task_lifecycle(client):
    client.post("/tasks/add", data={"title": "Write report", "category": "Work", "priority": "High"})
    assert b"Write report" in client.get("/tasks").data
    client.post("/tasks/1/toggle")
    assert b"Write report" in client.get("/tasks?status=done").data
    assert b"Write report" not in client.get("/tasks?status=open").data
    client.post("/tasks/1/update", data={"title": "Write final report", "category": "Study"})
    assert b"Write final report" in client.get("/tasks?category=Study").data
    client.post("/tasks/1/delete")
    assert b"Write final report" not in client.get("/tasks").data


def test_event_shows_on_dashboard_and_planner(client):
    today = date.today().isoformat()
    client.post("/events/add", data={"title": "Team sync", "day": today, "start_time": "14:30"})
    assert b"Team sync" in client.get("/planner").data
    assert b"Team sync" in client.get("/").data  # shared database
    client.post("/events/1/delete")
    assert b"Team sync" not in client.get("/planner").data


def test_task_due_today_appears_on_calendar(client):
    client.post("/tasks/add", data={"title": "Pay rent", "due": date.today().isoformat()})
    assert b"Pay rent" in client.get("/").data


def test_invalid_input_is_sanitised(client):
    client.post("/tasks/add", data={"title": "X", "category": "Bogus", "priority": "Nope", "due": "not-a-date"})
    assert b"Personal" in client.get("/tasks").data
    client.post("/tasks/add", data={"title": "   "})
    assert client.get("/tasks").data.count(b'class="item') == 1


def test_open_redirect_blocked(client):
    r = client.post("/tasks/add", data={"title": "a", "next": "//evil.com"})
    assert r.headers["Location"].endswith("/tasks")
