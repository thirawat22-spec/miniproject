import os
import sqlite3
from flask import Flask, render_template, request, redirect, session
from db import get_db
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
bcrypt = Bcrypt(app)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def home():
    if "user_id" in session:
        return redirect("/dashboard")
    return redirect("/login")

# ======================
# 🔐 REGISTER
# ======================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="Username นี้มีอยู่แล้ว")
        finally:
            conn.close()
        return redirect("/login")
    return render_template("register.html")

# ======================
# 🔑 LOGIN
# ======================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, password FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()
        if user and bcrypt.check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect("/dashboard")
        return render_template("login.html", error="Username หรือ Password ไม่ถูกต้อง")
    return render_template("login.html")

# ======================
# 🚪 LOGOUT
# ======================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ======================
# 🎮 DASHBOARD — แสดงข้อมูลทุกคน
# ======================
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    conn = get_db()
    cur = conn.cursor()
    # ดึงข้อมูลทุกคน พร้อม username เจ้าของ
    cur.execute("""
        SELECT champions.id, champions.role, champions.champion_name,
               champions.image, champions.user_id, users.username
        FROM champions
        JOIN users ON champions.user_id = users.id
        ORDER BY champions.id DESC
    """)
    data = cur.fetchall()
    conn.close()
    return render_template("dashboard.html", data=data, current_user_id=session["user_id"])

# ======================
# ➕ ADD — หน้าเพิ่มข้อมูล
# ======================
@app.route("/add", methods=["GET", "POST"])
def add():
    if "user_id" not in session:
        return redirect("/login")
    if request.method == "POST":
        role = request.form["role"]
        champion = request.form["champion"]
        image_filename = None
        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename):
            image_filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], image_filename))
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO champions (user_id, role, champion_name, image) VALUES (?, ?, ?, ?)",
            (session["user_id"], role, champion, image_filename)
        )
        conn.commit()
        conn.close()
        return redirect("/dashboard")
    return render_template("add.html")

# ======================
# ❌ DELETE — เฉพาะเจ้าของ
# ======================
@app.route("/delete/<int:id>")
def delete(id):
    if "user_id" not in session:
        return redirect("/login")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT image FROM champions WHERE id=? AND user_id=?", (id, session["user_id"]))
    row = cur.fetchone()
    if row and row["image"]:
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], row["image"])
        if os.path.exists(filepath):
            os.remove(filepath)
    cur.execute("DELETE FROM champions WHERE id=? AND user_id=?", (id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect("/dashboard")

# ======================
# ✏️ EDIT — เฉพาะเจ้าของ
# ======================
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if "user_id" not in session:
        return redirect("/login")
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        role = request.form["role"]
        champion = request.form["champion"]
        cur.execute("SELECT image FROM champions WHERE id=? AND user_id=?", (id, session["user_id"]))
        old = cur.fetchone()
        image_filename = old["image"] if old else None
        file = request.files.get("image")
        if file and file.filename and allowed_file(file.filename):
            if image_filename:
                old_path = os.path.join(app.config["UPLOAD_FOLDER"], image_filename)
                if os.path.exists(old_path):
                    os.remove(old_path)
            image_filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], image_filename))
        cur.execute(
            "UPDATE champions SET role=?, champion_name=?, image=? WHERE id=? AND user_id=?",
            (role, champion, image_filename, id, session["user_id"])
        )
        conn.commit()
        conn.close()
        return redirect("/dashboard")
    cur.execute("SELECT * FROM champions WHERE id=? AND user_id=?", (id, session["user_id"]))
    data = cur.fetchone()
    conn.close()
    if not data:
        return redirect("/dashboard")
    return render_template("edit.html", data=data)

if __name__ == "__main__":
    app.run(debug=True)
