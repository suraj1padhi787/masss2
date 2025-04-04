import sqlite3
from config import DB_PATH

# 🔧 Initialize DB (run once at startup)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER,
            session_string TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# 💾 Save new session
def save_session(user_id, session_string):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO sessions (user_id, session_string) VALUES (?, ?)", (user_id, session_string))
    conn.commit()
    conn.close()

# 📥 Get session by user_id
def get_session(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT session_string FROM sessions WHERE user_id = ? ORDER BY created DESC LIMIT 1", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# 📋 Get all sessions
def get_all_sessions():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, session_string FROM sessions")
    rows = c.fetchall()
    conn.close()
    return rows
