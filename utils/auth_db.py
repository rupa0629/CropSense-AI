import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

DB_NAME = "cropsense.db"


class ClosingConnection(sqlite3.Connection):
    """Commit/rollback like sqlite3.Connection, then always release the handle."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def _db_path() -> Path:
    base_dir = Path(__file__).resolve().parent.parent

    from config.settings import get_settings

    database_url = get_settings().database_url

    if database_url.startswith("sqlite:///"):
        raw_path = database_url.removeprefix("sqlite:///")
        path = Path(raw_path) if raw_path.startswith("/") else base_dir / raw_path
    else:
        raise ValueError(
            "Unsupported DATABASE_URL. CropSense currently supports sqlite:/// URLs only."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), timeout=30, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _hash_password(password: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return raw.hex()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'farmer',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (1)"
        )

        # Backfill older DBs that were created before role column existed.
        try:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'farmer'")
        except sqlite3.OperationalError:
            pass

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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revoked_at TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TIMESTAMP NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_at TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                is_correct INTEGER NOT NULL,
                corrected_disease TEXT,
                notes TEXT,
                review_status TEXT NOT NULL DEFAULT 'pending',
                reviewed_by INTEGER,
                reviewed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(analysis_id, user_id),
                FOREIGN KEY(analysis_id) REFERENCES analysis_logs(id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(reviewed_by) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agronomist_review_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                crop_stage TEXT,
                symptom_notes TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewer_notes TEXT,
                reviewed_by INTEGER,
                reviewed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(analysis_id) REFERENCES analysis_logs(id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(reviewed_by) REFERENCES users(id)
            )
            """
        )


def create_user(full_name: str, email: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"|,.<>/?]", password):
        return False, "Password must contain at least one special character."

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)

    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (full_name, email, password_hash, salt, role) VALUES (?, ?, ?, ?, ?)",
                (full_name.strip(), email, password_hash, salt, "farmer"),
            )
            user_id = cur.lastrowid
            conn.execute(
                "INSERT OR REPLACE INTO user_settings (user_id, weather_api_key, default_location) VALUES (?, ?, ?)",
                (user_id, "", "Delhi,IN"),
            )

            # Promote first account to admin for easy initial setup.
            total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
            if int(total_users) == 1:
                conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))

        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "This email is already registered."


def authenticate_user(email: str, password: str) -> Optional[dict]:
    email = email.strip().lower()
    with get_conn() as conn:
        user = conn.execute(
            "SELECT id, full_name, email, password_hash, salt, role FROM users WHERE email = ?",
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
        "role": user["role"],
    }


def get_user_by_id(user_id: int) -> Optional[dict]:
    with get_conn() as conn:
        user = conn.execute(
            "SELECT id, full_name, email, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not user:
        return None
    return {"id": user["id"], "full_name": user["full_name"], "email": user["email"], "role": user["role"]}


def get_user_by_email(email: str) -> Optional[dict]:
    with get_conn() as conn:
        user = conn.execute(
            "SELECT id, full_name, email, role FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    if not user:
        return None
    return {"id": user["id"], "full_name": user["full_name"], "email": user["email"], "role": user["role"]}


def update_user_password(user_id: int, new_password: str) -> tuple[bool, str]:
    if len(new_password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r"[A-Z]", new_password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", new_password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", new_password):
        return False, "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", new_password):
        return False, "Password must contain at least one special character."

    salt = secrets.token_hex(16)
    pwh = _hash_password(new_password, salt)
    with get_conn() as conn:
        conn.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (pwh, salt, user_id))
    return True, "Password updated."


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(user_id: int, raw_token: str, expires_minutes: int = 60 * 24 * 14) -> None:
    exp = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at, revoked) VALUES (?, ?, ?, 0)",
            (user_id, _hash_token(raw_token), exp.isoformat()),
        )


def validate_refresh_token(raw_token: str) -> Optional[dict]:
    th = _hash_token(raw_token)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, user_id, expires_at, revoked FROM refresh_tokens WHERE token_hash = ?",
            (th,),
        ).fetchone()
    if not row:
        return None
    if int(row["revoked"]) == 1:
        return None
    exp = datetime.fromisoformat(row["expires_at"])
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) >= exp:
        return None
    return {"id": row["id"], "user_id": row["user_id"]}


def revoke_refresh_token(raw_token: str) -> None:
    th = _hash_token(raw_token)
    with get_conn() as conn:
        conn.execute(
            "UPDATE refresh_tokens SET revoked = 1, revoked_at = CURRENT_TIMESTAMP WHERE token_hash = ?",
            (th,),
        )


def revoke_all_refresh_tokens_for_user(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE refresh_tokens SET revoked = 1, revoked_at = CURRENT_TIMESTAMP WHERE user_id = ? AND revoked = 0",
            (user_id,),
        )


def create_password_reset_token(user_id: int, raw_token: str, expires_minutes: int = 30) -> None:
    exp = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, used) VALUES (?, ?, ?, 0)",
            (user_id, _hash_token(raw_token), exp.isoformat()),
        )


def validate_password_reset_token(raw_token: str) -> Optional[dict]:
    th = _hash_token(raw_token)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, user_id, expires_at, used FROM password_reset_tokens WHERE token_hash = ?",
            (th,),
        ).fetchone()
    if not row:
        return None
    if int(row["used"]) == 1:
        return None
    exp = datetime.fromisoformat(row["expires_at"])
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) >= exp:
        return None
    return {"id": row["id"], "user_id": row["user_id"]}


