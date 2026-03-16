import os
import re
from typing import Optional

import psycopg
from flask import (
    Flask,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
    abort,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash

from fitness import init_fitness


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")


# -------------------------
# DB helpers
# -------------------------
def get_db_url() -> str:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    return db_url


def get_conn():
    return psycopg.connect(get_db_url(), autocommit=True)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            # users
            cur.execute("""
                create table if not exists users (
                    id bigserial primary key,
                    username text not null unique,
                    password_hash text not null,
                    created_at timestamptz not null default now()
                )
            """)

            # migration: fairness saldo
            cur.execute("""
                alter table users
                add column if not exists capsule_balance integer not null default 0
            """)

            # stats = persönlicher kaffeecounter
            cur.execute("""
                create table if not exists stats (
                    user_id bigint primary key references users(id) on delete cascade,
                    total integer not null default 0,
                    updated_at timestamptz not null default now()
                )
            """)

            # globaler gemeinsamer kapselvorrat
            cur.execute("""
                create table if not exists global_state (
                    id integer primary key,
                    shared_stock integer not null default 0
                )
            """)

            cur.execute("""
                insert into global_state (id, shared_stock)
                values (1, 0)
                on conflict (id) do nothing
            """)

            # kaffee-log für letzte Einträge
            cur.execute("""
                create table if not exists coffee_log (
                    id bigserial primary key,
                    user_id bigint not null references users(id) on delete cascade,
                    delta integer not null,
                    created_at timestamptz not null default now()
                )
            """)

            cur.execute("""
                create index if not exists idx_coffee_log_user_created
                on coffee_log (user_id, created_at desc)
            """)

            cur.execute("""
                create index if not exists idx_users_username on users (username)
            """)

        conn.commit()


@app.before_request
def _ensure_db():
    init_db()


# -------------------------
# auth helpers
# -------------------------
def normalize_username(u: str) -> Optional[str]:
    u = u.strip()
    if not (2 <= len(u) <= 24):
        return None
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", u):
        return None
    return u


def current_user_id_for(username: str) -> Optional[int]:
    return session.get(f"uid:{username}")


def require_login(username: str) -> int:
    uid = current_user_id_for(username)
    if not uid:
        abort(403)
    return int(uid)


def get_user_by_username(username: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, username, password_hash from users where username=%s",
                (username,),
            )
            return cur.fetchone()


def ensure_stats_row(user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into stats (user_id, total)
                values (%s, 0)
                on conflict (user_id) do nothing
            """, (user_id,))
        conn.commit()


# -------------------------
# shared stock / fairness
# -------------------------
def get_shared_stock() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("select shared_stock from global_state where id = 1")
            row = cur.fetchone()
            return int(row[0]) if row else 0


def change_shared_stock(delta: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                update global_state
                set shared_stock = shared_stock + %s
                where id = 1
            """, (delta,))
        conn.commit()


def get_fairness_ranking():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select username, capsule_balance
                from users
                order by capsule_balance asc, username asc
            """)
            return cur.fetchall()


def next_to_buy():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select username
                from users
                order by capsule_balance asc, username asc
                limit 1
            """)
            row = cur.fetchone()
            return row[0] if row else None


