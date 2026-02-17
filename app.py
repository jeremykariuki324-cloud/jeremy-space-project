import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATABASE = "site.db"


# --------------------------
# Database Connection
# --------------------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------
# Initialize Database
# --------------------------
def init_db():
    conn = get_db_connection()
    with open("schema.sql") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


# --------------------------
# Home
# --------------------------
@app.route("/")
def index():
    return render_template("index.html")


# --------------------------
# Register
# --------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password),
        )
        conn.commit()
        conn.close()

        flash("Registration successful. Please login.")
        return redirect(url_for("login"))

    return render_template("register.html")


# --------------------------
# Login
# --------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password),
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Logged in successfully.")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials.")

    return render_template("login.html")


# --------------------------
# Logout
# --------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# --------------------------
# Dashboard
# --------------------------
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]

        conn.execute(
            "INSERT INTO posts (title, content, user_id) VALUES (?, ?, ?)",
            (title, content, session["user_id"]),
        )
        conn.commit()

    posts = conn.execute(
        """
        SELECT posts.*, users.username
        FROM posts
        JOIN users ON posts.user_id = users.id
        ORDER BY posts.created_at DESC
        """
    ).fetchall()

    conn.close()

    return render_template("dashboard.html", posts=posts)


# --------------------------
# View Single Post
# --------------------------
@app.route("/post/<int:post_id>")
def post(post_id):
    conn = get_db_connection()
    post = conn.execute(
        """
        SELECT posts.*, users.username
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = ?
        """,
        (post_id,),
    ).fetchone()
    conn.close()

    return render_template("post.html", post=post)


# --------------------------
# REQUIRED FOR RENDER
# --------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
