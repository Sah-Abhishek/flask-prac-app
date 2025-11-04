from flask import Flask, request, jsonify
import sqlite3
import os

app = Flask(__name__)
DB_FILE = "users.db"

# --- Utility: initialize database ---
def init_db():
    if not os.path.exists(DB_FILE):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL
                );
            """)
            print("✅ Database initialized.")


# --- Utility: get database connection ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # enables dict-like access
    return conn


# --- Route: Add a user ---
@app.route("/add_user", methods=["POST"])
def add_user():
    data = request.get_json()

    if not data or not data.get("name") or not data.get("email"):
        return jsonify({"error": "Name and email are required"}), 400

    try:
        conn = get_db_connection()
        conn.execute("INSERT INTO users (name, email) VALUES (?, ?)", 
                     (data["name"], data["email"]))
        conn.commit()
        conn.close()
        return jsonify({"message": "User added successfully"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already exists"}), 409


# --- Route: Get all users ---
@app.route("/users", methods=["GET"])
def get_users():
    conn = get_db_connection()
    users = conn.execute("SELECT id, name, email FROM users").fetchall()
    conn.close()
    return jsonify([dict(u) for u in users]), 200


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
