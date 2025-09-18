import os
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient


def make_temp_db(tmp_path):
    db_path = tmp_path / "gum_test.db"
    with closing(sqlite3.connect(db_path)) as conn:
        cur = conn.cursor()
        cur.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE propositions (
                id INTEGER PRIMARY KEY,
                text TEXT NOT NULL,
                reasoning TEXT NOT NULL,
                confidence INTEGER,
                decay INTEGER,
                created_at TEXT,
                updated_at TEXT,
                revision_group TEXT,
                version INTEGER
            );
            CREATE TABLE observation_proposition (
                observation_id INTEGER,
                proposition_id INTEGER
            );

            INSERT INTO propositions (id, text, reasoning, confidence, decay, created_at, updated_at, revision_group, version)
            VALUES
                (1, 'low conf prop', 'r', 3, 5, '2024-01-01', '2024-01-01', 'rg1', 1),
                (2, 'mid conf prop', 'r', 6, 5, '2024-01-01', '2024-01-01', 'rg2', 1),
                (3, 'high conf prop', 'r', 9, 5, '2024-01-01', '2024-01-01', 'rg3', 1);

            INSERT INTO observation_proposition (observation_id, proposition_id) VALUES
                (10, 2), (11, 2);
            """
        )
        conn.commit()
    return str(db_path)


class FakeAttention:
    def __init__(self, focus_level=0.5, app="terminal", idle=0.0):
        self.focus_level = focus_level
        self.active_application = app
        self.idle_time_seconds = idle


class FakeAttentionMonitor:
    def __init__(self):
        self._state = FakeAttention()

    def start_monitoring(self):
        pass

    def stop_monitoring(self):
        pass

    def get_current_attention(self):
        return self._state


class FakeEngine:
    def __init__(self):
        self.calls = []

    def make_decision(self, context):
        # Deterministic decision purely from confidence to make assertions easy
        c = (context.proposition.confidence or 5)
        if c <= 5:
            decision = "no_action"
        elif c <= 8:
            decision = "dialogue"
        else:
            decision = "autonomous_action"
        metadata = {
            "confidence": c,
            "attention_level": context.user_attention_level,
            "active_app": context.active_application,
            "expected_utilities": {
                "no_action": 0.1,
                "dialogue": 0.2,
                "autonomous_action": 0.3,
            },
            "utilities_used": {
                "u_dialogue_goal_false": -0.15,
            },
        }
        self.calls.append(context)
        return decision, metadata


@pytest.fixture
def client_with_fakes(tmp_path, monkeypatch):
    # Build temp DB and point API to it
    db_path = make_temp_db(tmp_path)
    monkeypatch.setenv("GUM_DB_PATH", db_path)

    # Import after env is set
    from dashboard.simple_api import app
    import dashboard.simple_api as mod

    # Disable startup/shutdown hooks to avoid real engine/monitor
    app.router.on_startup.clear()
    app.router.on_shutdown.clear()

    # Inject fakes
    mod._ENGINE = FakeEngine()
    mod._ATTN = FakeAttentionMonitor()

    with TestClient(app) as client:
        yield client


def test_decisions_reflect_confidence(client_with_fakes):
    client = client_with_fakes
    r = client.get("/api/propositions?limit=50")
    assert r.status_code == 200, r.text
    data = r.json()
    props = {p["id"]: p for p in data["propositions"]}

    assert props[1]["mixed_initiative_score"]["decision"] == "no_action"
    assert props[2]["mixed_initiative_score"]["decision"] == "dialogue"
    assert props[3]["mixed_initiative_score"]["decision"] == "autonomous_action"

    # observation_count for id=2 should be 2
    assert props[2]["observation_count"] == 2


def test_500_when_engine_missing(tmp_path, monkeypatch):
    db_path = make_temp_db(tmp_path)
    monkeypatch.setenv("GUM_DB_PATH", db_path)

    from dashboard.simple_api import app
    import dashboard.simple_api as mod

    app.router.on_startup.clear()
    app.router.on_shutdown.clear()

    mod._ENGINE = None
    mod._ATTN = FakeAttentionMonitor()

    with TestClient(app) as client:
        r = client.get("/api/propositions?limit=10")
        assert r.status_code == 500
        assert "not initialized" in r.text or "Decision engine error" in r.text


