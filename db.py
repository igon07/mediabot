import sqlite3
from datetime import datetime, timezone

def get_connection():
    return sqlite3.connect("danbot.db")

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            filepath TEXT NOT NULL,
            added_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            discord_user_id TEXT NOT NULL,
            requested_at TEXT NOT NULL,
            FOREIGN KEY (file_id) REFERENCES files(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            category TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS post_tags (
            file_id TEXT REFERENCES files(id),
            tag_id INTEGER REFERENCES tags(id),
            PRIMARY KEY (file_id, tag_id)
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_post_tags_tag_id ON post_tags(tag_id)
    """)
    try:
        cur.execute("ALTER TABLE files ADD COLUMN score INTEGER")
    except:
        pass
    conn.commit()
    conn.close()

TAG_CATEGORY_FIELDS = {
    "tag_string_artist": "artist",
    "tag_string_character": "character",
    "tag_string_copyright" : "copyright",
    "tag_string_general": "general",
}

def save_tags(item_id, posts):
    """posts: a list of one or more post dicts to pull tags from"""
    conn = get_connection()
    cur = conn.cursor()
    for post in posts:
        for field, category in TAG_CATEGORY_FIELDS.items():
            tag_string = post.get(field)
            if not tag_string:
                continue
            for tag_name in tag_string.split():
                cur.execute("INSERT OR IGNORE INTO tags (name, category) VALUES (?, ?)", (tag_name, category))
                cur.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
                tag_id = cur.fetchone()[0]
                cur.execute("INSERT OR IGNORE INTO post_tags (file_id, tag_id) VALUES (?, ?)", (item_id, tag_id))
    conn.commit()
    conn.close()

def ensure_file_logged(item_id, filepath, score=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT filepath, score FROM files WHERE id = ?", (item_id,))
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "INSERT INTO files (id, filepath, added_at, score) VALUES (?, ?, ?, ?)",
            (item_id, filepath, datetime.now(timezone.utc).isoformat(), score)
        )
    else:
        existing_filepath, existing_score = row
        new_filepath = filepath if filepath != existing_filepath else existing_filepath
        new_score = score if score is not None else existing_score
        if new_filepath != existing_filepath or new_score != existing_score:
            cur.execute("UPDATE files SET filepath = ?, score = ? WHERE id = ?", (new_filepath, new_score, item_id))
    conn.commit()
    conn.close()

def log_request(file_id, discord_user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO requests (file_id, discord_user_id, requested_at) VALUES (?, ?, ?)",
        (file_id, str(discord_user_id), datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()

def get_filepath(file_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT filepath FROM files WHERE id = ?", (file_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def get_tags(limit=20, offset=0, category=None):
    conn = get_connection()
    cur = conn.cursor()
    if category:
        cur.execute("""
            SELECT t.id, t.name, COUNT(pt.file_id) as freq
            FROM tags t
            JOIN post_tags pt ON t.id = pt.tag_id
            WHERE t.category = ?
            GROUP BY t.id
            ORDER BY freq DESC
            LIMIT ? OFFSET ?
        """, (category, limit, offset))
    else:
        cur.execute("""
            SELECT t.id, t.name, COUNT(pt.file_id) as freq
            FROM tags t
            JOIN post_tags pt ON t.id = pt.tag_id
            GROUP BY t.id
            ORDER BY freq DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
    rows = cur.fetchall()
    conn.close()
    return rows  # list of (tag_id, tag_name, freq)

def get_top_requested_files(limit=20, offset=0):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT file_id, COUNT(*) as req_count
        FROM requests
        GROUP BY file_id
        ORDER BY req_count DESC
        LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = cur.fetchall()
    conn.close()
    return rows  # list of (file_id, req_count)

def get_top_requested_tags(limit=20, offset=0, category=None):
    conn = get_connection()
    cur = conn.cursor()
    if category:
        cur.execute("""
            SELECT t.id, t.name, COUNT(r.id) as req_count
            FROM tags t
            JOIN post_tags pt ON t.id = pt.tag_id
            JOIN requests r ON r.file_id = pt.file_id
            WHERE t.category = ?
            GROUP BY t.id
            ORDER BY req_count DESC
            LIMIT ? OFFSET ?
        """, (category, limit, offset))
    else:
        cur.execute("""
            SELECT t.id, t.name, COUNT(r.id) as req_count
            FROM tags t
            JOIN post_tags pt ON t.id = pt.tag_id
            JOIN requests r ON r.file_id = pt.file_id
            GROUP BY t.id
            ORDER BY req_count DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
    rows = cur.fetchall()
    conn.close()
    return rows  # list of (tag_name, req_count)

def get_top_files_by_score(limit=20, offset=0):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, score FROM files ORDER BY score DESC LIMIT ? OFFSET ?", (limit, offset))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_total_request_count():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM requests")
    count = cur.fetchone()[0]
    conn.close()
    return count

def get_total_file_count():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM files")
    count = cur.fetchone()[0]
    conn.close()
    return count

def get_files_for_tag(tag_id, limit=20, offset=0):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT file_id FROM post_tags
        WHERE tag_id = ?
        ORDER BY file_id
        LIMIT ? OFFSET ?
    """, (tag_id, limit, offset))
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

def set_total_size(size_bytes):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('total_size_bytes', ?)", (str(size_bytes),))
    conn.commit()
    conn.close()

def get_total_size():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM meta WHERE key = 'total_size_bytes'")
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if row else 0

init_db()