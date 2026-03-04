from __future__ import annotations

from datetime import date, datetime
from typing import Callable, Optional, Any, Dict, List, Tuple

from flask import flash, redirect, render_template_string, request, url_for


FITNESS_TPL = """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ username }} · Fitness</title>
  {{ base_css|safe }}
  <style>
    .mini { font-size: 13px; color: #666; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid #eee; vertical-align: top; }
    .right { text-align: right; }
    .pill { display:inline-block; padding: 6px 10px; border-radius: 999px; background:#f0f2f7; }
    .chart { width: 100%; height: 220px; background: #fafbff; border: 1px solid #eef1fb; border-radius: 14px; padding: 12px; box-sizing: border-box; }
    .chart svg { width: 100%; height: 100%; display: block; }
    .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
    @media (max-width: 900px) { .grid3 { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <div class="row">
      <div>
        <h1>{{ username }} · Fitness</h1>
        <div class="muted">Workouts & Gewicht – nur für dich (Login nötig).</div>
      </div>
      <div class="spacer"></div>
      <a href="{{ url_for('dashboard', username=username) }}"><button class="btn light">← zurück</button></a>
    </div>
  </div>

  {% with msgs = get_flashed_messages() %}
    {% if msgs %}
      <div class="flash card">{{ msgs[0] }}</div>
    {% endif %}
  {% endwith %}

  <div class="grid3">
    <div class="card" style="margin:0;">
      <h2>Neuer Workout</h2>
      <form method="post" action="{{ url_for('fitness_add_workout', username=username) }}">
        <label class="mini">Datum</label>
        <input name="day" type="date" value="{{ today }}" required>
        <div style="height:8px"></div>

        <label class="mini">Sport / Aktivität</label>
        <input name="activity" placeholder="z.B. Gym, Run, Bike, Yoga…" maxlength="60" required>
        <div style="height:8px"></div>

        <label class="mini">Dauer (Minuten)</label>
        <input name="minutes" type="number" min="0" step="1" placeholder="z.B. 45">
        <div style="height:8px"></div>

        <label class="mini">Notiz (optional)</label>
        <input name="note" placeholder="z.B. Beine, Intervalle…" maxlength="200">
        <div style="height:12px"></div>

        <button class="btn" type="submit">Workout speichern</button>
      </form>
    </div>

    <div class="card" style="margin:0;">
      <h2>Gewicht eintragen</h2>
      <form method="post" action="{{ url_for('fitness_add_weight', username=username) }}">
        <label class="mini">Datum</label>
        <input name="day" type="date" value="{{ today }}" required>
        <div style="height:8px"></div>

        <label class="mini">Gewicht (kg)</label>
        <input name="weight_kg" type="number" step="0.1" placeholder="z.B. 79.4" required>
        <div style="height:8px"></div>

        <label class="mini">Grösse (cm, optional)</label>
        <input name="height_cm" type="number" step="0.1" placeholder="z.B. 180">
        <div style="height:12px"></div>

        <button class="btn" type="submit">Eintragen</button>
      </form>

      {% if last_weight %}
        <div style="height:12px"></div>
        <div class="muted">Letzter Eintrag</div>
        <div class="row">
          <span class="pill">{{ last_weight.day }}</span>
          <span class="pill">{{ "%.1f"|format(last_weight.weight_kg) }} kg</span>
          {% if last_weight.height_cm %}
            <span class="pill">{{ "%.1f"|format(last_weight.height_cm) }} cm</span>
          {% endif %}
          {% if last_bmi %}
            <span class="pill">BMI {{ "%.1f"|format(last_bmi) }}</span>
          {% endif %}
        </div>
      {% endif %}
    </div>

    <div class="card" style="margin:0;">
      <h2>Gewichtsverlauf</h2>
      <div class="muted">Letzte {{ weights|length }} Einträge</div>
      <div style="height:10px"></div>

      {% if chart_svg %}
        <div class="chart">{{ chart_svg|safe }}</div>
      {% else %}
        <div class="muted">Noch keine Daten für eine Grafik.</div>
      {% endif %}
    </div>
  </div>

  <div class="grid2" style="margin-top:14px;">
    <div class="card" style="margin:0;">
      <h2>Workouts (neueste zuerst)</h2>
      {% if workouts %}
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Aktivität</th>
              <th class="right">Min</th>
              <th>Notiz</th>
              <th class="right"></th>
            </tr>
          </thead>
          <tbody>
            {% for w in workouts %}
              <tr>
                <td>{{ w.day }}</td>
                <td><b>{{ w.activity }}</b></td>
                <td class="right">{{ w.minutes if w.minutes is not none else "" }}</td>
                <td>{{ w.note or "" }}</td>
                <td class="right">
                  <form method="post" action="{{ url_for('fitness_delete_workout', username=username, workout_id=w.id) }}" style="display:inline;">
                    <button class="btn light" type="submit">löschen</button>
                  </form>
                </td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      {% else %}
        <div class="muted">Noch keine Workouts.</div>
      {% endif %}
    </div>

    <div class="card" style="margin:0;">
      <h2>Gewicht (neueste zuerst)</h2>
      {% if weights %}
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th class="right">kg</th>
              <th class="right">cm</th>
              <th class="right">BMI</th>
              <th class="right"></th>
            </tr>
          </thead>
          <tbody>
            {% for x in weights %}
              <tr>
                <td>{{ x.day }}</td>
                <td class="right">{{ "%.1f"|format(x.weight_kg) }}</td>
                <td class="right">{% if x.height_cm %}{{ "%.1f"|format(x.height_cm) }}{% endif %}</td>
                <td class="right">{% if x.bmi %}{{ "%.1f"|format(x.bmi) }}{% endif %}</td>
                <td class="right">
                  <form method="post" action="{{ url_for('fitness_delete_weight', username=username, weight_id=x.id) }}" style="display:inline;">
                    <button class="btn light" type="submit">löschen</button>
                  </form>
                </td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      {% else %}
        <div class="muted">Noch keine Gewichtseinträge.</div>
      {% endif %}
    </div>
  </div>

</div>
</body>
</html>
"""


