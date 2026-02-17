import os
import sqlite3
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash


# -----------------------------
# APP CONFIG
# -----------------------------
app = Flask(__name__)
app.secret_key = "change-this-to-a-long-random-secret"  # change later for production

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "site.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


# -----------------------------
# DB HELPERS
# -----------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Creates the database tables using schema.sql.
    Safe to run multiple times if schema uses IF NOT EXISTS.
    """
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"schema.sql not found at: {SCHEMA_PATH}")

    db = get_db()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()
    db.close()
    return True


def login_required(fn):
    """
    Simple decorator to protect routes.
    """
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")


# ---------- AUTH ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("register"))

        db = get_db()

        # check username exists
        existing = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing:
            db.close()
            flash("Username already exists. Please choose another.", "warning")
            return redirect(url_for("register"))

        pw_hash = generate_password_hash(password)

        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, pw_hash)
        )
        db.commit()
        db.close()

        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        db.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


# ---------- DASHBOARD (POSTING) ----------
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    db = get_db()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title or not content:
            flash("Title and content are required.", "danger")
            return redirect(url_for("dashboard"))

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "INSERT INTO posts (title, content, created_at, user_id) VALUES (?, ?, ?, ?)",
            (title, content, created_at, session["user_id"])
        )
        db.commit()
        flash("Post published!", "success")
        return redirect(url_for("dashboard"))

    # show user's posts on dashboard
    my_posts = db.execute("""
        SELECT posts.id, posts.title, posts.content, posts.created_at, users.username
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE users.id = ?
        ORDER BY posts.id DESC
    """, (session["user_id"],)).fetchall()

    db.close()
    return render_template("dashboard.html", posts=my_posts)


# ---------- PUBLIC POSTS ----------
@app.route("/posts")
def posts():
    db = get_db()
    rows = db.execute("""
        SELECT posts.id, posts.title, posts.content, posts.created_at, users.username
        FROM posts
        JOIN users ON posts.user_id = users.id
        ORDER BY posts.id DESC
    """).fetchall()
    db.close()
    return render_template("posts.html", posts=rows)


@app.route("/post/<int:post_id>")
def view_post(post_id):
    db = get_db()
    row = db.execute("""
        SELECT posts.id, posts.title, posts.content, posts.created_at, users.username
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = ?
    """, (post_id,)).fetchone()
    db.close()

    if row is None:
        return "Post not found", 404

    return render_template("post.html", post=row)


# ---------- DB INIT COMMAND ----------
@app.route("/init-db")
def init_db_route():
    """
    Optional: open this once in browser to initialize db.
    Safer to run init from terminal, but this helps beginners.
    """
    try:
        init_db()
        return "Database initialized successfully ✅"
    except Exception as e:
        return f"DB init failed: {e}", 500


# -----------------------------
# RUN APP
# -----------------------------
if __name__ == "__main__":
    # NOTE: You can comment this out if you prefer manual init_db()
    # init_db()

    app.run(debug=True)
