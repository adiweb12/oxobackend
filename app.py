from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from openai import OpenAI

# ======================
# CONFIG
# ======================
OPENAI_API_KEY = "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"
GPT_MODEL = "gpt-4.1"
DB_FILE = "memory.db"

client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
CORS(app)   # IMPORTANT for frontend connection

# ======================
# DATABASE
# ======================
def get_db():
    return sqlite3.connect(DB_FILE)

def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        block_id INTEGER,
        role TEXT,
        content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    db.commit()
    db.close()

init_db()

# ======================
# DB HELPERS
# ======================
def create_block(name):
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT OR IGNORE INTO blocks (name) VALUES (?)", (name,))
    db.commit()
    db.close()

def get_block_id(name):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM blocks WHERE name = ?", (name,))
    row = cur.fetchone()
    db.close()
    return row[0] if row else None

def save_message(block_id, role, content):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO messages (block_id, role, content) VALUES (?, ?, ?)",
        (block_id, role, content)
    )
    db.commit()
    db.close()

def load_block_messages(block_id):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT role, content FROM messages WHERE block_id = ? ORDER BY id",
        (block_id,)
    )
    rows = cur.fetchall()
    db.close()
    return [{"role": r, "content": c} for r, c in rows]

# ======================
# GPT CALL
# ======================
def call_gpt(messages):
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages,
        temperature=0.2,
        max_tokens=4096
    )
    return response.choices[0].message.content

# ======================
# API ROUTES
# ======================

@app.route("/blocks", methods=["POST"])
def new_block():
    name = request.json.get("name")
    if not name:
        return jsonify({"error": "Block name required"}), 400

    create_block(name)
    return jsonify({"status": "created", "block": name})

@app.route("/blocks", methods=["GET"])
def list_blocks():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT name FROM blocks ORDER BY id DESC")
    rows = cur.fetchall()
    db.close()
    return jsonify([r[0] for r in rows])

@app.route("/chat", methods=["POST"])
def chat():
    block_name = request.json.get("block")
    user_msg = request.json.get("message")

    if not block_name or not user_msg:
        return jsonify({"error": "Block and message required"}), 400

    block_id = get_block_id(block_name)
    if not block_id:
        return jsonify({"error": "Block not found"}), 404

    save_message(block_id, "user", user_msg)

    block_messages = load_block_messages(block_id)

    system_prompt = {
        "role": "system",
        "content": (
            "You are a senior coding AI.\n"
            "You must ONLY use information from this block.\n"
            "Never reference other blocks.\n"
            "Write complete, production-ready code.\n"
            "Avoid placeholders unless asked."
        )
    }

    context = [system_prompt] + block_messages
    ai_reply = call_gpt(context)

    save_message(block_id, "assistant", ai_reply)

    return jsonify({"reply": ai_reply})

# ======================
# RUN
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
