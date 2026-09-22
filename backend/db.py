import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "reconciliation.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS location (
            location_id TEXT PRIMARY KEY,
            org_id TEXT NOT NULL,
            location_name TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_location_org ON location(org_id);

        CREATE TABLE IF NOT EXISTS system_a_record (
            record_id TEXT PRIMARY KEY,
            location_id TEXT NOT NULL REFERENCES location(location_id),
            event_date TEXT NOT NULL,
            category_code TEXT NOT NULL,
            actor_id TEXT NOT NULL DEFAULT '',
            base_value TEXT NOT NULL,
            adjustment TEXT NOT NULL,
            total_value TEXT NOT NULL,
            state TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS system_b_entry (
            entry_id TEXT PRIMARY KEY,
            record_ref_raw TEXT NOT NULL,
            record_ref_normalized TEXT NOT NULL,
            location_id TEXT REFERENCES location(location_id),
            recorded_on TEXT,
            value TEXT,
            value_raw TEXT NOT NULL DEFAULT '',
            label TEXT NOT NULL DEFAULT '',
            parse_warnings TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_b_ref_norm
            ON system_b_entry(record_ref_normalized);

        CREATE TABLE IF NOT EXISTS disagreement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            system_a_value TEXT NOT NULL DEFAULT '',
            system_b_value TEXT NOT NULL DEFAULT '',
            location_id TEXT NOT NULL DEFAULT '',
            org_id TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_disagree_org ON disagreement(org_id);
        CREATE INDEX IF NOT EXISTS idx_disagree_org_reason
            ON disagreement(org_id, reason);
    """)

    conn.commit()
    conn.close()


def reset_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        DELETE FROM disagreement;
        DELETE FROM system_b_entry;
        DELETE FROM system_a_record;
        DELETE FROM location;
    """)
    conn.commit()
    conn.close()
