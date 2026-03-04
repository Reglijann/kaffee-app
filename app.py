import os
from functools import wraps

from flask import Flask, redirect, render_template_string, request, session, url_for, abort
import psycopg

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")


def get_db_url() -> str:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    return db_url


def get_conn():
    # Supabase Pooler URL funktioniert gut auf Render
    return psycopg.connect(get_db_url())


def init_db():
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS counter (
                    id INT PRIMARY KEY,
                    value INT NOT NULL
                )
                """
            )
            c.execute("SELECT COUNT(*) FROM counter WHERE id = 1")
            if c.fetchone()[0] == 0:
                c.execute("INSERT INTO counter (id, value) VALUES (1, 0)")
        conn.commit()


def get_total() -> int:
    init_db()
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("SELECT value FROM counter WHERE id = 1")
            return int(c.fetchone()[0])


def set_total(new_value: int):
    init_db()
    with get_conn() as conn:
        with conn.cursor() as c:
            c.execute("UPDATE counter SET value = %s WHERE id = 1", (new_value,))
        conn.commit()


def is_admin() -> bool:
    return session.get("is_admin") is True


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_admin():
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Kaffee</title>
  <style>
    body { font-family: system-ui; max-width: 520px; margin: 40px auto; padding: 0 16px; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 18px; }
    .big { font-size: 56px; font-weight: 800; margin: 12px 0; }
    button { padding: 14px 18px; font-size: 18px; border-radius: 12px; border: 1px solid #ccc; cursor: pointer; }
    .row { display:flex; gap: 10px; flex-wrap: wrap; }
    .muted { color:#666; }
    .top { display:flex; justify-content: space-between; align-items:center; gap: 10px; }
    a { color: inherit; }
  </style>
</head>
<body>
  <div class="top">
    <h2>Kaffee-Zähler</h2>
    {% if is_admin %}
      <form method="post" action="{{ url_for('logout') }}">
        <button type="submit">Admin logout</button>
      </form>
    {% else %}
      <a href="{{ url_for('login') }}" class="muted">Admin login</a>
    {% endif %}
  </div>

  <div class="card">
    <div class="muted">Total getrunken:</div>
    <div class="big">{{ total }}</div>

    {% if is_admin %}
      <div class="row">
        <form method="post" action="{{ url_for('change') }}">
          <input type="hidden" name="delta" value="1">
          <button type="submit">+1</button>
        </form>

        <form method="post" action="{{ url_for('change') }}">
          <input type="hidden" name="delta" value="-1">
          <button type="submit">-1</button>
        </form>

        <form method="get" action="{{ url_for('reset_confirm') }}">
          <button type="submit">Reset</button>
        </form>
      </div>
      <p class="muted">Admin-Modus aktiv ✅</p>
    {% else %}
      <p class="muted">Besucher-Modus: nur anschauen 👀</p>
    {% endif %}
  </div>
</body>
</html>
"""

LOGIN_TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Admin Login</title>
  <style>
    body { font-family: system-ui; max-width: 520px; margin: 40px auto; padding: 0 16px; }
    input, button { padding: 12px 14px; font-size: 16px; border-radius: 10px; border: 1px solid #ccc; }
    .row { display:flex; gap: 10px; }
    .err { color: #b00; }
  </style>
</head>
<body>
  <h2>Admin Login</h2>
  {% if error %}<p class="err">{{ error }}</p>{% endif %}
  <form method="post">
    <div class="row">
      <input type="password" name="password" placeholder="Admin Passwort" required>
      <button type="submit">Login</button>
    </div>
  </form>
  <p><a href="{{ url_for('index') }}">Zurück</a></p>
</body>
</html>
"""

RESET_TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Reset?</title>
  <style>
    body { font-family: system-ui; max-width: 520px; margin: 40px auto; padding: 0 16px; }
    button { padding: 14px 18px; font-size: 18px; border-radius: 12px; border: 1px solid #ccc; cursor: pointer; }
    .row { display:flex; gap: 10px; flex-wrap: wrap; }
  </style>
</head>
<body>
  <h2>Sicher zurücksetzen?</h2>
  <div class="row">
    <form method="post" action="{{ url_for('reset') }}">
      <button type="submit">Ja, reset</button>
    </form>
    <form method="get" action="{{ url_for('index') }}">
      <button type="submit">Abbrechen</button>
    </form>
  </div>
</body>
</html>
"""


@app.get("/")
def index():
    total = get_total()
    return render_template_string(TEMPLATE, total=total, is_admin=is_admin())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        admin_pw = os.environ.get("ADMIN_PASSWORD", "")
        if admin_pw and pw == admin_pw:
            session["is_admin"] = True
            return redirect(url_for("index"))
        return render_template_string(LOGIN_TEMPLATE, error="Falsches Passwort.")
    return render_template_string(LOGIN_TEMPLATE, error=None)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.post("/change")
@admin_required
def change():
    delta = int(request.form.get("delta", "0"))
    total = get_total()
    total = max(0, total + delta)   # nicht unter 0
    set_total(total)
    return redirect(url_for("index"))


@app.get("/reset-confirm")
@admin_required
def reset_confirm():
    return render_template_string(RESET_TEMPLATE)


@app.post("/reset")
@admin_required
def reset():
    set_total(0)
    return redirect(url_for("index"))