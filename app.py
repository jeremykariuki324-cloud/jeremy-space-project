import os
import sqlite3
import tempfile
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ----------------------------
# REQUIRED FOR RENDER
# ----------------------------
# Set SECRET_KEY in Render > Settings > Environment
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# ✅ SQLite path: Render-friendly (writable)
# - On Render: uses /tmp (or a mounted disk path if you later add one)
# - Locally: uses your system temp folder
BASE_DB_DIR = os.environ.get("RENDER_DISK_PATH") or tempfile.gettempdir()
DB_PATH = os.path.join(BASE_DB_DIR, "site.db")


# ----------------------------
# DATABASE HELPERS
# ----------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initializes DB tables.
    If schema.sql exists in project root, it will run it.
    Otherwise, it creates the tables directly.
    """
    conn = get_db()
    cur = conn.cursor()

    schema_file = os.path.join(os.path.dirname(__file__), "schema.sql")
    if os.path.exists(schema_file):
        with open(schema_file, "r", encoding="utf-8") as f:
            cur.executescript(f.read())
    else:
        # Fallback schema
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)

    conn.commit()
    conn.close()


# Run once on startup (important for Render)
init_db()


# ----------------------------
# AUTH HELPERS
# ----------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper


def current_user():
    if "user_id" not in session:
        return None
    return {"id": session["user_id"], "username": session.get("username")}


# ----------------------------
# ROUTES
# ----------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash),
            )
            conn.commit()
            user_id = cur.lastrowid
            conn.close()

            # Auto-login after register
            session["user_id"] = user_id
            session["username"] = username

            flash("Account created successfully!", "success")
            return redirect(url_for("dashboard"))

        except sqlite3.IntegrityError:
            flash("Username or email already exists.", "danger")
            return redirect(url_for("register"))
        except Exception as e:
            # Show a friendly error, but keep details in logs
            app.logger.exception("Register failed")
            flash("Registration failed. Please try again.", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not email or not password:
            flash("Email and password are required.", "danger")
            return redirect(url_for("login"))

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    user = current_user()

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()

        if not title or not content:
            flash("Title and content are required.", "danger")
            return redirect(url_for("dashboard"))

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO posts (user_id, title, content, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], title, content, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        conn.close()

        flash("Post published!", "success")
        return redirect(url_for("dashboard"))

    # Show latest posts
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.title, p.content, p.created_at, u.username
        FROM posts p
        JOIN users u ON u.id = p.user_id
        ORDER BY p.id DESC
    """)
    posts = cur.fetchall()
    conn.close()

    return render_template("dashboard.html", posts=posts, user=user)


@app.route("/posts")
def posts():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.title, p.content, p.created_at, u.username
        FROM posts p
        JOIN users u ON u.id = p.user_id
        ORDER BY p.id DESC
    """)
    posts_list = cur.fetchall()
    conn.close()

    return render_template("posts.html", posts=posts_list)


@app.route("/post/<int:post_id>")
def post_detail(post_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.title, p.content, p.created_at, u.username
        FROM posts p
        JOIN users u ON u.id = p.user_id
        WHERE p.id = ?
    """, (post_id,))
    post = cur.fetchone()
    conn.close()

    if not post:
        abort(404)

    return render_template("post.html", post=post)


# ----------------------------
# RUN (LOCAL) + RENDER PORT FIX
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
