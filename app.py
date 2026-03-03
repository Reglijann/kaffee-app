import os
import sqlite3

import psycopg
from flask import Flask, redirect, request, url_for

app = Flask(__name__)

# ---------- DB Layer (Postgres via DATABASE_URL, else SQLite) ----------

SQLITE_PATH = "data.db"


def get_db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def is_postgres() -> bool:
    url = get_db_url()
    return bool(url) and url.startswith("postgres")


def get_conn():
    """
    Returns a connection object for either Postgres (psycopg) or SQLite (sqlite3).
    """
    if is_postgres():
        return psycopg.connect(get_db_url())
    return sqlite3.connect(SQLITE_PATH)


def init_db():
    """
    Ensures the 'counter' table exists and row (id=1) exists.
    Safe to call multiple times.
    """
    conn = get_conn()
    cur = conn.cursor()

    if is_postgres():
        cur.execute("""
            CREATE TABLE IF NOT EXISTS counter (
                id INTEGER PRIMARY KEY,
                value INTEGER NOT NULL DEFAULT 0
            )
        """)
        cur.execute("""
            INSERT INTO counter (id, value)
            VALUES (1, 0)
            ON CONFLICT (id) DO NOTHING
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS counter (
                id INTEGER PRIMARY KEY,
                value INTEGER NOT NULL
            )
        """)
        cur.execute("SELECT COUNT(*) FROM counter WHERE id = 1")
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO counter (id, value) VALUES (1, 0)")

    conn.commit()
    cur.close()
    conn.close()


def get_total() -> int:
    init_db()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM counter WHERE id = 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return int(row[0]) if row else 0


def set_total(value: int):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    if is_postgres():
        cur.execute("UPDATE counter SET value = %s WHERE id = 1", (value,))
    else:
        cur.execute("UPDATE counter SET value = ? WHERE id = 1", (value,))

    conn.commit()
    cur.close()
    conn.close()


def change_total(delta: int):
    total = get_total()
    total = max(0, total + delta)
    set_total(total)


def reset_counter():
    set_total(0)


# ---------- Routes / UI ----------

@app.get("/")
def index():
    total = get_total()
    return f"""
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Kaffee Zähler</title>
  <style>
    body {{ text-align:center; font-family: Arial, sans-serif; margin: 0; padding: 0; }}
    .wrap {{ margin-top: 90px; padding: 16px; }}
    .row {{ display:flex; justify-content:center; gap:18px; flex-wrap:wrap; margin-top: 24px; }}
    .big {{ font-size: 56px; padding: 36px 70px; border-radius: 22px; border: none; color: white; cursor:pointer; }}
    .plus {{ background:#2ecc71; }}
    .minus {{ background:#f39c12; }}
    .counter {{ font-size: 38px; margin-top: 38px; }}
    .reset {{ margin-top: 40px; font-size: 18px; padding: 12px 22px; border-radius: 12px; border: none; background:#e74c3c; color:white; cursor:pointer; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Kaffee</h1>

    <form method="post" action="/change">
      <div class="row">
        <button class="big plus" type="submit" name="delta" value="1">+1 ☕</button>
        <button class="big minus" type="submit" name="delta" value="-1">-1 ↩</button>
      </div>
    </form>

    <div class="counter">Total getrunken: <b>{total}</b></div>

    <form method="get" action="/reset-confirm">
      <button class="reset" type="submit">Reset</button>
    </form>
  </div>
</body>
</html>
"""


@app.post("/change")
def change():
    delta = int(request.form["delta"])
    change_total(delta)
    return redirect(url_for("index"))


@app.get("/reset-confirm")
def reset_confirm():
    return """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Reset?</title>
  <style>
    body { text-align:center; font-family: Arial, sans-serif; margin: 0; padding: 0; }
    .wrap { margin-top: 140px; padding: 16px; }
    button { font-size: 22px; padding: 14px 26px; border-radius: 12px; border: none; cursor:pointer; }
    .yes { background:#e74c3c; color:white; }
    .no { background:#95a5a6; color:white; margin-top: 16px; }
  </style>
</head>
<body>
  <div class="wrap">
    <h2>Sicher zurücksetzen?</h2>

    <form method="post" action="/reset">
      <button class="yes" type="submit">Ja, zurücksetzen</button>
    </form>

    <form method="get" action="/">
      <button class="no" type="submit">Abbrechen</button>
    </form>
  </div>
</body>
</html>
"""


@app.post("/reset")
def reset():
    reset_counter()
    return redirect(url_for("index"))


if __name__ == "__main__":
    # Lokal: http://127.0.0.1:5001
    app.run(host="0.0.0.0", port=5001, debug=True)