def _calc_bmi(weight_kg: float, height_cm: Optional[float]) -> Optional[float]:
    if not height_cm or height_cm <= 0:
        return None
    h_m = height_cm / 100.0
    return weight_kg / (h_m * h_m)


def _svg_weight_chart(points: List[Tuple[str, float]]) -> str:
    """Mini inline SVG chart (no libs). points must be oldest -> newest."""
    if len(points) < 2:
        return ""

    values = [v for _, v in points]
    vmin, vmax = min(values), max(values)
    if vmax - vmin < 0.01:
        vmax = vmin + 1.0

    w, h = 800, 220
    pad_l, pad_r, pad_t, pad_b = 40, 20, 18, 28
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b

    def x(i: int) -> float:
        return pad_l + (iw * i / (len(points) - 1))

    def y(v: float) -> float:
        return pad_t + (ih * (1.0 - (v - vmin) / (vmax - vmin)))

    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(points))
    first_label = points[0][0]
    last_label = points[-1][0]

    svg = f"""
<svg viewBox="0 0 {w} {h}" role="img" aria-label="Gewichtsverlauf">
  <rect x="0" y="0" width="{w}" height="{h}" fill="white" rx="14"></rect>

  <text x="{pad_l}" y="{pad_t - 2}" font-size="12" fill="#666">{vmax:.1f} kg</text>
  <text x="{pad_l}" y="{h - pad_b + 18}" font-size="12" fill="#666">{vmin:.1f} kg</text>

  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{h - pad_b}" stroke="#eee"/>
  <line x1="{pad_l}" y1="{h - pad_b}" x2="{w - pad_r}" y2="{h - pad_b}" stroke="#eee"/>

  <polyline points="{pts}" fill="none" stroke="#2c7be5" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  {"".join(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="4" fill="#2c7be5"/>' for i, (_, v) in enumerate(points))}

  <text x="{pad_l}" y="{h - 8}" font-size="12" fill="#666">{first_label}</text>
  <text x="{w - pad_r}" y="{h - 8}" font-size="12" fill="#666" text-anchor="end">{last_label}</text>
</svg>
""".strip()
    return svg


