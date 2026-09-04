"""
database.py

Simple SQLite storage matching the ActivityData table described in
the project report's database schema. No external DB server needed --
SQLite stores everything in a single local file (carbon_tracker.db).
"""

import sqlite3
from datetime import datetime

DB_PATH = "carbon_tracker.db"


def init_db(db_path: str = DB_PATH) -> None:
    """Create the ActivityData table if it doesn't already exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ActivityData (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            electricity_units REAL NOT NULL,
            carbon_emission REAL NOT NULL,
            eco_score INTEGER NOT NULL,
            recommendation TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_record(
    user_name: str,
    electricity_units: float,
    carbon_emission_kg: float,
    eco_score: int,
    recommendation: str,
    db_path: str = DB_PATH,
) -> int:
    """Insert one activity record. Returns the new row's id."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO ActivityData
            (user_name, electricity_units, carbon_emission, eco_score, recommendation, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_name,
            electricity_units,
            carbon_emission_kg,
            eco_score,
            recommendation,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_all_records(db_path: str = DB_PATH):
    """Return all saved records, most recent first."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_name, electricity_units, carbon_emission, eco_score, recommendation, created_at "
        "FROM ActivityData ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_records_for_user(user_name: str, db_path: str = DB_PATH):
    """Return all records for one user, most recent first -- used for
    month-over-month comparison and streak calculation."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_name, electricity_units, carbon_emission, eco_score, recommendation, created_at "
        "FROM ActivityData WHERE user_name = ? ORDER BY created_at DESC",
        (user_name,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_leaderboard(db_path: str = DB_PATH, limit: int = 10):
    """
    Return each user's average eco-score and total points, ranked best
    first. Points are simply the sum of eco-scores across all of that
    user's entries -- a simple, transparent scoring model (more entries
    with better scores earns more points), inspired by gamification
    approaches in similar public carbon-tracking projects.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT user_name,
               ROUND(AVG(eco_score), 1) AS avg_score,
               SUM(eco_score) AS total_points,
               COUNT(*) AS entry_count
        FROM ActivityData
        GROUP BY user_name
        ORDER BY total_points DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    # Quick manual test: python database.py
    init_db()
    save_record("Test User", 120, 98.4, 75, "Reduce usage during peak hours.")
    for row in get_all_records():
        print(row)
