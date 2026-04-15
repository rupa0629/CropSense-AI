import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path
from typing import Optional

DB_NAME = "cropsense.db"


def _db_path() -> Path:
    base_dir = Path(__file__).resolve().parent.parent
    return base_dir / DB_NAME


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                weather_api_key TEXT,
                default_location TEXT DEFAULT 'Delhi,IN',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                image_name TEXT,
                disease TEXT,
                confidence REAL,
                severity TEXT,
                immediate_action TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weather_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                location TEXT,
                temperature REAL,
                humidity REAL,
                wind_speed REAL,
                description TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )


def _hash_password(password: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return raw.hex()


def create_user(full_name: str, email: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)

    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (full_name, email, password_hash, salt) VALUES (?, ?, ?, ?)",
                (full_name.strip(), email, password_hash, salt),
            )
            user_id = cur.lastrowid
            conn.execute(
                "INSERT OR REPLACE INTO user_settings (user_id, weather_api_key, default_location) VALUES (?, ?, ?)",
                (user_id, "", "Delhi,IN"),
            )
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "This email is already registered."


def authenticate_user(email: str, password: str) -> Optional[dict]:
    email = email.strip().lower()
    with get_conn() as conn:
        user = conn.execute(
            "SELECT id, full_name, email, password_hash, salt FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if not user:
        return None

    candidate_hash = _hash_password(password, user["salt"])
    if not hmac.compare_digest(candidate_hash, user["password_hash"]):
        return None

    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
    }


def save_user_settings(user_id: int, location: str, weather_api_key: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_settings (user_id, weather_api_key, default_location, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                weather_api_key = excluded.weather_api_key,
                default_location = excluded.default_location,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, weather_api_key.strip(), location.strip() or "Delhi,IN"),
        )


def get_user_settings(user_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT weather_api_key, default_location FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return {"weather_api_key": "", "default_location": "Delhi,IN"}
    return {
        "weather_api_key": row["weather_api_key"] or "",
        "default_location": row["default_location"] or "Delhi,IN",
    }


def save_analysis_log(
    user_id: int,
    image_name: str,
    disease: str,
    confidence: float,
    severity: str,
    immediate_action: str,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO analysis_logs (user_id, image_name, disease, confidence, severity, immediate_action)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, image_name, disease, confidence, severity, immediate_action),
        )


def save_weather_log(
    user_id: int,
    location: str,
    temperature: float,
    humidity: float,
    wind_speed: float,
    description: str,
    source: str,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO weather_logs (user_id, location, temperature, humidity, wind_speed, description, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, location, temperature, humidity, wind_speed, description, source),
        )


def save_chat_log(user_id: int, role: str, message: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_logs (user_id, role, message) VALUES (?, ?, ?)",
            (user_id, role, message),
        )


def get_recent_analysis(user_id: int, limit: int = 5) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT image_name, disease, confidence, severity, created_at
            FROM analysis_logs
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

    return [
        {
            "image_name": r["image_name"],
            "disease": r["disease"],
            "confidence": r["confidence"],
            "severity": r["severity"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