def init_fitness(app, get_conn: Callable[[], Any], require_login: Callable[[str], int], base_css: str) -> None:
    """Register fitness routes."""

    def init_fitness_db() -> None:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    create table if not exists fitness_workouts (
                        id bigserial primary key,
                        user_id bigint not null references users(id) on delete cascade,
                        day date not null,
                        activity text not null,
                        minutes int,
                        note text,
                        created_at timestamptz not null default now()
                    );
                """)
                cur.execute("""
                    create table if not exists fitness_weights (
                        id bigserial primary key,
                        user_id bigint not null references users(id) on delete cascade,
                        day date not null,
                        weight_kg double precision not null,
                        height_cm double precision,
                        created_at timestamptz not null default now()
                    );
                """)
                cur.execute("create index if not exists fitness_workouts_user_day_idx on fitness_workouts (user_id, day desc);")
                cur.execute("create index if not exists fitness_weights_user_day_idx on fitness_weights (user_id, day desc);")
            conn.commit()

    def _parse_day(s: str) -> date:
        return datetime.strptime(s, "%Y-%m-%d").date()

    def _fetch_workouts(user_id: int, limit: int = 25) -> List[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    select id, day, activity, minutes, note
                    from fitness_workouts
                    where user_id=%s
                    order by day desc, id desc
                    limit %s
                """, (user_id, limit))
                rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append({
                "id": r[0],
                "day": r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1]),
                "activity": r[2],
                "minutes": r[3],
                "note": r[4],
            })
        return out

    def _fetch_weights(user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    select id, day, weight_kg, height_cm
                    from fitness_weights
                    where user_id=%s
                    order by day desc, id desc
                    limit %s
                """, (user_id, limit))
                rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            bmi = _calc_bmi(float(r[2]), float(r[3]) if r[3] is not None else None)
            out.append({
                "id": r[0],
                "day": r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1]),
                "weight_kg": float(r[2]),
                "height_cm": float(r[3]) if r[3] is not None else None,
                "bmi": bmi,
            })
        return out

    @app.get("/u/<username>/fitness")
    def fitness_home(username: str):
        init_fitness_db()
        uid = require_login(username)

        workouts = _fetch_workouts(uid, 25)
        weights = _fetch_weights(uid, 20)

        chart_points = list(reversed([(w["day"], w["weight_kg"]) for w in weights]))
        chart_svg = _svg_weight_chart(chart_points) if len(chart_points) >= 2 else ""

        last_weight = weights[0] if weights else None
        last_bmi = last_weight["bmi"] if last_weight else None

        return render_template_string(
            FITNESS_TPL,
            base_css=base_css,
            username=username,
            today=date.today().isoformat(),
            workouts=workouts,
            weights=weights,
            chart_svg=chart_svg,
            last_weight=last_weight,
            last_bmi=last_bmi,
        )

    @app.post("/u/<username>/fitness/workout/add")
    def fitness_add_workout(username: str):
        init_fitness_db()
        uid = require_login(username)

        day_str = request.form.get("day", "").strip()
        activity = request.form.get("activity", "").strip()
        minutes_raw = request.form.get("minutes", "").strip()
        note = request.form.get("note", "").strip() or None

        if not day_str or not activity:
            flash("Bitte Datum und Aktivität ausfüllen.")
            return redirect(url_for("fitness_home", username=username))

        minutes = None
        if minutes_raw:
            try:
                minutes = int(minutes_raw)
            except ValueError:
                flash("Minuten muss eine Zahl sein.")
                return redirect(url_for("fitness_home", username=username))

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    insert into fitness_workouts (user_id, day, activity, minutes, note)
                    values (%s, %s, %s, %s, %s)
                """, (uid, _parse_day(day_str), activity, minutes, note))
            conn.commit()

        flash("Workout gespeichert ✅")
        return redirect(url_for("fitness_home", username=username))

    @app.post("/u/<username>/fitness/workout/<int:workout_id>/delete")
    def fitness_delete_workout(username: str, workout_id: int):
        init_fitness_db()
        uid = require_login(username)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from fitness_workouts where id=%s and user_id=%s", (workout_id, uid))
            conn.commit()

        flash("Workout gelöscht.")
        return redirect(url_for("fitness_home", username=username))

    @app.post("/u/<username>/fitness/weight/add")
    def fitness_add_weight(username: str):
        init_fitness_db()
        uid = require_login(username)

        day_str = request.form.get("day", "").strip()
        weight_raw = request.form.get("weight_kg", "").strip()
        height_raw = request.form.get("height_cm", "").strip()

        if not day_str or not weight_raw:
            flash("Bitte Datum und Gewicht ausfüllen.")
            return redirect(url_for("fitness_home", username=username))

        try:
            weight_kg = float(weight_raw)
        except ValueError:
            flash("Gewicht muss eine Zahl sein.")
            return redirect(url_for("fitness_home", username=username))

        height_cm = None
        if height_raw:
            try:
                height_cm = float(height_raw)
            except ValueError:
                flash("Grösse muss eine Zahl sein.")
                return redirect(url_for("fitness_home", username=username))

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    insert into fitness_weights (user_id, day, weight_kg, height_cm)
                    values (%s, %s, %s, %s)
                """, (uid, _parse_day(day_str), weight_kg, height_cm))
            conn.commit()

        flash("Gewicht eingetragen ✅")
        return redirect(url_for("fitness_home", username=username))

    @app.post("/u/<username>/fitness/weight/<int:weight_id>/delete")
    def fitness_delete_weight(username: str, weight_id: int):
        init_fitness_db()
        uid = require_login(username)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from fitness_weights where id=%s and user_id=%s", (weight_id, uid))
            conn.commit()

        flash("Eintrag gelöscht.")
        return redirect(url_for("fitness_home", username=username))