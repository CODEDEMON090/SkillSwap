from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.secret_key = "skillswap-hackathon-secret"
DB = Path(__file__).with_name("skillswap.db")

CATEGORIES = ["Design", "Video Editing", "Programming", "Data & AI", "Tutoring", "Music", "Writing", "Other"]

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS gigs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        rate REAL NOT NULL,
        description TEXT NOT NULL,
        creator TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gig_id INTEGER NOT NULL,
        client_name TEXT NOT NULL,
        client_email TEXT NOT NULL,
        message TEXT,
        status TEXT NOT NULL DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (gig_id) REFERENCES gigs(id)
    );
    """)

    if conn.execute("SELECT COUNT(*) FROM gigs").fetchone()[0] == 0:
        demo_gigs = [
            ("Modern Logo Design", "Design", 499, "I will create a clean, modern logo for your brand or project.", "Aarav"),
            ("Python Data Analysis", "Data & AI", 799, "I will clean your dataset and create useful analysis with Python.", "Zoya"),
            ("Short Video Editing", "Video Editing", 599, "I will edit a short-form video with clean cuts, captions and transitions.", "Kabir"),
            ("Landing Page Development", "Programming", 999, "I will build a responsive landing page for your project.", "Riya"),
            ("Math Tutoring", "Tutoring", 399, "One-on-one help with school and entrance-exam mathematics.", "Aman"),
            ("Presentation Writing", "Writing", 449, "I will turn your ideas into a clear and professional presentation.", "Sara"),
        ]
        conn.executemany(
            "INSERT INTO gigs (title, category, rate, description, creator) VALUES (?, ?, ?, ?, ?)",
            demo_gigs
        )
    conn.commit()
    conn.close()

@app.context_processor
def inject_globals():
    return {"categories": CATEGORIES}

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    conn = get_db()
    sql = "SELECT * FROM gigs WHERE 1=1"
    params = []

    if q:
        sql += " AND (title LIKE ? OR description LIKE ? OR creator LIKE ? OR category LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like, like])

    if category and category in CATEGORIES:
        sql += " AND category = ?"
        params.append(category)

    if q:
        sql += """
        ORDER BY
          CASE
            WHEN title LIKE ? THEN 0
            WHEN category LIKE ? THEN 1
            ELSE 2
          END,
          created_at DESC
        """
        params.extend([f"%{q}%", f"%{q}%"])
    else:
        sql += " ORDER BY created_at DESC"

    gigs = conn.execute(sql, params).fetchall()
    conn.close()

    return render_template("index.html", gigs=gigs, q=q, selected_category=category)

@app.route("/post", methods=["GET", "POST"])
def post_gig():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        rate = request.form.get("rate", "").strip()
        description = request.form.get("description", "").strip()
        creator = request.form.get("creator", "").strip()

        if not all([title, category, rate, description, creator]):
            flash("Please complete every field.", "error")
            return render_template("post_gig.html")

        try:
            rate_value = float(rate)
            if rate_value <= 0:
                raise ValueError
        except ValueError:
            flash("Enter a valid positive rate.", "error")
            return render_template("post_gig.html")

        conn = get_db()
        conn.execute(
            "INSERT INTO gigs (title, category, rate, description, creator) VALUES (?, ?, ?, ?, ?)",
            (title, category, rate_value, description, creator)
        )
        conn.commit()
        gig_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

        flash("Your gig is live!", "success")
        return redirect(url_for("gig_detail", gig_id=gig_id))

    return render_template("post_gig.html")

@app.route("/gig/<int:gig_id>")
def gig_detail(gig_id):
    conn = get_db()
    gig = conn.execute("SELECT * FROM gigs WHERE id = ?", (gig_id,)).fetchone()
    conn.close()

    if not gig:
        return "Gig not found", 404

    return render_template("gig.html", gig=gig)

@app.route("/book/<int:gig_id>", methods=["POST"])
def book_gig(gig_id):
    client_name = request.form.get("client_name", "").strip()
    client_email = request.form.get("client_email", "").strip()
    message = request.form.get("message", "").strip()

    if not client_name or not client_email:
        flash("Name and email are required.", "error")
        return redirect(url_for("gig_detail", gig_id=gig_id))

    conn = get_db()
    gig = conn.execute("SELECT * FROM gigs WHERE id = ?", (gig_id,)).fetchone()

    if not gig:
        conn.close()
        return "Gig not found", 404

    conn.execute(
        "INSERT INTO bookings (gig_id, client_name, client_email, message) VALUES (?, ?, ?, ?)",
        (gig_id, client_name, client_email, message)
    )
    conn.commit()
    conn.close()

    flash("Booking request sent successfully.", "success")
    return redirect(url_for("bookings", client_name=client_name))

@app.route("/bookings")
def bookings():
    client_name = request.args.get("client_name", "").strip()
    conn = get_db()

    if client_name:
        rows = conn.execute("""
            SELECT bookings.*, gigs.title, gigs.category, gigs.rate, gigs.creator
            FROM bookings
            JOIN gigs ON gigs.id = bookings.gig_id
            WHERE bookings.client_name = ?
            ORDER BY bookings.created_at DESC
        """, (client_name,)).fetchall()
    else:
        rows = []

    conn.close()
    return render_template("bookings.html", bookings=rows, client_name=client_name)

@app.route("/dashboard")
def dashboard():
    creator = request.args.get("creator", "").strip()
    conn = get_db()

    if creator:
        rows = conn.execute("""
            SELECT bookings.*, gigs.title, gigs.category, gigs.creator
            FROM bookings
            JOIN gigs ON gigs.id = bookings.gig_id
            WHERE gigs.creator = ?
            ORDER BY bookings.created_at DESC
        """, (creator,)).fetchall()
    else:
        rows = []

    conn.close()
    return render_template("dashboard.html", bookings=rows, creator=creator)

@app.post("/booking/<int:booking_id>/<action>")
def update_booking(booking_id, action):
    if action not in ("accept", "decline"):
        return "Invalid action", 400

    status = "Accepted" if action == "accept" else "Declined"
    conn = get_db()
    conn.execute("UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id))
    conn.commit()
    conn.close()

    flash(f"Booking marked {status.lower()}.", "success")
    return redirect(request.referrer or url_for("dashboard"))

@app.get("/health")
def health():
    return {"status": "ok"}

init_db()

if __name__ == "__main__":
    app.run(debug=True)
