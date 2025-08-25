from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
import os

# 🔹 new import
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = "secret123"  # needed for session + flash

# 🔹 add socketio
socketio = SocketIO(app)

# 🔹 in-memory chat (not persistent)
chat_messages = []

# --- DB init ---
def init_db():
    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        # Users table
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                genre TEXT
            )
        """)
        # Movies table
        c.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                date TEXT,
                imdb REAL,
                review TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        conn.commit()

init_db()

# --- Auth: Register ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        genre = request.form["genre"].strip()

        try:
            with sqlite3.connect("database.db") as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO users (username, password, genre) VALUES (?, ?, ?)",
                    (username, password, genre),
                )
                conn.commit()
            flash("✅ Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("⚠️ Username already exists. Try another one.", "warning")
            return redirect(url_for("register"))
        except Exception as e:
            flash(f"❌ Error: {e}", "danger")
            return redirect(url_for("register"))

    return render_template("register.html")

# --- Auth: Login ---
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute(
                "SELECT id, username, password, genre FROM users WHERE username=? AND password=?",
                (username, password),
            )
            user = c.fetchone()

        if user:
            session["user_id"] = user[0]
            session["genre"] = user[3]
            session["username"] = user[1]
            flash(f"👋 Welcome back, {user[1]}!", "success")
            return redirect(url_for("home"))
        else:
            flash("❌ Invalid credentials", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

# --- Home + simple recommendations ---
@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_genre = session.get("genre", "")

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute(
            "SELECT username FROM users WHERE genre=? AND id!=?",
            (user_genre, session["user_id"]),
        )
        similar_users = [row[0] for row in c.fetchall()]

    rec = (
        f"Because you like {user_genre}, you might enjoy movies similar to users who also like {user_genre}."
        if user_genre
        else "Tell us your favorite genre to get recommendations!"
    )

    return render_template("home.html", 
                           rec=rec, 
                           similar_users=similar_users,
                           chat_messages=chat_messages)   # 🔹 pass chat to template

# --- Chat socket events ---
@socketio.on("message")
def handle_message(msg):
    username = session.get("username", "Anonymous")
    message = f"{username}: {msg}"
    chat_messages.append(message)  # 🔹 store in memory
    emit("message", message, broadcast=True)

# --- Add movie ---
@app.route("/add_movie", methods=["GET", "POST"])
def add_movie():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form["name"].strip()
        date = request.form["date"].strip()
        imdb = request.form["imdb"].strip()
        review = request.form["review"].strip()

        with sqlite3.connect("database.db") as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO movies (user_id, name, date, imdb, review) VALUES (?, ?, ?, ?, ?)",
                (session["user_id"], name, date, imdb, review),
            )
            conn.commit()

        flash("✅ Movie added!", "success")
        return redirect(url_for("view_movies"))

    return render_template("add_movie.html")

# --- View movies ---
@app.route("/view_movies")
def view_movies():
    if "user_id" not in session:
        return redirect(url_for("login"))

    with sqlite3.connect("database.db") as conn:
        c = conn.cursor()
        c.execute(
            "SELECT name, date, imdb, review FROM movies WHERE user_id=?",
            (session["user_id"],),
        )
        movies = c.fetchall()

    return render_template("view_movies.html", movies=movies)

# --- Optional: Logout ---
@app.route("/logout")
def logout():
    session.clear()
    chat_messages.clear()   # 🔹 clear chat when user logs out
    flash("👋 Logged out.", "info")
    return redirect(url_for("login"))

# --- Run ---
if __name__ == "__main__":
    socketio.run(app, debug=True)   # 🔹 run with socketio