def mark_password_reset_token_used(raw_token: str) -> None:
    th = _hash_token(raw_token)
    with get_conn() as conn:
        conn.execute(
            "UPDATE password_reset_tokens SET used = 1, used_at = CURRENT_TIMESTAMP WHERE token_hash = ?",
            (th,),
        )


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
        row = conn.execute("SELECT weather_api_key, default_location FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return {"weather_api_key": "", "default_location": "Delhi,IN"}
    return {"weather_api_key": row["weather_api_key"] or "", "default_location": row["default_location"] or "Delhi,IN"}


def save_analysis_log(user_id: int, image_name: str, disease: str, confidence: float, severity: str, immediate_action: str) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO analysis_logs (user_id, image_name, disease, confidence, severity, immediate_action) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, image_name, disease, confidence, severity, immediate_action),
        )
        return int(cursor.lastrowid)


def save_prediction_feedback(
    analysis_id: int,
    user_id: int,
    is_correct: bool,
    corrected_disease: str | None,
    notes: str | None,
) -> bool:
    with get_conn() as conn:
        owner = conn.execute(
            "SELECT 1 FROM analysis_logs WHERE id = ? AND user_id = ?",
            (analysis_id, user_id),
        ).fetchone()
        if not owner:
            return False
        conn.execute(
            """
            INSERT INTO prediction_feedback
                (analysis_id, user_id, is_correct, corrected_disease, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(analysis_id, user_id) DO UPDATE SET
                is_correct = excluded.is_correct,
                corrected_disease = excluded.corrected_disease,
                notes = excluded.notes,
                review_status = 'pending',
                reviewed_by = NULL,
                reviewed_at = NULL
            """,
            (
                analysis_id,
                user_id,
                int(is_correct),
                corrected_disease.strip() if corrected_disease else None,
                notes.strip() if notes else None,
            ),
        )
    return True


def enqueue_agronomist_review(
    analysis_id: int,
    user_id: int,
    reason: str,
    crop_stage: str | None,
    symptom_notes: str | None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO agronomist_review_queue
                (analysis_id, user_id, reason, crop_stage, symptom_notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(analysis_id) DO UPDATE SET
                reason = excluded.reason,
                crop_stage = excluded.crop_stage,
                symptom_notes = excluded.symptom_notes,
                status = 'pending',
                reviewer_notes = NULL,
                reviewed_by = NULL,
                reviewed_at = NULL
            """,
            (analysis_id, user_id, reason, crop_stage, symptom_notes),
        )


def save_weather_log(user_id: int, location: str, temperature: float, humidity: float, wind_speed: float, description: str, source: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO weather_logs (user_id, location, temperature, humidity, wind_speed, description, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, location, temperature, humidity, wind_speed, description, source),
        )


def save_chat_log(user_id: int, role: str, message: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT INTO chat_logs (user_id, role, message) VALUES (?, ?, ?)", (user_id, role, message))


def get_recent_analysis(user_id: int, limit: int = 5) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT image_name, disease, confidence, severity, created_at FROM analysis_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [{"image_name": r["image_name"], "disease": r["disease"], "confidence": r["confidence"], "severity": r["severity"], "created_at": r["created_at"]} for r in rows]


def get_analysis_timeline(user_id: int, limit: int = 30) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT created_at, confidence FROM analysis_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [{"created_at": r["created_at"], "confidence": float(r["confidence"])} for r in reversed(rows)]


def get_disease_distribution(user_id: int, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT disease, COUNT(*) AS count
            FROM (
              SELECT disease FROM analysis_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?
            )
            GROUP BY disease
            ORDER BY count DESC
            """,
            (user_id, limit),
        ).fetchall()
    return [{"disease": r["disease"], "count": int(r["count"])} for r in rows]


def get_dashboard_counts(user_id: int) -> dict:
    with get_conn() as conn:
        total_analysis = conn.execute("SELECT COUNT(*) AS c FROM analysis_logs WHERE user_id = ?", (user_id,)).fetchone()["c"]
        total_weather = conn.execute("SELECT COUNT(*) AS c FROM weather_logs WHERE user_id = ?", (user_id,)).fetchone()["c"]
        total_chat = conn.execute("SELECT COUNT(*) AS c FROM chat_logs WHERE user_id = ?", (user_id,)).fetchone()["c"]
    return {"analysis_count": int(total_analysis), "weather_count": int(total_weather), "chat_count": int(total_chat)}


def get_admin_overview() -> dict:
    with get_conn() as conn:
        users = int(conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"])
        analyses = int(conn.execute("SELECT COUNT(*) AS c FROM analysis_logs").fetchone()["c"])
        weather = int(conn.execute("SELECT COUNT(*) AS c FROM weather_logs").fetchone()["c"])
        chats = int(conn.execute("SELECT COUNT(*) AS c FROM chat_logs").fetchone()["c"])
        top_diseases = conn.execute(
            "SELECT disease, COUNT(*) AS count FROM analysis_logs GROUP BY disease ORDER BY count DESC LIMIT 6"
        ).fetchall()

    return {
        "users": users,
        "analyses": analyses,
        "weather_checks": weather,
        "chat_messages": chats,
        "top_diseases": [{"disease": r["disease"], "count": int(r["count"])} for r in top_diseases],
    }


def list_users(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, full_name, email, role, created_at FROM users ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {"id": r["id"], "full_name": r["full_name"], "email": r["email"], "role": r["role"], "created_at": r["created_at"]}
        for r in rows
    ]

