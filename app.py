import os
import re
from typing import Optional

import psycopg
from flask import (
    Flask, redirect, render_template_string, request, session,
    url_for, abort, flash
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
            
            cur.execute("""
            create table if not exists users(
                id bigserial primary key,
                username text unique not null,
                password_hash text not null,
                created_at timestamptz not null default now()
            )
            """)
            
            cur.execute("""
            alter table users
            add column if not exists capsule_balance integer not null default 0
            """)
            
            cur.execute("""
            create table if not exists stats(
                user_id bigint primary key references users(id) on delete cascade,
                total integer not null default 0
            )
            """)
            
            cur.execute("""
            create table if not exists global_state(
                id integer primary key,
                shared_stock integer not null default 0
            )
            """)
            
            cur.execute("""
            insert into global_state (id, shared_stock)
            values (1,0)
            on conflict (id) do nothing
            """)
            
        conn.commit()


@app.before_request
def ensure_db():
    init_db()


# -------------------------
# shared stock
# -------------------------
def get_shared_stock():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("select shared_stock from global_state where id=1")
            return cur.fetchone()[0]


def change_stock(delta):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            update global_state
            set shared_stock = shared_stock + %s
            where id = 1
            """, (delta,))


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


def current_user_id_for(username):
    return session.get(f"uid:{username}")


def require_login(username):
    uid = current_user_id_for(username)
    if not uid:
        abort(403)
    return int(uid)


def get_user_by_username(username):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("select id, username, password_hash from users where username=%s", (username,))
            return cur.fetchone()


# -------------------------
# fairness helpers
# -------------------------
def next_to_buy():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            select username
            from users
            order by capsule_balance asc
            limit 1
            """)
            row = cur.fetchone()
            return row[0] if row else None


def fairness_ranking():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            select username, capsule_balance
            from users
            order by capsule_balance asc
            """)
            return cur.fetchall()


# -------------------------
# CSS
# -------------------------
BASE_CSS = """
<style>
body { font-family: system-ui; background:#f6f7fb; }
.wrap { max-width:900px;margin:auto;padding:20px }
.card { background:white;border-radius:16px;padding:18px;margin:14px 0 }
.big { font-size:42px;font-weight:700 }
.btn { padding:12px 14px;border-radius:10px;border:0;background:#2c7be5;color:white }
.btn.light { background:#e9eef9;color:#1b3a6b }
.row { display:flex;gap:10px;align-items:center }
.spacer { flex:1 }
</style>
"""


# -------------------------
# INDEX
# -------------------------
INDEX_TPL = """
<!doctype html>
<html>
<head>
<title>Kaffee</title>
""" + BASE_CSS + """
</head>

<body>
<div class="wrap">

<div class="card">
<h1>Kaffee Counter ☕</h1>
<div class="muted">Total getrunken</div>
<div class="big">{{ total }}</div>
</div>

<div class="card">
<h2>Kapselvorrat</h2>
<div class="big">{{ stock }}</div>
</div>

<div class="card">
<h2>Nächste Person bringt Kapseln</h2>
<div class="big">{{ next_person }}</div>
</div>

<div class="card">
<h2>Fairness Ranking</h2>

{% for u in fairness %}
<div class="row">
<div>{{ u[0] }}</div>
<div class="spacer"></div>
<div>{{ u[1] }}</div>
</div>
{% endfor %}

</div>

<div class="card">
<h2>Accounts</h2>

{% for u in users %}
<a href="{{ url_for('user_entry', username=u) }}">{{ u }}</a><br>
{% endfor %}

</div>

</div>
</body>
</html>
"""


# -------------------------
# ROUTES
# -------------------------
@app.get("/health")
def health():
    return "ok", 200


@app.get("/")
def index():

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute("select coalesce(sum(total),0) from stats")
            total = cur.fetchone()[0]

            cur.execute("select username from users order by username")
            users = [r[0] for r in cur.fetchall()]

    stock = get_shared_stock()
    next_person = next_to_buy()
    fairness = fairness_ranking()

    return render_template_string(
        INDEX_TPL,
        total=total,
        users=users,
        stock=stock,
        next_person=next_person,
        fairness=fairness
    )


# -------------------------
# SIGNUP
# -------------------------
@app.route("/signup", methods=["GET","POST"])
def signup():

    if request.method == "GET":
        return "signup page"

    username = normalize_username(request.form["username"])
    password = request.form["password"]

    pw_hash = generate_password_hash(password)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into users (username,password_hash) values (%s,%s) returning id",
                (username,pw_hash)
            )
            uid = cur.fetchone()[0]

            cur.execute(
                "insert into stats (user_id,total) values (%s,0)",
                (uid,)
            )

    return redirect("/")


# -------------------------
# LOGIN
# -------------------------
@app.get("/u/<username>")
def user_entry(username):
    return f"login page {username}"


@app.post("/u/<username>/login")
def login(username):

    row = get_user_by_username(username)

    if not row:
        abort(404)

    uid,_,pw_hash = row

    if not check_password_hash(pw_hash, request.form["password"]):
        abort(403)

    session[f"uid:{username}"] = uid

    return redirect(url_for("dashboard", username=username))


# -------------------------
# DASHBOARD
# -------------------------
@app.get("/u/<username>/dash")
def dashboard(username):

    uid = require_login(username)

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute("select total from stats where user_id=%s",(uid,))
            total = cur.fetchone()[0]

            cur.execute("select capsule_balance from users where id=%s",(uid,))
            balance = cur.fetchone()[0]

    stock = get_shared_stock()

    return f"""
    <h1>{username}</h1>
    Kaffee: {total}<br>
    Saldo: {balance}<br>
    Vorrat: {stock}<br><br>

    <form method="post" action="/u/{username}/coffee">
    <button>+1 Kaffee</button>
    </form>

    <form method="post" action="/u/{username}/pack">
    <input type="hidden" name="amount" value="12">
    <button>+12 gebracht</button>
    </form>

    <form method="post" action="/u/{username}/pack">
    <input type="hidden" name="amount" value="48">
    <button>+48 gebracht</button>
    </form>
    """


# -------------------------
# COFFEE
# -------------------------
@app.post("/u/<username>/coffee")
def coffee(username):

    uid = require_login(username)

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute("""
            update stats
            set total = total + 1
            where user_id=%s
            """,(uid,))

            cur.execute("""
            update users
            set capsule_balance = capsule_balance - 1
            where id=%s
            """,(uid,))

    change_stock(-1)

    return redirect(url_for("dashboard", username=username))


# -------------------------
# PACK
# -------------------------
@app.post("/u/<username>/pack")
def pack(username):

    uid = require_login(username)

    amount = int(request.form["amount"])

    with get_conn() as conn:
        with conn.cursor() as cur:

            cur.execute("""
            update users
            set capsule_balance = capsule_balance + %s
            where id=%s
            """,(amount,uid))

    change_stock(amount)

    return redirect(url_for("dashboard", username=username))


# -------------------------
# FITNESS
# -------------------------
init_fitness(app, get_conn, require_login, BASE_CSS)


# -------------------------
# LOCAL
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT",5001))
    app.run(host="0.0.0.0",port=port,debug=True)