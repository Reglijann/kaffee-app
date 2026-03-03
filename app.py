import os
import sqlite3
from flask import Flask, redirect, url_for, request

app = Flask(__name__)

DB_PATH = os.environ.get("DB_PATH", "data.db")

def connect():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = connect()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS counter (
            id INTEGER PRIMARY KEY,
            value INTEGER NOT NULL
        )
    """)
    # sorgt dafür, dass id=1 existiert (ohne doppelte Einträge)
    c.execute("INSERT OR IGNORE INTO counter (id, value) VALUES (1, 0)")
    conn.commit()
    conn.close()

def get_total():
    init_db()
    conn = connect()
    c = conn.cursor()
    c.execute("SELECT value FROM counter WHERE id = 1")
    value = c.fetchone()[0]
    conn.close()
    return value

def change_total(delta: int):
    init_db()
    conn = connect()
    c = conn.cursor()
    if delta == 1:
        c.execute("UPDATE counter SET value = value + 1 WHERE id = 1")
    else:
        c.execute("""
            UPDATE counter
            SET value = CASE WHEN value > 0 THEN value - 1 ELSE 0 END
            WHERE id = 1
        """)
    conn.commit()
    conn.close()

def reset_counter():
    init_db()
    conn = connect()
    c = conn.cursor()
    c.execute("UPDATE counter SET value = 0 WHERE id = 1")
    conn.commit()
    conn.close()

@app.route("/", methods=["GET"])
def index():
    total = get_total()
    return f"""
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <style>
        body {{ text-align: center; font-family: Arial; margin-top: 100px; }}
        .big-button {{ font-size: 60px; padding: 40px 80px; border-radius: 20px; border: none; color: white; margin: 20px; }}
        .plus {{ background-color: #4CAF50; }}
        .minus {{ background-color: #f39c12; }}
        .reset {{ font-size: 20px; padding: 10px 20px; border-radius: 10px; border: none; background-color: #e74c3c; color: white; margin-top: 40px; }}
        .counter {{ font-size: 40px; margin-top: 40px; }}
        .row {{ display:flex; justify-content:center; flex-wrap:wrap; gap:20px; }}
      </style>
    </head>
    <body>

      <form method="post" action="/change">
        <div class="row">
          <button class="big-button plus" type="submit" name="delta" value="1">+1 ☕</button>
          <button class="big-button minus" type="submit" name="delta" value="-1">-1 ↩</button>
        </div>
      </form>

      <div class="counter">Total getrunken: {total}</div>

      <form method="get" action="/reset-confirm">
        <button class="reset" type="submit">Reset</button>
      </form>

    </body>
    </html>
    """

@app.route("/change", methods=["POST"])
def change():
    delta = int(request.form["delta"])
    change_total(delta)
    return redirect(url_for("index"))

@app.route("/reset-confirm", methods=["GET"])
def reset_confirm():
    return """
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1" />
    </head>
    <body style="text-align:center;font-family:Arial;margin-top:150px;">
      <h2>Sicher zurücksetzen?</h2>

      <form method="post" action="/reset">
        <button style="font-size:25px;padding:15px 30px;background:#e74c3c;color:white;border:none;border-radius:10px;">
          Ja, zurücksetzen
        </button>
      </form>

      <form method="get" action="/">
        <button style="font-size:25px;padding:15px 30px;background:#95a5a6;color:white;border:none;border-radius:10px;margin-top:20px;">
          Abbrechen
        </button>
      </form>
    </body>
    </html>
    """

@app.route("/reset", methods=["POST"])
def reset():
    reset_counter()
    return redirect(url_for("index"))

# lokal starten (Render startet via gunicorn)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)