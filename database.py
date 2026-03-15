import sqlite3

conn = sqlite3.connect("candidates.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS candidates(
id INTEGER PRIMARY KEY AUTOINCREMENT,
skills TEXT,
matched TEXT,
score INTEGER,
status TEXT,
resume_path TEXT,
email TEXT,
rating INTEGER
)
""")

conn.commit()

# Lightweight migration for older databases without resume_path
cursor.execute("PRAGMA table_info(candidates)")
cols = [row[1] for row in cursor.fetchall()]
if "resume_path" not in cols:
    cursor.execute("ALTER TABLE candidates ADD COLUMN resume_path TEXT")
    conn.commit()
if "email" not in cols:
    cursor.execute("ALTER TABLE candidates ADD COLUMN email TEXT")
    conn.commit()
if "rating" not in cols:
    cursor.execute("ALTER TABLE candidates ADD COLUMN rating INTEGER")
    conn.commit()
