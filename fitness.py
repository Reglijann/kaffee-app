# Erweiterung für die Kaffee-App mit dem Fitness Teil

# fitness.py
from __future__ import annotations

from datetime import date as date_cls
from flask import request, redirect, url_for, render_template_string, flash, abort


def init_fitness(app, get_conn, require_login, base_css: str):
		"""
		Register Fitness/Gym routes on the given Flask app.
		- get_conn: function returning psycopg connection (context manager ok)
		- require_login(username) -> user_id (or abort)
		- base_css: CSS string used in app templates
		"""
	
		def ensure_fitness_tables():
				with get_conn() as conn:
						with conn.cursor() as cur:
								# Workouts: what sport, when, duration, optional notes
								cur.execute("""
										create table if not exists workouts (
												id bigserial primary key,
												user_id bigint not null references users(id) on delete cascade,
												day date not null,
												activity text not null,
												minutes int not null default 0,
												notes text,
												created_at timestamptz not null default now()
										);
								""")
								cur.execute("create index if not exists idx_workouts_user_day on workouts(user_id, day desc);")
							
								# Weight entries: day, weight, optional height snapshot
								cur.execute("""
										create table if not exists weights (
												id bigserial primary key,
												user_id bigint not null references users(id) on delete cascade,
												day date not null,
												weight_kg numeric(6,2) not null,
												height_cm int,
												created_at timestamptz not null default now(),
												unique(user_id, day)
										);
								""")
								cur.execute("create index if not exists idx_weights_user_day on weights(user_id, day desc);")
							
		FITNESS_TPL = """
<!doctype html>
<html><head>
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<title>{{ username }} – Fitness</title>
	{base_css}
	<style>
		.small { font-size: 13px; color: #666; }
		textarea { padding: 12px; border-radius: 12px; border: 1px solid #ddd; width: 100%; box-sizing: border-box; min-height: 90px; }
		select { padding: 12px; border-radius: 12px; border: 1px solid #ddd; width: 100%; box-sizing: border-box; background: white; }
		table { width: 100%; border-collapse: collapse; }
		th, td { padding: 10px 8px; border-bottom: 1px solid #eee; text-align: left; vertical-align: top; }
		.chart { width: 100%; overflow-x: auto; }
		.chart svg { width: 100%; height: 220px; }
		.chip { display:inline-block; padding: 6px 10px; border-radius: 999px; background:#f0f2f7; }
	</style>
</head><body>
<div class="wrap">

	<div class="card">
		<div class="row">
			<div>
				<h1>Fitness – {{ username }} 🏋️</h1>
				<div class="muted">Workouts & Gewicht (nur für dich sichtbar, wenn du eingeloggt bist)</div>
			</div>
			<div class="spacer"></div>
			<a href="{{ url_for('dashboard', username=username) }}"><button class="btn light">← zurück</button></a>
		</div>

		{% with msgs = get_flashed_messages() %}
			{% if msgs %}
				<div class="flash" style="margin-top:12px;">{{ msgs[0] }}</div>
			{% endif %}
		{% endwith %}
	</div>

	<div class="grid2">
		<div class="card">
			<h2>Workout eintragen</h2>
			<form method="post" action="{{ url_for('fitness_add_workout', username=username) }}">
				<div class="grid2">
					<div>
						<label class="muted">Tag</label><br>
						<input name="day" type="date" value="{{ today }}" required>
					</div>
					<div>
						<label class="muted">Dauer (Minuten)</label><br>
						<input name="minutes" type="number" step="1" min="0" value="30" required>
					</div>
				</div>

				<div style="height:10px;"></div>
				<label class="muted">Sport</label><br>
				<input name="activity" placeholder="z.B. Gym, Joggen, Fussball, Yoga…" required>

				<div style="height:10px;"></div>
				<label class="muted">Notizen (optional)</label><br>
				<textarea name="notes" placeholder="z.B. Beine, 5km locker, Intervall…"></textarea>

				<div style="height:12px;"></div>
				<button class="btn" type="submit">Speichern</button>
			</form>
		</div>

		<div class="card">
			<h2>Gewicht eintragen</h2>
			<form method="post" action="{{ url_for('fitness_add_weight', username=username) }}">
				<div class="grid2">
					<div>
						<label class="muted">Tag</label><br>
						<input name="day" type="date" value="{{ today }}" required>
					</div>
					<div>
						<label class="muted">Gewicht (kg)</label><br>
						<input name="weight_kg" type="number" step="0.1" min="0" placeholder="z.B. 78.4" required>
					</div>
				</div>

				<div style="height:10px;"></div>
				<label class="muted">Grösse (cm, optional)</label><br>
				<input name="height_cm" type="number" step="1" min="0" placeholder="z.B. 180">

				<div class="small" style="margin-top:8px;">
					Tipp: Pro Tag 1 Wert (wird überschrieben, wenn du denselben Tag nochmals speicherst).
				</div>

				<div style="height:12px;"></div>
				<button class="btn" type="submit">Speichern</button>
			</form>
		</div>
	</div>

	<div class="card">
		<div class="row">
			<h2>Gewichtsverlauf</h2>
			<div class="spacer"></div>
			{% if last_bmi %}
				<span class="chip">BMI (letzter): {{ last_bmi }}</span>
			{% endif %}
		</div>

		{% if chart_svg %}
			<div class="chart" style="margin-top:10px;">{{ chart_svg|safe }}</div>
			<div class="small" style="margin-top:8px;">Letzte {{ chart_points }} Einträge</div>
		{% else %}
			<div class="muted">Noch keine Gewichts-Einträge.</div>
		{% endif %}
	</div>

	<div class="grid2">
		<div class="card">
			<h2>Letzte Workouts</h2>
			{% if workouts %}
				<table>
					<thead>
						<tr><th>Tag</th><th>Sport</th><th>Min</th><th>Notizen</th></tr>
					</thead>
					<tbody>
						{% for w in workouts %}
							<tr>
								<td>{{ w.day }}</td>
								<td><b>{{ w.activity }}</b></td>
								<td>{{ w.minutes }}</td>
								<td class="small">{{ w.notes or '' }}</td>
							</tr>
						{% endfor %}
					</tbody>
				</table>
			{% else %}
				<div class="muted">Noch keine Workouts.</div>
			{% endif %}
		</div>

		<div class="card">
			<h2>Letzte Gewichte</h2>
			{% if weights %}
				<table>
					<thead>
						<tr><th>Tag</th><th>kg</th><th>cm</th></tr>
					</thead>
					<tbody>
						{% for x in weights %}
							<tr>
								<td>{{ x.day }}</td>
								<td><b>{{ x.weight_kg }}</b></td>
								<td class="small">{{ x.height_cm or '' }}</td>
							</tr>
						{% endfor %}
					</tbody>
				</table>
			{% else %}
				<div class="muted">Noch keine Gewichte.</div>
			{% endif %}
		</div>
	</div>

</div>
</body></html>
"""

		def build_weight_chart(points):
				"""
				points: list of tuples (day_str, weight_float) ascending by day.
				Returns SVG string.
				"""
				if len(points) < 2:
						return None
			
				# Basic scaling
				w = 900
				h = 220
				pad = 24
			
				weights = [p[1] for p in points]
				min_w = min(weights)
				max_w = max(weights)
				if max_w - min_w < 0.1:
						max_w = min_w + 0.1
					
				def sx(i):
						return pad + (w - 2 * pad) * (i / (len(points) - 1))
			
				def sy(val):
						# invert y axis
						return pad + (h - 2 * pad) * (1 - ((val - min_w) / (max_w - min_w)))
			
				# line path
				d = []
				for i, (_, val) in enumerate(points):
						x = sx(i)
						y = sy(val)
						d.append(("M" if i == 0 else "L") + f" {x:.1f} {y:.1f}")
				path = " ".join(d)
			
				# y labels
				y1 = min_w
				y2 = (min_w + max_w) / 2
				y3 = max_w
			
				svg = """
<svg viewBox="0 0 {w} {h}" role="img" aria-label="Gewichtsverlauf">
	<rect x="0" y="0" width="{w}" height="{h}" fill="white" />
	<!-- grid -->
	<line x1="{pad}" y1="{sy(y1):.1f}" x2="{w-pad}" y2="{sy(y1):.1f}" stroke="#eee"/>
	<line x1="{pad}" y1="{sy(y2):.1f}" x2="{w-pad}" y2="{sy(y2):.1f}" stroke="#eee"/>
	<line x1="{pad}" y1="{sy(y3):.1f}" x2="{w-pad}" y2="{sy(y3):.1f}" stroke="#eee"/>

	<text x="{pad}" y="{sy(y3)-6:.1f}" font-size="12" fill="#666">{y3:.1f} kg</text>
	<text x="{pad}" y="{sy(y2)-6:.1f}" font-size="12" fill="#666">{y2:.1f} kg</text>
	<text x="{pad}" y="{sy(y1)-6:.1f}" font-size="12" fill="#666">{y1:.1f} kg</text>

	<path d="{path}" fill="none" stroke="#2c7be5" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
"""
				# points
				for i, (day_str, val) in enumerate(points):
						x = sx(i)
						y = sy(val)
						svg += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#2c7be5" />'
						if i in (0, len(points) - 1):
								svg += f'<text x="{x:.1f}" y="{h-pad+16}" text-anchor="middle" font-size="12" fill="#666">{day_str}</text>'
							
				svg += "</svg>"
				return svg
				
		@app.get("/u/<username>/fitness")
		def fitness_home(username):
				user_id = require_login(username)
				ensure_fitness_tables()
			
				today = date_cls.today().isoformat()
			
				with get_conn() as conn:
						with conn.cursor() as cur:
								cur.execute("""
										select day::text, activity, minutes, notes
										from workouts
										where user_id=%s
										order by day desc, id desc
										limit 20
								""", (user_id,))
								workouts = [
										{"day": r[0], "activity": r[1], "minutes": r[2], "notes": r[3]}
										for r in cur.fetchall()
								]
							
								cur.execute("""
										select day::text, weight_kg::float, height_cm
										from weights
										where user_id=%s
										order by day desc, id desc
										limit 20
								""", (user_id,))
								weights_rows = cur.fetchall()
								weights = [{"day": r[0], "weight_kg": f"{r[1]:.1f}", "height_cm": r[2]} for r in weights_rows]
							
								# Chart data (last 30 ascending)
								cur.execute("""
										select day::text, weight_kg::float
										from weights
										where user_id=%s
										order by day asc
										limit 30
								""", (user_id,))
								pts = cur.fetchall()
								chart_svg = build_weight_chart(pts) if pts else None
							
								# BMI from latest entry (if height available)
								cur.execute("""
										select weight_kg::float, height_cm
										from weights
										where user_id=%s
										order by day desc, id desc
										limit 1
								""", (user_id,))
								last = cur.fetchone()
								last_bmi = None
								if last and last[1]:
										kg = float(last[0])
										m = int(last[1]) / 100.0
										if m > 0:
												last_bmi = f"{(kg / (m*m)):.1f}"
											
				return render_template_string(
						FITNESS_TPL,
						username=username,
						today=today,
						workouts=workouts,
						weights=weights,
						chart_svg=chart_svg,
						chart_points=min(30, len(pts)) if pts else 0,
						last_bmi=last_bmi
				)
				
		@app.post("/u/<username>/fitness/workout")
		def fitness_add_workout(username):
				user_id = require_login(username)
				ensure_fitness_tables()
			
				day = (request.form.get("day") or "").strip()
				activity = (request.form.get("activity") or "").strip()
				minutes = (request.form.get("minutes") or "0").strip()
				notes = (request.form.get("notes") or "").strip()
			
				if not day or not activity:
						flash("Bitte Tag und Sport ausfüllen.")
						return redirect(url_for("fitness_home", username=username))
			
				try:
						minutes_i = int(minutes)
				except Exception:
						minutes_i = 0
					
				with get_conn() as conn:
						with conn.cursor() as cur:
								cur.execute("""
										insert into workouts (user_id, day, activity, minutes, notes)
										values (%s, %s, %s, %s, %s)
								""", (user_id, day, activity, minutes_i, notes or None))
							
				flash("Workout gespeichert ✅")
				return redirect(url_for("fitness_home", username=username))

		@app.post("/u/<username>/fitness/weight")
		def fitness_add_weight(username):
				user_id = require_login(username)
				ensure_fitness_tables()
			
				day = (request.form.get("day") or "").strip()
				weight = (request.form.get("weight_kg") or "").strip()
				height = (request.form.get("height_cm") or "").strip()
			
				if not day or not weight:
						flash("Bitte Tag und Gewicht ausfüllen.")
						return redirect(url_for("fitness_home", username=username))
			
				try:
						weight_f = float(weight)
				except Exception:
						flash("Gewicht muss eine Zahl sein (z.B. 78.4).")
						return redirect(url_for("fitness_home", username=username))
			
				height_i = None
				if height:
						try:
								height_i = int(height)
						except Exception:
								height_i = None
							
				with get_conn() as conn:
						with conn.cursor() as cur:
								# unique(user_id, day) -> overwrite the day entry
								cur.execute("""
										insert into weights (user_id, day, weight_kg, height_cm)
										values (%s, %s, %s, %s)
										on conflict (user_id, day) do update set
												weight_kg = excluded.weight_kg,
												height_cm = coalesce(excluded.height_cm, weights.height_cm)
								""", (user_id, day, weight_f, height_i))
							
				flash("Gewicht gespeichert ✅")
				return redirect(url_for("fitness_home", username=username))

		# Optional: small health check that fitness tables exist
		@app.get("/fitness-health")
		def fitness_health():
				try:
						ensure_fitness_tables()
						return "ok", 200
				except Exception:
						return "fail", 500

			