import os
import sqlite3
import tempfile
import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.db import init_db, get_connection
import backend.db as db_module


@pytest.fixture
def test_db(tmp_path):
    """Provide a fresh SQLite database for each test."""
    db_path = str(tmp_path / "test.db")
    original = db_module.DB_PATH
    db_module.DB_PATH = db_path
    init_db()
    yield db_path
    db_module.DB_PATH = original


@pytest.fixture
def conn(test_db):
    """Provide a database connection to the test database."""
    connection = get_connection()
    yield connection
    connection.close()


@pytest.fixture
def seed_locations(conn):
    """Insert the standard location set."""
    conn.executemany(
        "INSERT INTO location (location_id, org_id, location_name) VALUES (?, ?, ?)",
        [
            ("LOC-101", "ORG-A", "Location 101"),
            ("LOC-102", "ORG-A", "Location 102"),
            ("LOC-103", "ORG-A", "Location 103"),
            ("LOC-201", "ORG-B", "Location 201"),
            ("LOC-202", "ORG-B", "Location 202"),
        ],
    )
    conn.commit()


def insert_system_a(conn, record_id, location_id="LOC-101", event_date="2026-03-15",
                     category_code="CAT-01", actor_id="USR-11", base_value="100.00",
                     adjustment="10.00", total_value="110.00", state="CONFIRMED"):
    conn.execute(
        """INSERT INTO system_a_record
           (record_id, location_id, event_date, category_code, actor_id,
            base_value, adjustment, total_value, state)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (record_id, location_id, event_date, category_code, actor_id,
         base_value, adjustment, total_value, state),
    )


def insert_system_b(conn, entry_id, record_ref_normalized, location_id="LOC-101",
                     recorded_on="2026-03-15", value="110.00", value_raw="110.00",
                     label="Entry for CAT-01", record_ref_raw=None, parse_warnings=""):
    if record_ref_raw is None:
        record_ref_raw = record_ref_normalized
    conn.execute(
        """INSERT INTO system_b_entry
           (entry_id, record_ref_raw, record_ref_normalized, location_id,
            recorded_on, value, value_raw, label, parse_warnings)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (entry_id, record_ref_raw, record_ref_normalized, location_id,
         recorded_on, value, value_raw, label, parse_warnings),
    )
