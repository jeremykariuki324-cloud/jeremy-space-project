import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)

# IMPORTANT: set a secret key (Render needs it)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# ------------------------------------------------------------
# DATABASE PATH (works locally + on Render)
# Render filesystem is ephemeral, but this will still work per-deploy.
# ------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "site.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # USERS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # POSTS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        username TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


# ensure tables exist on startup (Render included)
init_db()


# ------------------------------------------------------------
# AUTH HELPERS
# ------------------------------------------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        if not username or not password:
            return "Username and password required", 400

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
                (username, password, datetime.utcnow().isoformat())
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Username already exists. Go to /login", 400

        conn.close()
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()

        # plain text check (simple for now)
        if user and user["password"] == password:
            session["user"] = user["username"]
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid username or password"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    # create post
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()

        if title and content:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO posts (title, content, username, created_at) VALUES (?, ?, ?, ?)",
                (title, content, session["user"], datetime.utcnow().isoformat())
            )
            conn.commit()
            conn.close()

        return redirect(url_for("dashboard"))

    # show posts
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM posts ORDER BY id DESC")
    posts = cur.fetchall()
    conn.close()

    return render_template("dashboard.html", posts=posts)


@app.route("/posts")
def posts():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM posts ORDER BY id DESC")
    posts = cur.fetchall()
    conn.close()
    return render_template("posts.html", posts=posts)


# ------------------------------------------------------------
# RUN (LOCAL) - Render uses gunicorn, but keep this for local dev
# ------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
