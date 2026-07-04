"""
SQLite3 backend — drop-in replacement for the former Supabase client.
Keeps the same public function names so no route code needs to change.
Database file: artificial_education.db (override with DB_PATH env var).
"""
import os, sqlite3, hashlib, secrets, uuid
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "artificial_education.db"))


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    conn = _conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id            TEXT PRIMARY KEY,
        email         TEXT UNIQUE NOT NULL,
        name          TEXT,
        password_hash TEXT NOT NULL,
        salt          TEXT NOT NULL,
        created_at    TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS profiles (
        id                 TEXT PRIMARY KEY,
        plan               TEXT DEFAULT 'free',
        credits_minutes    REAL DEFAULT 0,
        stripe_customer_id TEXT,
        created_at         TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS course_assignments (
        user_id     TEXT NOT NULL,
        build_id    TEXT NOT NULL,
        assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, build_id)
    );
    """)
    conn.commit()
    conn.close()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()


def create_user(email: str, password: str, name: str):
    init_db()
    conn = _conn()
    try:
        if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            return None, "An account with this email already exists"
        uid = str(uuid.uuid4())
        salt = secrets.token_hex(16)
        pw_hash = _hash_password(password, salt)
        conn.execute("INSERT INTO users (id, email, name, password_hash, salt) VALUES (?,?,?,?,?)",
                     (uid, email, name, pw_hash, salt))
        conn.execute("INSERT INTO profiles (id, plan, credits_minutes) VALUES (?, 'free', 0)", (uid,))
        conn.commit()
        return {"id": uid, "email": email, "name": name}, None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()


def verify_user(email: str, password: str):
    init_db()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or _hash_password(password, row["salt"]) != row["password_hash"]:
            return None, "Invalid email or password"
        return {"id": row["id"], "email": row["email"], "name": row["name"]}, None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()


def get_profile(user_id):
    init_db()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (user_id,)).fetchone()
        if row:
            return dict(row)
        conn.execute("INSERT INTO profiles (id, plan, credits_minutes) VALUES (?, 'free', 0)", (user_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def update_profile(user_id, fields: dict):
    init_db()
    conn = _conn()
    try:
        get_profile(user_id)
        cols = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [user_id]
        conn.execute(f"UPDATE profiles SET {cols} WHERE id = ?", vals)
        conn.commit()
        return True
    except Exception as e:
        print(f"update_profile ERROR for {user_id}: {e}")
        return False
    finally:
        conn.close()


def get_assigned_build_ids(user_id):
    init_db()
    conn = _conn()
    try:
        rows = conn.execute("SELECT build_id FROM course_assignments WHERE user_id = ?", (user_id,)).fetchall()
        return {r["build_id"] for r in rows}
    except Exception:
        return set()
    finally:
        conn.close()


def assign_course(user_id, build_id):
    init_db()
    conn = _conn()
    try:
        conn.execute("INSERT OR IGNORE INTO course_assignments (user_id, build_id) VALUES (?, ?)",
                     (user_id, build_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"assign_course ERROR: {e}")
        return False
    finally:
        conn.close()


def unassign_course(user_id, build_id):
    init_db()
    conn = _conn()
    try:
        conn.execute("DELETE FROM course_assignments WHERE user_id = ? AND build_id = ?", (user_id, build_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"unassign_course ERROR: {e}")
        return False
    finally:
        conn.close()


def list_all_assignments():
    init_db()
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM course_assignments ORDER BY assigned_at DESC").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_supabase():
    return None

def get_supabase_admin():
    return None


# ── Account deletion, settings, user listing (SQLite) ─────────────────────────

def delete_user(user_id):
    init_db()
    conn = _conn()
    try:
        conn.execute("DELETE FROM profiles WHERE id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.execute("DELETE FROM course_assignments WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"delete_user ERROR: {e}")
        return False
    finally:
        conn.close()


def set_setting(key, value):
    init_db()
    conn = _conn()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))
        conn.commit()
        return True
    except Exception as e:
        print(f"set_setting ERROR: {e}")
        return False
    finally:
        conn.close()


def get_setting(key, default=None):
    init_db()
    conn = _conn()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    except Exception:
        return default
    finally:
        conn.close()


def list_all_users():
    """Returns joined user+profile rows for the admin dashboard."""
    init_db()
    conn = _conn()
    try:
        rows = conn.execute("""
            SELECT u.id, u.email, u.name, u.created_at,
                   p.plan, p.credits_minutes, p.stripe_customer_id
            FROM users u LEFT JOIN profiles p ON p.id = u.id
            ORDER BY u.created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()
