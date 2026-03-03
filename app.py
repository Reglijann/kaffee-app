from flask import Flask, redirect, url_for, request
import sqlite3

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS counter (
            id INTEGER PRIMARY KEY,
            value INTEGER
        )
    """)
    c.execute("SELECT COUNT(*) FROM counter")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO counter (id, value) VALUES (1, 0)")
    conn.commit()
    conn.close()

def get_total():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("SELECT value FROM counter WHERE id = 1")
    value = c.fetchone()[0]
    conn.close()
    return value

def increment():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("UPDATE counter SET value = value + 1 WHERE id = 1")
    conn.commit()
    conn.close()

def decrement():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("""
        UPDATE counter 
        SET value = CASE 
            WHEN value > 0 THEN value - 1 
            ELSE 0 
        END
        WHERE id = 1
    """)
    conn.commit()
    conn.close()
    
def reset_counter():
    conn = sqlite3.connect("data.db")
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
        <style>
            body {{
                text-align: center;
                font-family: Arial;
                margin-top: 100px;
            }}
            .big-button {{
                font-size: 60px;
                padding: 40px 80px;
                border-radius: 20px;
                border: none;
                background-color: #4CAF50;
                color: white;
                margin: 20px;
            }}
            .reset-button {{
                font-size: 20px;
                padding: 10px 20px;
                border-radius: 10px;
                border: none;
                background-color: #e74c3c;
                color: white;
                margin-top: 40px;
            }}
            .counter {{
                font-size: 40px;
                margin-top: 40px;
            }}
        </style>
    </head>
    <body>

        <form method="post" action="/change">
            <button class="big-button" type="submit" name="delta" value="1">+1 ☕</button>
            <button class="big-button" type="submit" name="delta" value="-1"
                    style="background-color:#f39c12;">-1 ↩</button>
        </form>

        <div class="counter">
            Total getrunken: {total}
        </div>

        <form method="get" action="/reset-confirm">
            <button class="reset-button" type="submit">Reset</button>
        </form>

    </body>
    </html>
    """

@app.route("/change", methods=["POST"])
def change():
    delta = int(request.form["delta"])
    
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    
    if delta == 1:
        c.execute("UPDATE counter SET value = value + 1 WHERE id = 1")
    else:
        # nie unter 0
        c.execute("""
            UPDATE counter
            SET value = CASE WHEN value > 0 THEN value - 1 ELSE 0 END
            WHERE id = 1
        """)
        
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/reset-confirm", methods=["GET"])
def reset_confirm():
    return """
    <html>
    <head>
        <style>
            body {
                text-align: center;
                font-family: Arial;
                margin-top: 150px;
            }
            .confirm-button {
                font-size: 25px;
                padding: 15px 30px;
                margin: 20px;
                border-radius: 10px;
                border: none;
            }
            .yes {
                background-color: #e74c3c;
                color: white;
            }
            .no {
                background-color: #95a5a6;
                color: white;
            }
        </style>
    </head>
    <body>
        <h2>Sicher zurücksetzen?</h2>

        <form method="post" action="/reset">
            <button class="confirm-button yes" type="submit">Ja, zurücksetzen</button>
        </form>

        <form method="get" action="/">
            <button class="confirm-button no" type="submit">Abbrechen</button>
        </form>
    </body>
    </html>
    """

@app.route("/reset", methods=["POST"])
def reset():
    reset_counter()
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)