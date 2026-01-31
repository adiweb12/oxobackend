from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import OpenAI

# ======================
# CONFIG (Direct Secrets)
# ======================
OPENAI_API_KEY = "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"
GPT_MODEL = "gpt-4.1"
DATABASE_URL = "postgresql://testbase_nriq_user:YblTg3DsAbznOu3mTsedodGbbeRNzOvQ@dpg-d5uvggcoud1c73859uc0-a/testbase_nriq"

client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
CORS(app)   # Allow frontend connections

# ======================
# DATABASE
# ======================
def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS blocks (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        block_id INTEGER REFERENCES blocks(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    db.commit()
    cur.close()
    db.close()

init_db()

# ======================
# DB HELPERS
# ======================
def create_block(name):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO blocks (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
        (name,)
    )
    db.commit()
    cur.close()
    db.close()

def get_block_id(name):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM blocks WHERE name = %s", (name,))
    row = cur.fetchone()
    cur.close()
    db.close()
    return row["id"] if row else None

def save_message(block_id, role, content):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO messages (block_id, role, content) VALUES (%s, %s, %s)",
        (block_id, role, content)
    )
    db.commit()
    cur.close()
    db.close()

def load_block_messages(block_id):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT role, content FROM messages WHERE block_id = %s ORDER BY id",
        (block_id,)
    )
    rows = cur.fetchall()
    cur.close()
    db.close()
    return rows

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
    cur.close()
    db.close()
    return jsonify([r["name"] for r in rows])

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