# -------------------------
# coffee log
# -------------------------
def add_coffee_log(user_id: int, delta: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into coffee_log (user_id, delta)
                values (%s, %s)
            """, (user_id, delta))
        conn.commit()


from zoneinfo import ZoneInfo

def get_recent_coffee_logs(user_id: int, limit: int = 5):
  
  with get_conn() as conn:
    with conn.cursor() as cur:
      cur.execute("""
        select delta, created_at
        from coffee_log
        where user_id = %s
        order by created_at desc
        limit %s
      """, (user_id, limit))
      
      rows = cur.fetchall()
      
  result = []
  
  zurich = ZoneInfo("Europe/Zurich")
  
  for delta, created_at in rows:
    
    local_time = created_at.astimezone(zurich)
    
    result.append({
      "delta": int(delta),
      "label": "+1" if int(delta) > 0 else "-1",
      "created_at": local_time.strftime("%d.%m.%Y, %H:%M"),
    })
    
  return result


# -------------------------
# UI templates
# -------------------------
BASE_CSS = """
<style>
  body { font-family: -apple-system, system-ui, Arial, sans-serif; margin: 0; padding: 0; background: #f6f7fb; color: #111; }
  .wrap { max-width: 900px; margin: 0 auto; padding: 20px; }
  .card { background: white; border-radius: 16px; padding: 18px; box-shadow: 0 8px 30px rgba(0,0,0,0.06); margin: 14px 0; }
  h1,h2 { margin: 0 0 10px 0; }
  .muted { color: #666; }
  .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  .spacer { flex: 1; }
  a { color: inherit; text-decoration: none; }
  .btn { border: 0; padding: 12px 14px; border-radius: 12px; background: #2c7be5; color: #fff; cursor: pointer; font-weight: 600; }
  .btn.secondary { background: #444; }
  .btn.danger { background: #c0392b; }
  .btn.light { background: #e9eef9; color: #1b3a6b; }
  .btn:active { transform: translateY(1px); }
  input { padding: 12px; border-radius: 12px; border: 1px solid #ddd; width: 100%; box-sizing: border-box; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  @media (max-width: 700px) { .grid2 { grid-template-columns: 1fr; } }
  .big { font-size: 44px; font-weight: 800; }
  .list { display: grid; gap: 10px; }
  .pill { display:inline-block; padding: 6px 10px; border-radius: 999px; background:#f0f2f7; }
  .flash { background: #fff6d6; border: 1px solid #ffe49a; padding: 10px 12px; border-radius: 12px; margin-bottom: 14px; }
  .log-item { display:flex; gap:12px; align-items:center; justify-content:space-between; padding:10px 0; border-bottom:1px solid #eee; }
  .log-item:last-child { border-bottom:0; }
</style>
"""

INDEX_TPL = """
<!doctype html>
<html><head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kaffee ☕</title>
  """ + BASE_CSS + """
</head><body>
<div class="wrap">
  <div class="card">
    <div class="row">
      <div>
        <h1>Kaffee Counter ☕</h1>
        <div class="muted">Total getrunken (alle zusammen)</div>
      </div>
      <div class="spacer"></div>
      <a href="{{ url_for('signup') }}"><button class="btn">Create account</button></a>
    </div>
    <div class="big">{{ total_all }}</div>
  </div>

  {% with msgs = get_flashed_messages() %}
    {% if msgs %}
      <div class="flash">{{ msgs[0] }}</div>
    {% endif %}
  {% endwith %}

  <div class="grid2">
    <div class="card">
      <h2>Gemeinsamer Kapselvorrat</h2>
      <div class="big">{{ shared_stock }}</div>
      {% if shared_stock < 5 %}
        <div class="muted" style="margin-top:8px;">⚠️ Nur noch wenige Kapseln übrig.</div>
      {% endif %}
    </div>

    <div class="card">
      <h2>Nächste Person bringt Kapseln</h2>
      <div class="big">{{ next_person if next_person else "—" }}</div>
      <div class="muted" style="margin-top:8px;">
        Die Person mit dem tiefsten Fairness-Saldo ist als nächstes dran.
      </div>
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Rangliste</h2>
      <div class="muted">Top nach getrunkenen Kaffees</div>
      <div class="list" style="margin-top:12px;">
        {% for u in leaderboard %}
          <a class="card" style="margin:0; padding:12px;" href="{{ url_for('user_entry', username=u.username) }}">
            <div class="row">
              <div><b>{{ loop.index }}.</b> {{ u.username }}</div>
              <div class="spacer"></div>
              <span class="pill">{{ u.total }}</span>
            </div>
          </a>
        {% else %}
          <div class="muted">Noch keine Accounts.</div>
        {% endfor %}
      </div>
    </div>

    <div class="card">
      <h2>Fairness Ranking</h2>
      <div class="muted">Wer ist am meisten im Minus / Plus?</div>
      <div class="list" style="margin-top:12px;">
        {% for row in fairness %}
          <div class="card" style="margin:0; padding:12px;">
            <div class="row">
              <div>{{ row[0] }}</div>
              <div class="spacer"></div>
              <span class="pill">{{ row[1] }}</span>
            </div>
          </div>
        {% else %}
          <div class="muted">Noch keine Accounts.</div>
        {% endfor %}
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Accounts</h2>
    <div class="muted">Klicken → Passwort eingeben → eigene Seite</div>
    <div class="list" style="margin-top:12px;">
      {% for name in users %}
        <a class="card" style="margin:0; padding:12px;" href="{{ url_for('user_entry', username=name) }}">
          <div class="row">
            <div>{{ name }}</div>
            <div class="spacer"></div>
            <span class="pill">öffnen</span>
          </div>
        </a>
      {% else %}
        <div class="muted">Noch keine Accounts.</div>
      {% endfor %}
    </div>
  </div>
</div>
</body></html>
"""

SIGNUP_TPL = """
<!doctype html>
<html><head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Create account</title>
  """ + BASE_CSS + """
</head><body>
<div class="wrap">
  <div class="card">
    <div class="row">
      <h1>Create account</h1>
      <div class="spacer"></div>
      <a href="{{ url_for('index') }}"><button class="btn light">← zurück</button></a>
    </div>

    {% with msgs = get_flashed_messages() %}
      {% if msgs %}
        <div class="flash" style="margin-top:12px;">{{ msgs[0] }}</div>
      {% endif %}
    {% endwith %}

    <form method="post" style="margin-top:12px;">
      <label class="muted">Username (z.B. max, anna_zhaw)</label><br>
      <input name="username" placeholder="username" required>

      <div style="height:10px;"></div>
      <label class="muted">Passwort</label><br>
      <input name="password" type="password" placeholder="passwort" required>

      <div style="height:14px;"></div>
      <button class="btn" type="submit">Account erstellen</button>
    </form>

    <div class="muted" style="margin-top:12px;">
      Tipp: Username nur <b>Buchstaben/Zahlen/._-</b> (2–24 Zeichen).
    </div>
  </div>
</div>
</body></html>
"""

LOGIN_TPL = """
<!doctype html>
<html><head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login {{ username }}</title>
  """ + BASE_CSS + """
</head><body>
<div class="wrap">
  <div class="card">
    <div class="row">
      <h1>{{ username }}</h1>
      <div class="spacer"></div>
      <a href="{{ url_for('index') }}"><button class="btn light">← Home</button></a>
    </div>

    {% with msgs = get_flashed_messages() %}
      {% if msgs %}
        <div class="flash" style="margin-top:12px;">{{ msgs[0] }}</div>
      {% endif %}
    {% endwith %}

    {% if already_logged_in %}
      <div class="muted" style="margin-top:10px;">Du bist bereits eingeloggt.</div>
      <div style="height:12px;"></div>
      <a href="{{ url_for('dashboard', username=username) }}"><button class="btn">Zur eigenen Seite</button></a>
      <form method="post" action="{{ url_for('logout', username=username) }}" style="margin-top:10px;">
        <button class="btn secondary" type="submit">Logout</button>
      </form>
    {% else %}
      <form method="post" action="{{ url_for('login', username=username) }}" style="margin-top:12px;">
        <label class="muted">Passwort</label><br>
        <input name="password" type="password" placeholder="passwort" required>
        <div style="height:14px;"></div>
        <button class="btn" type="submit">Einloggen</button>
      </form>
    {% endif %}
  </div>
</div>
</body></html>
"""

DASH_TPL = """
<!doctype html>
<html><head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ username }} ☕</title>
  """ + BASE_CSS + """
  <style>
    .btn.bigbtn { width: 100%; padding: 22px 16px; font-size: 28px; border-radius: 16px; }
  </style>
</head><body>
<div class="wrap">
  <div class="card">
    <div class="row">
      <div>
        <h1>{{ username }} ☕</h1>
        <div class="muted">Dein Counter & Fairness-Saldo</div>
      </div>

      <div class="spacer"></div>

      <a href="{{ url_for('fitness_home', username=username) }}">
        <button class="btn light">Fitness</button>
      </a>

      <a href="{{ url_for('index') }}">
        <button class="btn light">Home</button>
      </a>

      <form method="post" action="{{ url_for('logout', username=username) }}">
        <button class="btn secondary" type="submit">Logout</button>
      </form>
    </div>

    {% with msgs = get_flashed_messages() %}
      {% if msgs %}
        <div class="flash" style="margin-top:12px;">{{ msgs[0] }}</div>
      {% endif %}
    {% endwith %}

    <div class="grid2" style="margin-top:14px;">
      <div class="card" style="margin:0;">
        <div class="muted">Total getrunken</div>
        <div class="big">{{ total }}</div>
      </div>
      <div class="card" style="margin:0;">
        <div class="muted">Gemeinsamer Vorrat</div>
        <div class="big">{{ stock }}</div>
      </div>
    </div>

    <div class="card" style="margin-top:12px;">
      <div class="muted">Dein Fairness-Saldo</div>
      <div class="big">{{ balance }}</div>
      <div class="muted" style="margin-top:8px;">
        Negativ = du schuldest eher Kapseln. Positiv = du hast eher mehr gebracht als getrunken.
      </div>
    </div>

    <div class="grid2" style="margin-top:12px;">
      <form method="post" action="{{ url_for('coffee_plus', username=username) }}">
        <button class="btn bigbtn" type="submit">+1 Kaffee</button>
      </form>

      <form method="post" action="{{ url_for('coffee_minus', username=username) }}">
        <button class="btn bigbtn secondary" type="submit">-1 Kaffee</button>
      </form>
    </div>

    <div class="card" style="margin-top:12px;">
      <h2>Pack gebracht</h2>

      <div class="row">
        <form method="post" action="{{ url_for('add_pack', username=username) }}">
          <input type="hidden" name="amount" value="12">
          <button class="btn light" type="submit">+12</button>
        </form>

        <form method="post" action="{{ url_for('add_pack', username=username) }}">
          <input type="hidden" name="amount" value="48">
          <button class="btn light" type="submit">+48</button>
        </form>
      </div>

      <div class="muted" style="margin-top:8px;">
        Wenn du ein neues Pack bringst, wird dein Fairness-Saldo entsprechend erhöht.
      </div>
    </div>

    <div class="card" style="margin-top:12px;">
      <h2>Letzte 5 Kaffee-Einträge</h2>

      {% if recent_logs %}
        {% for log in recent_logs %}
          <div class="log-item">
            <div>{{ log.created_at }}</div>
            <div class="pill">{{ log.label }}</div>
          </div>
        {% endfor %}
      {% else %}
        <div class="muted">Noch keine Kaffee-Einträge vorhanden.</div>
      {% endif %}
    </div>

    <div class="card" style="margin-top:12px;">
      <h2>Reset</h2>
      <a href="{{ url_for('reset_confirm', username=username) }}">
        <button class="btn danger">Reset…</button>
      </a>
    </div>
  </div>
</div>
</body></html>
"""

RESET_TPL = """
<!doctype html>
<html><head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Reset bestätigen</title>
  """ + BASE_CSS + """
</head><body>
<div class="wrap">
  <div class="card">
    <h1>Sicher zurücksetzen?</h1>
    <div class="muted">Das setzt <b>{{ username }}</b> Total auf 0. Fairness-Saldo und Vorrat bleiben unverändert.</div>
    <div style="height:14px;"></div>

    <div class="row">
      <a href="{{ url_for('dashboard', username=username) }}"><button class="btn light">Abbrechen</button></a>
      <form method="post" action="{{ url_for('reset', username=username) }}">
        <button class="btn danger" type="submit">Ja, reset</button>
      </form>
    </div>
  </div>
</div>
</body></html>
"""


# -------------------------
# Routes
# -------------------------
@app.get("/health")
def health():
    return "ok", 200


@app.get("/")
def index():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("select coalesce(sum(total), 0) from stats")
            total_all = cur.fetchone()[0] or 0

            cur.execute("""
                select u.username, s.total
                from users u
                join stats s on s.user_id = u.id
                order by s.total desc, u.username asc
                limit 20
            """)
            leaderboard = [{"username": r[0], "total": r[1]} for r in cur.fetchall()]

            cur.execute("select username from users order by username asc")
            users = [r[0] for r in cur.fetchall()]

    return render_template_string(
        INDEX_TPL,
        total_all=total_all,
        leaderboard=leaderboard,
        users=users,
        shared_stock=get_shared_stock(),
        next_person=next_to_buy(),
        fairness=get_fairness_ranking(),
    )


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template_string(SIGNUP_TPL)

    username_raw = request.form.get("username", "")
    password = request.form.get("password", "")

    username = normalize_username(username_raw)
    if not username:
        flash("Username ungültig (2–24 Zeichen, nur Buchstaben/Zahlen/._-).")
        return redirect(url_for("signup"))

    if len(password) < 4:
        flash("Passwort zu kurz (min. 4 Zeichen).")
        return redirect(url_for("signup"))

    pw_hash = generate_password_hash(password)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into users (username, password_hash) values (%s, %s) returning id",
                    (username, pw_hash),
                )
                user_id = cur.fetchone()[0]
                ensure_stats_row(int(user_id))
    except Exception:
        flash("Username existiert schon. Bitte anderen wählen.")
        return redirect(url_for("signup"))

    flash("Account erstellt! Klicke deinen Namen und logge dich ein.")
    return redirect(url_for("index"))


@app.get("/u/<username>")
def user_entry(username):
    row = get_user_by_username(username)
    if not row:
        abort(404)

    already = current_user_id_for(username) is not None
    return render_template_string(
        LOGIN_TPL,
        username=username,
        already_logged_in=already
    )


@app.post("/u/<username>/login")
def login(username):
    row = get_user_by_username(username)
    if not row:
        abort(404)

    user_id, _, pw_hash = row
    password = request.form.get("password", "")

    if not check_password_hash(pw_hash, password):
        flash("Falsches Passwort.")
        return redirect(url_for("user_entry", username=username))

    session[f"uid:{username}"] = int(user_id)
    ensure_stats_row(int(user_id))
    return redirect(url_for("dashboard", username=username))


@app.post("/u/<username>/logout")
def logout(username):
    session.pop(f"uid:{username}", None)
    return redirect(url_for("user_entry", username=username))


@app.get("/u/<username>/dash")
def dashboard(username):
    uid = require_login(username)

    with get_conn() as conn:
        with conn.cursor() as cur:
            ensure_stats_row(uid)

            cur.execute("select total from stats where user_id=%s", (uid,))
            total = cur.fetchone()[0]

            cur.execute("select capsule_balance from users where id=%s", (uid,))
            balance = cur.fetchone()[0]

    return render_template_string(
        DASH_TPL,
        username=username,
        total=total,
        balance=balance,
        stock=get_shared_stock(),
        recent_logs=get_recent_coffee_logs(uid, 5),
    )


@app.post("/u/<username>/coffee-plus")
def coffee_plus(username):
    uid = require_login(username)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                update stats
                set total = total + 1,
                    updated_at = now()
                where user_id = %s
            """, (uid,))

            cur.execute("""
                update users
                set capsule_balance = capsule_balance - 1
                where id = %s
            """, (uid,))
        conn.commit()

    change_shared_stock(-1)
    add_coffee_log(uid, 1)
    return redirect(url_for("dashboard", username=username))


@app.post("/u/<username>/coffee-minus")
def coffee_minus(username):
    uid = require_login(username)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                update stats
                set total = greatest(0, total - 1),
                    updated_at = now()
                where user_id = %s
            """, (uid,))

            cur.execute("""
                update users
                set capsule_balance = capsule_balance + 1
                where id = %s
            """, (uid,))
        conn.commit()

    change_shared_stock(1)
    add_coffee_log(uid, -1)
    return redirect(url_for("dashboard", username=username))


@app.post("/u/<username>/pack")
def add_pack(username):
    uid = require_login(username)
    amount = int(request.form["amount"])

    if amount not in (12, 48):
        abort(400)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                update users
                set capsule_balance = capsule_balance + %s
                where id = %s
            """, (amount, uid))
        conn.commit()

    change_shared_stock(amount)
    flash(f"{amount} Kapseln hinzugefügt ✅")
    return redirect(url_for("dashboard", username=username))


@app.get("/u/<username>/reset-confirm")
def reset_confirm(username):
    require_login(username)
    return render_template_string(RESET_TPL, username=username)


@app.post("/u/<username>/reset")
def reset(username):
    uid = require_login(username)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                update stats
                set total = 0,
                    updated_at = now()
                where user_id = %s
            """, (uid,))
        conn.commit()

    return redirect(url_for("dashboard", username=username))
  
  
@app.get("/api/coffee")
def api_coffee():
  
  username = request.args.get("user")
  key = request.args.get("key")
  
  if key != os.environ.get("API_KEY"):
    abort(403)
    
  row = get_user_by_username(username)
  
  if not row:
    abort(404)
    
  user_id = row[0]
  
  with get_conn() as conn:
    with conn.cursor() as cur:
      
      cur.execute("""
        update stats
        set total = total + 1,
          updated_at = now()
        where user_id = %s
      """, (user_id,))
      
      cur.execute("""
        update users
        set capsule_balance = capsule_balance - 1
        where id = %s
      """, (user_id,))
      
  change_shared_stock(-1)
  add_coffee_log(user_id, 1)
  
  return "ok"


# -------------------------
# Fitness module
# -------------------------
init_fitness(app, get_conn, require_login, BASE_CSS)


# -------------------------
# Local dev
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True)