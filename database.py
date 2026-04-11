import sqlite3
from datetime import datetime
from typing import Optional


def init_db(db_path: str = "meytapp.db") -> None:
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shootings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            shooter TEXT NOT NULL,
            discipline TEXT NOT NULL,
            total_score INTEGER NOT NULL,
            series TEXT NOT NULL,
            url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_shooting(
    user_id: str,
    date: str,
    shooter: str,
    discipline: str,
    total_score: int,
    series: str,
    url: Optional[str] = None,
    db_path: str = "meytapp.db"
) -> None:
    """Save a shooting result to the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO shootings (user_id, date, shooter, discipline, total_score, series, url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, date, shooter, discipline, total_score, series, url))
    conn.commit()
    conn.close()


def get_all_shootings(
    user_id: Optional[str] = None,
    db_path: str = "meytapp.db"
) -> list:
    """Retrieve shooting records for a specific user (or all if user_id is None)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    if user_id:
        cursor.execute("""
            SELECT id, user_id, date, shooter, discipline, total_score, series, url, created_at
            FROM shootings
            WHERE user_id = ?
            ORDER BY date DESC
        """, (user_id,))
    else:
        cursor.execute("""
            SELECT id, user_id, date, shooter, discipline, total_score, series, url, created_at
            FROM shootings
            ORDER BY date DESC
        """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def delete_shooting(shooting_id: int, user_id: str, db_path: str = "meytapp.db") -> None:
    """Delete a shooting record by ID, only if it belongs to the user."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM shootings WHERE id = ? AND user_id = ?",
        (shooting_id, user_id)
    )
    conn.commit()
    conn.close()
